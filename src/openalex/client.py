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


def fetch_works_for_author(author_openalex_id: str, from_year: int, mailto: Optional[str]) -> List[Dict]:
    """Fetch works for an OpenAlex author using polite pagination."""
    works: List[Dict] = []
    try:
        s = _session(mailto)
        # Filter by authorship author id and from year via publication_date
        filt = f"authorships.author.id:{author_openalex_id},from_publication_date:{from_year}-01-01"
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
            batch = data.get("results", [])
            for w in batch:
                title = w.get("display_name") or ""
                year = w.get("publication_year")
                abstract = _decode_abstract(w.get("abstract_inverted_index"))
                url = w.get("primary_location", {}).get("landing_page_url") or w.get("openalex")
                journal = w.get("host_venue", {}).get("display_name")
                cites = w.get("cited_by_count")
                # Join authors
                auths = ", ".join([
                    a.get("author", {}).get("display_name", "") for a in (w.get("authorships") or [])
                ])
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
        count = 0
        for w in works:
            conn.execute(
                "INSERT OR REPLACE INTO publications (author_id, title, year, abstract, url, citations) VALUES (?, ?, ?, ?, ?, ?)",
                (
                    author_id,
                    w.get("title", ""),
                    w.get("year"),
                    w.get("abstract"),
                    w.get("pub_url"),
                    w.get("num_citations"),
                ),
            )
            count += 1
        conn.commit()
        return count
    finally:
        conn.close()

