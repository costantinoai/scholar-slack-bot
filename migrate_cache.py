#!/usr/bin/env python3
"""Migrate JSON caches to a SQLite database.

This script reads per-author JSON cache files and stores their contents
in a SQLite database using the ``publications`` schema.

Usage:
    python migrate_cache.py --json_dir /path/to/json_cache --db_dir /path/to/output
"""

import argparse
import json
import os
import sqlite3

DB_NAME = "publications.db"


def init_db(db_path: str) -> sqlite3.Connection:
    """Create the publications table if needed and return a connection."""
    conn = sqlite3.connect(db_path)
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
    return conn


def migrate(json_dir: str, db_dir: str) -> None:
    """Import every JSON cache file into the SQLite database.

    Args:
        json_dir: Directory containing ``<author_id>.json`` files.
        db_dir: Location where the SQLite database should reside.
    """
    db_path = os.path.join(db_dir, DB_NAME)
    conn = init_db(db_path)
    try:
        for fname in os.listdir(json_dir):
            if not fname.endswith(".json"):
                continue
            author_id = os.path.splitext(fname)[0]
            with open(os.path.join(json_dir, fname), "r") as f:
                pubs = json.load(f)
            for pub in pubs:
                title = pub["bib"]["title"]
                year = pub["bib"].get("pub_year")
                year_val = int(year) if year else None
                abstract = pub["bib"].get("abstract")
                url = pub.get("pub_url")
                citations = pub.get("num_citations")
                conn.execute(
                    "INSERT OR REPLACE INTO publications (author_id, title, year, abstract, url, citations) VALUES (?, ?, ?, ?, ?, ?)",
                    (author_id, title, year_val, abstract, url, citations),
                )
        conn.commit()
    finally:
        conn.close()


def main() -> None:
    """Parse arguments and perform the migration."""
    parser = argparse.ArgumentParser(description="Migrate JSON cache to SQLite.")
    parser.add_argument(
        "--json_dir", required=True, help="Directory with JSON cache files"
    )
    parser.add_argument("--db_dir", required=True, help="Directory for the SQLite DB")
    args = parser.parse_args()
    migrate(args.json_dir, args.db_dir)


if __name__ == "__main__":
    main()
