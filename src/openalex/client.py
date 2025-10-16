"""OpenAlex client utilities.

Implements polite access to OpenAlex:
- Always include a `mailto` parameter to join the polite pool
- Use cursor-based pagination with reasonable page size

This module does not manage secrets and reads contact email from settings.json.
"""

from __future__ import annotations

import logging
import sqlite3
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple

import requests

logger = logging.getLogger(__name__)

BASE_URL = "https://api.openalex.org"


def _get_mailto(settings_path: Path = Path("./settings.json")) -> Optional[str]:
    try:
        import json

        raw = json.loads(settings_path.read_text())
        return raw.get("openalex_email")
    except Exception:
        return None


def _session(mailto: Optional[str]) -> requests.Session:
    s = requests.Session()
    s.headers.update({"User-Agent": "ScholarSlackBot/1.0"})
    # We'll add mailto to params in each call
    s.params = {"mailto": mailto} if mailto else {}
    return s


def find_author_id_by_name(name: str, mailto: Optional[str]) -> Optional[str]:
    try:
        s = _session(mailto)
        resp = s.get(f"{BASE_URL}/authors", params={"search": name, "per_page": 1}, timeout=20)
        data = resp.json()
        results = data.get("results", [])
        if results:
            return results[0].get("id")
    except Exception as e:
        logger.warning(f"OpenAlex author search failed for '{name}': {e}")
    return None


def get_author_name_by_id(author_openalex_id: str, mailto: Optional[str]) -> Optional[str]:
    """Fetch an OpenAlex author's display name by ID.

    Returns the display name or None if not found.
    """
    try:
        s = _session(mailto)
        # Accept both bare IDs (A...) and full URLs (https://openalex.org/A...)
        if author_openalex_id.startswith('http'):
            url = author_openalex_id
        else:
            url = f"{BASE_URL}/authors/{author_openalex_id}"
        resp = s.get(url, timeout=20)
        if resp.status_code != 200:
            return None
        data = resp.json()
        return data.get("display_name")
    except Exception as e:
        logger.warning(f"OpenAlex author get failed for '{author_openalex_id}': {e}")
        return None


def find_author_by_orcid(orcid: str, mailto: Optional[str]) -> Optional[Dict[str, str]]:
    """Resolve an ORCID to an OpenAlex author record.

    Returns dict with keys {"id", "display_name"} if found, else None.
    """
    try:
        # Normalize ORCID (strip URL prefix)
        o = orcid.strip()
        if o.startswith('http'):
            o = o.rstrip('/').split('/')[-1]
        s = _session(mailto)
        resp = s.get(f"{BASE_URL}/authors", params={"filter": f"orcid:{o}", "per_page": 1}, timeout=20)
        if resp.status_code != 200:
            return None
        data = resp.json() or {}
        results = data.get('results') or []
        if not results:
            return None
        rec = results[0]
        return {"id": rec.get("id"), "display_name": rec.get("display_name")}
    except Exception as e:
        logger.warning(f"OpenAlex ORCID lookup failed for '{orcid}': {e}")
        return None


def _normalize_doi(doi_val: Optional[str]) -> Optional[str]:
    if not doi_val:
        return None
    d = doi_val.strip()
    # OpenAlex returns DOIs sometimes as 'https://doi.org/10.x' or 'doi:10.x'
    d = d.replace('DOI:', '').replace('doi:', '').strip()
    if d.lower().startswith('https://doi.org/'):
        d = d[len('https://doi.org/'):]
    if d.lower().startswith('http://doi.org/'):
        d = d[len('http://doi.org/'):]
    return d or None


def _normalize_openalex_author_id(author_id: str) -> str:
    if not author_id:
        return author_id
    if author_id.startswith("http"):
        # Extract terminal segment
        try:
            return author_id.rstrip('/').split('/')[-1]
        except Exception:
            return author_id
    return author_id


def fetch_works_for_author(author_openalex_id: str, from_year: Optional[int], mailto: Optional[str]) -> List[Dict]:
    """Fetch all works for an OpenAlex author using polite cursor pagination.

    This uses the official Works endpoint with the `author.id:A...` filter,
    `per_page=200`, and `cursor=*` to iterate through all of an author's works.
    We always join the OpenAlex polite pool by including the `mailto` param.

    Args:
        author_openalex_id: The author's OpenAlex ID. Accepts full URL or bare key (e.g., "A123...").
        from_year: Optional lower bound (inclusive) for publication year; if None, fetch full history.
        mailto: Optional contact email for the polite pool.

    Returns:
        List of normalized work dicts with keys:
        title, authors, abstract, year, num_citations, journal, pub_url, doi
    """
    works: List[Dict] = []
    try:
        s = _session(mailto)
        # Use official works API filter: author.id:A... (recommended by OpenAlex)
        oaid = _normalize_openalex_author_id(author_openalex_id)
        filt = f"author.id:{oaid}"
        if from_year:
            # Use from_publication_date for year ranges per OpenAlex docs
            filt = f"{filt},from_publication_date:{from_year}-01-01"
        cursor = "*"
        while True:
            params = {
                "filter": filt,
                # Use dashed style per OpenAlex docs; underscore often works too
                "per-page": 200,
                "cursor": cursor,
                # Sorting is optional but helps surface high-impact first if UI streams
                "sort": "cited_by_count:desc",
                # Select only fields we use to reduce payload size
                "select": ",".join([
                    "id",
                    "doi",
                    "display_name",
                    "publication_year",
                    "abstract_inverted_index",
                    "primary_location",
                    "cited_by_count",
                    "authorships",
                    "type",
                    # Prefer canonical topical signals from OpenAlex
                    "topics",
                    "concepts",
                ]),
            }
            resp = s.get(f"{BASE_URL}/works", params=params, timeout=30)
            # Raise for non-200 to surface proper logging and exit
            resp.raise_for_status()
            data = resp.json() or {}
            batch = data.get("results", []) or []
            for w in batch:
                title = (w or {}).get("display_name") or ""
                year = (w or {}).get("publication_year")
                wtype = (w or {}).get("type")
                wtype_xref = None  # not selected; keep variable for backward-compat in checks
                # Filter out datasets/components and file-like titles
                if _looks_like_file_title(title):
                    continue
                # Accept either OpenAlex `type` or Crossref-style `type_crossref` (if present)
                allowed_types = {
                    # OpenAlex canonical types
                    "journal-article", "proceedings-article", "book-chapter", "report", "book", "preprint", "posted-content",
                    # Crossref style sometimes appears as `type`
                    "article",
                }
                # Skip if both provided type indicators are not allowed; if only one present and not allowed, skip
                if (wtype and wtype not in allowed_types) and (wtype_xref and wtype_xref not in allowed_types):
                    continue
                if (wtype and wtype not in allowed_types) and (not wtype_xref):
                    continue
                if (wtype_xref and wtype_xref not in allowed_types) and (not wtype):
                    continue
                abstract = _decode_abstract((w or {}).get("abstract_inverted_index"))
                primary_location = (w or {}).get("primary_location") or {}
                # Prefer landing page; fallback to PDF; else use the work's id (OpenAlex URL)
                url = primary_location.get("landing_page_url") or primary_location.get("pdf_url") or (w or {}).get("id")
                # Use primary_location.source.display_name as journal/source label
                src = (primary_location.get("source") or {}) if isinstance(primary_location, dict) else {}
                journal = src.get("display_name")
                doi = _normalize_doi((w or {}).get("doi"))
                cites = (w or {}).get("cited_by_count")
                # Join authors
                authorships = (w or {}).get("authorships") or []
                auths = ", ".join([ (a.get("author") or {}).get("display_name", "") for a in authorships ])
                # Extract institutions from authorships for geo stats
                insts = []
                try:
                    for a in authorships:
                        for inst in (a.get("institutions") or []):
                            inst_id = (inst.get("id") or "").strip()
                            inst_name = (inst.get("display_name") or "").strip()
                            ccode = (inst.get("country_code") or "").strip().upper()
                            if not inst_id and not inst_name and not ccode:
                                continue
                            insts.append({"id": inst_id, "name": inst_name, "country_code": ccode})
                except Exception:
                    insts = []
                # Extract topics (prefer `topics`, fallback to `concepts`)
                topics_list = []
                try:
                    raw_topics = (w or {}).get("topics") or []
                    if isinstance(raw_topics, list) and raw_topics:
                        topics_list = [
                            {
                                "term": (t.get("display_name") or "").strip(),
                                "score": t.get("score"),
                            }
                            for t in raw_topics
                            if isinstance(t, dict) and (t.get("display_name") or "").strip()
                        ]
                    elif isinstance((w or {}).get("concepts"), list):
                        raw_concepts = (w or {}).get("concepts") or []
                        topics_list = [
                            {
                                "term": (c.get("display_name") or "").strip(),
                                "score": c.get("score"),
                            }
                            for c in raw_concepts
                            if isinstance(c, dict) and (c.get("display_name") or "").strip()
                        ]
                except Exception:
                    topics_list = []

                works.append({
                    "title": title,
                    "authors": auths,
                    "abstract": abstract or "",
                    "year": year,
                    "num_citations": cites,
                    "journal": journal or "",
                    "pub_url": url or "",
                    "doi": doi or "",
                    "topics": topics_list,
                    "institutions": insts,
                })
            cursor = data.get("meta", {}).get("next_cursor")
            if not cursor:
                break
    except Exception as e:
        logger.error(f"OpenAlex works fetch failed for {author_openalex_id}: {e}")
    if not works:
        logger.info("OpenAlex returned 0 works for author %s (from_year=%s)", author_openalex_id, from_year)
    else:
        logger.info("OpenAlex fetched %d works for author %s", len(works), author_openalex_id)
    return works


def get_author_metrics(author_openalex_id: str, mailto: Optional[str]) -> Optional[Dict[str, object]]:
    """Fetch summary metrics for an author from OpenAlex.

    Retrieves `works_count`, `cited_by_count`, and `summary_stats` (e.g., `h_index`)
    via the Authors endpoint. Useful to validate our locally-computed totals or
    to display quick stats without scanning all works.

    Args:
        author_openalex_id: OpenAlex Author ID; accepts URL or bare key.
        mailto: Optional polite pool contact email.

    Returns:
        Dict with keys: id, display_name, works_count, cited_by_count, summary_stats, works_api_url
        or None on failure.
    """
    try:
        s = _session(mailto)
        aid = _normalize_openalex_author_id(author_openalex_id)
        url = f"{BASE_URL}/authors/{aid}"
        params = {
            "select": ",".join([
                "id",
                "display_name",
                "works_count",
                "cited_by_count",
                "summary_stats",
                "works_api_url",
            ])
        }
        resp = s.get(url, params=params, timeout=20)
        if resp.status_code != 200:
            return None
        data = resp.json() or {}
        return {
            "id": data.get("id"),
            "display_name": data.get("display_name"),
            "works_count": data.get("works_count"),
            "cited_by_count": data.get("cited_by_count"),
            "summary_stats": data.get("summary_stats"),
            "works_api_url": data.get("works_api_url"),
        }
    except Exception as e:
        logger.warning(f"OpenAlex author metrics fetch failed for '{author_openalex_id}': {e}")
        return None


def _decode_abstract(inv_index: Optional[Dict[str, List[int]]]) -> Optional[str]:
    # OpenAlex stores abstracts as inverted indices; reconstruct string
    if not inv_index:
        return None
    # Build a list of words positioned by their first index
    max_pos = 0
    for positions in inv_index.values():
        max_pos = max(max_pos, max(positions))
    words = [None] * (max_pos + 1)
    for word, positions in inv_index.items():
        for pos in positions:
            if 0 <= pos < len(words):
                words[pos] = word
    return " ".join([w for w in words if w])


def _looks_like_file_title(title: str) -> bool:
    if not title:
        return False
    t = title.strip().lower()
    import re
    # Typical file extensions
    if re.search(r"\.(zip|tar|tar\.gz|gz|bz2|7z|rar|mat|csv|tsv|xlsx|xls|docx?|pptx?|txt)$", t):
        return True
    # Likely file-like if contains no spaces and has an extension
    if ('.' in t) and (' ' not in t):
        return True
    return False


def upsert_publications(author_id: str, works: Iterable[Dict], db_path: Path = Path("./src/publications.db")) -> int:
    """Insert/replace works into publications DB for the author.

    Returns number of upserted rows.
    """
    conn = sqlite3.connect(db_path)
    try:
        conn.execute(
            """CREATE TABLE IF NOT EXISTS publications (
                author_id TEXT,
                title TEXT,
                year INTEGER,
                abstract TEXT,
                url TEXT,
                citations INTEGER,
                PRIMARY KEY (author_id, title)
            )"""
        )
        # Ensure optional columns and migrate PK if needed
        try:
            cols_info = conn.execute("PRAGMA table_info(publications)").fetchall()
            cols = [row[1] for row in cols_info]
            if 'journal' not in cols:
                conn.execute("ALTER TABLE publications ADD COLUMN journal TEXT")
            if 'authors' not in cols:
                conn.execute("ALTER TABLE publications ADD COLUMN authors TEXT")
            if 'doi' not in cols:
                conn.execute("ALTER TABLE publications ADD COLUMN doi TEXT")
            if 'source_id' not in cols:
                conn.execute("ALTER TABLE publications ADD COLUMN source_id TEXT DEFAULT ''")

            # Migrate PK to (author_id, title, source_id) if still on old schema
            pk_cols = [row[1] for row in cols_info if row[5] > 0]
            if pk_cols == ['author_id', 'title']:
                conn.execute("BEGIN TRANSACTION")
                conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS publications_v2 (
                        author_id TEXT,
                        title TEXT,
                        source_id TEXT,
                        year INTEGER,
                        abstract TEXT,
                        url TEXT,
                        doi TEXT,
                        citations INTEGER,
                        journal TEXT,
                        authors TEXT,
                        PRIMARY KEY (author_id, title, source_id)
                    )
                    """
                )
                conn.execute(
                    """
                    INSERT OR REPLACE INTO publications_v2 (
                        author_id, title, source_id, year, abstract, url, doi, citations, journal, authors
                    )
                    SELECT
                        author_id,
                        title,
                        CASE
                            WHEN COALESCE(doi, '') <> '' THEN doi
                            WHEN COALESCE(url, '') <> '' THEN url
                            ELSE title
                        END AS source_id,
                        year,
                        abstract,
                        url,
                        doi,
                        citations,
                        journal,
                        authors
                    FROM publications
                    """
                )
                conn.execute("DROP TABLE publications")
                conn.execute("ALTER TABLE publications_v2 RENAME TO publications")
                conn.execute("COMMIT")
        except Exception:
            pass
        # Ensure canonical topics table exists (author_id, source_id, term, score)
        try:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS publication_topics (
                    author_id TEXT,
                    source_id TEXT,
                    term TEXT,
                    score REAL,
                    PRIMARY KEY (author_id, source_id, term)
                )
                """
            )
        except Exception:
            pass
        # Ensure institutions table exists for geo stats
        try:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS publication_institutions (
                    author_id TEXT,
                    source_id TEXT,
                    institution_id TEXT,
                    institution_name TEXT,
                    country_code TEXT,
                    PRIMARY KEY (author_id, source_id, institution_id)
                )
                """
            )
        except Exception:
            pass

        def _extract_domain(url: Optional[str]) -> Optional[str]:
            if not url:
                return None
            try:
                from urllib.parse import urlparse
                netloc = urlparse(url).netloc
                return netloc.lower() if netloc else None
            except Exception:
                return None

        def _source_tag(journal: Optional[str], url: Optional[str]) -> Optional[str]:
            j = (journal or "").strip()
            d = _extract_domain(url) or ""
            if "arxiv" in j.lower() or "arxiv" in d:
                return "arXiv"
            if j:
                return j
            if d:
                return d
            return None

        count = 0
        for w in works:
            title = (w.get("title") or "").strip()
            year = w.get("year")
            abstract = w.get("abstract")
            url = (w.get("pub_url") or "").strip()
            doi = (w.get("doi") or "").strip()
            cites = w.get("num_citations")
            journal = (w.get("journal") or "").strip()
            authors = (w.get("authors") or "").strip()
            topics = w.get("topics") or []  # list of {term, score}
            institutions = w.get("institutions") or []  # list of {id, name, country_code}

            # Ensure integer citations
            try:
                citations_val = int(cites) if cites is not None else 0
            except Exception:
                citations_val = 0

            # If an entry with same (author_id, title) exists but has a different URL/journal,
            # keep both by disambiguating the title with a source tag.
            existing = conn.execute(
                "SELECT url, journal FROM publications WHERE author_id = ? AND title = ?",
                (author_id, title),
            ).fetchone()

            source_id = doi if doi else (url if url else title)
            if existing is None:
                conn.execute(
                    "INSERT OR REPLACE INTO publications (author_id, title, source_id, year, abstract, url, doi, citations, journal, authors) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (author_id, title, source_id, year, abstract, url, doi, citations_val, journal, authors),
                )
                # Upsert topics for this source
                try:
                    if topics:
                        conn.execute(
                            "DELETE FROM publication_topics WHERE author_id = ? AND source_id = ?",
                            (author_id, source_id),
                        )
                        for t in topics:
                            term = (t.get("term") or "").strip() if isinstance(t, dict) else str(t)
                            if not term:
                                continue
                            score_val = t.get("score") if isinstance(t, dict) else None
                            conn.execute(
                                "INSERT OR REPLACE INTO publication_topics (author_id, source_id, term, score) VALUES (?, ?, ?, ?)",
                                (author_id, source_id, term, score_val),
                            )
                except Exception:
                    pass
                # Upsert topics
                try:
                    if topics:
                        conn.execute(
                            "DELETE FROM publication_topics WHERE author_id = ? AND source_id = ?",
                            (author_id, source_id),
                        )
                        for t in topics:
                            term = (t.get("term") or "").strip() if isinstance(t, dict) else str(t)
                            if not term:
                                continue
                            score_val = t.get("score") if isinstance(t, dict) else None
                            conn.execute(
                                "INSERT OR REPLACE INTO publication_topics (author_id, source_id, term, score) VALUES (?, ?, ?, ?)",
                                (author_id, source_id, term, score_val),
                            )
                except Exception:
                    pass
                # Upsert institutions
                try:
                    if institutions:
                        conn.execute(
                            "DELETE FROM publication_institutions WHERE author_id = ? AND source_id = ?",
                            (author_id, source_id),
                        )
                        seen = set()
                        for inst in institutions:
                            inst_id = (inst.get("id") or "").strip()
                            inst_name = (inst.get("name") or "").strip()
                            ccode = (inst.get("country_code") or "").strip().upper()
                            key = inst_id or inst_name
                            if not key or key in seen:
                                continue
                            seen.add(key)
                            conn.execute(
                                "INSERT OR REPLACE INTO publication_institutions (author_id, source_id, institution_id, institution_name, country_code) VALUES (?, ?, ?, ?, ?)",
                                (author_id, source_id, inst_id, inst_name, ccode),
                            )
                except Exception:
                    pass
                count += 1
                continue

            ex_url, ex_journal = (existing[0] or "").strip(), (existing[1] or "").strip()
            same_source = (ex_url == url and ex_url != "") or (ex_journal and ex_journal == journal)
            if same_source:
                # Update/replace existing
                conn.execute(
                    "INSERT OR REPLACE INTO publications (author_id, title, source_id, year, abstract, url, doi, citations, journal, authors) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (author_id, title, source_id, year, abstract, url, doi, citations_val, journal, authors),
                )
                # Replace topics for this source
                try:
                    if topics:
                        conn.execute(
                            "DELETE FROM publication_topics WHERE author_id = ? AND source_id = ?",
                            (author_id, source_id),
                        )
                        for t in topics:
                            term = (t.get("term") or "").strip() if isinstance(t, dict) else str(t)
                            if not term:
                                continue
                            score_val = t.get("score") if isinstance(t, dict) else None
                            conn.execute(
                                "INSERT OR REPLACE INTO publication_topics (author_id, source_id, term, score) VALUES (?, ?, ?, ?)",
                                (author_id, source_id, term, score_val),
                            )
                except Exception:
                    pass
                # Replace institutions for this source
                try:
                    if institutions:
                        conn.execute(
                            "DELETE FROM publication_institutions WHERE author_id = ? AND source_id = ?",
                            (author_id, source_id),
                        )
                        seen = set()
                        for inst in institutions:
                            inst_id = (inst.get("id") or "").strip()
                            inst_name = (inst.get("name") or "").strip()
                            ccode = (inst.get("country_code") or "").strip().upper()
                            key = inst_id or inst_name
                            if not key or key in seen:
                                continue
                            seen.add(key)
                            conn.execute(
                                "INSERT OR REPLACE INTO publication_institutions (author_id, source_id, institution_id, institution_name, country_code) VALUES (?, ?, ?, ?, ?)",
                                (author_id, source_id, inst_id, inst_name, ccode),
                            )
                except Exception:
                    pass
                count += 1
            else:
                # Different source (e.g., preprint vs journal) → keep both by altering title
                tag = _source_tag(journal, url) or "alt"
                alt_title = f"{title} [{tag}]"
                alt_source = doi if doi else (url if url else alt_title)
                conn.execute(
                    "INSERT OR REPLACE INTO publications (author_id, title, source_id, year, abstract, url, doi, citations, journal, authors) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (author_id, alt_title, alt_source, year, abstract, url, doi, citations_val, journal, authors),
                )
                # Insert topics for alt source as well
                try:
                    if topics:
                        conn.execute(
                            "DELETE FROM publication_topics WHERE author_id = ? AND source_id = ?",
                            (author_id, alt_source),
                        )
                        for t in topics:
                            term = (t.get("term") or "").strip() if isinstance(t, dict) else str(t)
                            if not term:
                                continue
                            score_val = t.get("score") if isinstance(t, dict) else None
                            conn.execute(
                                "INSERT OR REPLACE INTO publication_topics (author_id, source_id, term, score) VALUES (?, ?, ?, ?)",
                                (author_id, alt_source, term, score_val),
                            )
                except Exception:
                    pass
                # Insert institutions for alt source as well
                try:
                    if institutions:
                        conn.execute(
                            "DELETE FROM publication_institutions WHERE author_id = ? AND source_id = ?",
                            (author_id, alt_source),
                        )
                        seen = set()
                        for inst in institutions:
                            inst_id = (inst.get("id") or "").strip()
                            inst_name = (inst.get("name") or "").strip()
                            ccode = (inst.get("country_code") or "").strip().upper()
                            key = inst_id or inst_name
                            if not key or key in seen:
                                continue
                            seen.add(key)
                            conn.execute(
                                "INSERT OR REPLACE INTO publication_institutions (author_id, source_id, institution_id, institution_name, country_code) VALUES (?, ?, ?, ?, ?)",
                                (author_id, alt_source, inst_id, inst_name, ccode),
                            )
                except Exception:
                    pass
                count += 1
        conn.commit()
        return count
    finally:
        conn.close()
