"""Backend-agnostic fetch facade.

Routes calls to either Google Scholar (existing) or OpenAlex (new) based on
settings in `settings.json`.
"""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace
from typing import List, Tuple

from helper_funcs import get_authors_json
import fetch_scholar
from src.openalex.client import find_author_id_by_name, fetch_works_for_author, upsert_publications, _get_mailto


def _backend() -> str:
    try:
        cfg = json.loads(Path("./settings.json").read_text())
        return cfg.get("backend", "scholar").lower()
    except Exception:
        return "scholar"


def fetch_from_json(args, idx=None):  # noqa: ANN001
    if _backend() == "scholar":
        return fetch_scholar.fetch_from_json(args, idx=idx)

    # OpenAlex path
    authors_json = get_authors_json(args.authors_path)
    authors = [(a["name"], a["id"]) for a in authors_json]
    if idx is not None:
        authors = authors[:idx]

    mailto = _get_mailto()
    from_year = int(__import__("time").strftime("%Y"))
    pubs: List[dict] = []
    for name, author_id in authors:
        openalex_id = find_author_id_by_name(name, mailto)
        if not openalex_id:
            continue
        works = fetch_works_for_author(openalex_id, from_year, mailto)
        # Upsert into DB; even if 0 works return
        upsert_publications(author_id, works)
        pubs.extend(works)
    return authors, pubs


def fetch_publications_by_id(
    author_id: str,
    output_folder: str = "./src",
    args=None,
    from_year: int = 2023,
    exclude_not_cited_papers: bool = False,
):
    if _backend() == "scholar":
        return fetch_scholar.fetch_publications_by_id(
            author_id,
            output_folder=output_folder,
            args=args,
            from_year=from_year,
            exclude_not_cited_papers=exclude_not_cited_papers,
        )

    # OpenAlex path
    mailto = _get_mailto()
    # We require author's name to find OpenAlex ID
    # Load from authors DB (same location as output_folder)
    from helper_funcs import _init_authors_db  # type: ignore

    conn = _init_authors_db(f"{output_folder}/authors.db")
    try:
        row = conn.execute("SELECT name FROM authors WHERE id=?", (author_id,)).fetchone()
    finally:
        conn.close()
    if not row:
        return []
    name = row[0]
    openalex_id = find_author_id_by_name(name, mailto)
    if not openalex_id:
        return []
    works = fetch_works_for_author(openalex_id, from_year, mailto)
    upsert_publications(author_id, works)
    # Optionally filter by citations if requested
    if exclude_not_cited_papers:
        works = [w for w in works if (w.get("num_citations") or 0) > 0]
    return works

