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


def fetch_works_for_author(author_openalex_id: str, from_year: Optional[int], mailto: Optional[str]) -> List[Dict]:
    """Fetch works for an OpenAlex author using polite pagination."""
    works: List[Dict] = []
    try:
        s = _session(mailto)
        # Filter by authorship author id and from year via publication_date
        # Build filter: always filter by author; add from_publication_date if requested
        filt = f"authorships.author.id:{author_openalex_id}"
        if from_year:
            filt = f"{filt},from_publication_date:{from_year}-01-01"
        cursor = "*"
        while True:
            params = {
                "filter": filt,
                "per_page": 200,
                "cursor": cursor,
                "sort": "cited_by_count:desc",
            }
            resp = s.get(f"{BASE_URL}/works", params=params, timeout=30)
            data = resp.json()
            batch = data.get("results", []) or []
            for w in batch:
                title = (w or {}).get("display_name") or ""
                year = (w or {}).get("publication_year")
                wtype = (w or {}).get("type")
                # Filter out datasets/components and file-like titles
                if _looks_like_file_title(title):
                    continue
                allowed_types = {"journal-article", "proceedings-article", "book-chapter", "report", "book", "preprint"}
                if wtype and wtype not in allowed_types:
                    continue
                abstract = _decode_abstract((w or {}).get("abstract_inverted_index"))
                primary_location = (w or {}).get("primary_location") or {}
                url = primary_location.get("landing_page_url") or (w or {}).get("openalex")
                host_venue = (w or {}).get("host_venue") or {}
                journal = host_venue.get("display_name")
                cites = (w or {}).get("cited_by_count")
                # Join authors
                authorships = (w or {}).get("authorships") or []
                auths = ", ".join([ (a.get("author") or {}).get("display_name", "") for a in authorships ])
                works.append({
                    "title": title,
                    "authors": auths,
                    "abstract": abstract or "",
                    "year": year,
                    "num_citations": cites,
                    "journal": journal or "",
                    "pub_url": url or "",
                })
            cursor = data.get("meta", {}).get("next_cursor")
            if not cursor:
                break
    except Exception as e:
        logger.error(f"OpenAlex works fetch failed for {author_openalex_id}: {e}")
    return works


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
        # Ensure optional columns
        try:
            cols = [row[1] for row in conn.execute("PRAGMA table_info(publications)").fetchall()]
            if 'journal' not in cols:
                conn.execute("ALTER TABLE publications ADD COLUMN journal TEXT")
            if 'authors' not in cols:
                conn.execute("ALTER TABLE publications ADD COLUMN authors TEXT")
        except Exception:
            pass
        count = 0
        for w in works:
            conn.execute(
                "INSERT OR REPLACE INTO publications (author_id, title, year, abstract, url, citations, journal, authors) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    author_id,
                    w.get("title", ""),
                    w.get("year"),
                    w.get("abstract"),
                    w.get("pub_url"),
                    w.get("num_citations"),
                    w.get("journal"),
                    w.get("authors"),
                ),
            )
            count += 1
        conn.commit()
        return count
    finally:
        conn.close()
