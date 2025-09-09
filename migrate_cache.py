#!/usr/bin/env python3
"""Migrate JSON caches and authors list to SQLite.

This utility converts existing per-author JSON cache files and the legacy
``authors.json`` into SQLite databases. After a successful migration, the
original files are moved into an ``obsolete`` folder for archival purposes.

Usage:
    python migrate_cache.py --root ./src [--backup_dir ./src/googleapi_cache_bkp]
"""

import argparse
import json
import os
import shutil
import sqlite3

DB_NAME = "publications.db"
AUTHORS_DB = "authors.db"


def init_pub_db(db_path: str) -> sqlite3.Connection:
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


def init_authors_db(db_path: str) -> sqlite3.Connection:
    """Create the authors table if needed and return a connection."""
    conn = sqlite3.connect(db_path)
    conn.execute(
        """CREATE TABLE IF NOT EXISTS authors (
                name TEXT,
                id TEXT PRIMARY KEY
            )"""
    )
    return conn


def migrate(root: str, backup_dir: str | None = None) -> None:
    """Perform the migration and archive legacy files.

    Args:
        root: Base directory containing ``authors.json`` and ``googleapi_cache``.
        backup_dir: Optional path to a legacy backup cache directory.
    """

    cache_dir = os.path.join(root, "googleapi_cache")
    # Store the new publications database directly under ``root`` so it remains
    # after the legacy cache folder is archived.
    pub_db_path = os.path.join(root, DB_NAME)
    conn = init_pub_db(pub_db_path)
    try:
        for fname in os.listdir(cache_dir):
            if not fname.endswith(".json"):
                continue
            author_id = os.path.splitext(fname)[0]
            with open(os.path.join(cache_dir, fname), "r") as f:
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

    authors_json = os.path.join(root, "authors.json")
    authors_db_path = os.path.join(root, AUTHORS_DB)
    if os.path.exists(authors_json):
        # Ensure the authors database resides in ``root`` before archiving
        a_conn = init_authors_db(authors_db_path)
        try:
            with open(authors_json, "r") as f:
                authors = json.load(f)
            for author in authors:
                a_conn.execute(
                    "INSERT OR REPLACE INTO authors (name, id) VALUES (?, ?)",
                    (author["name"], author["id"]),
                )
            a_conn.commit()
        finally:
            a_conn.close()

    obsolete_dir = os.path.join(root, "obsolete")
    os.makedirs(obsolete_dir, exist_ok=True)
    if os.path.exists(authors_json):
        shutil.move(authors_json, os.path.join(obsolete_dir, "authors.json"))
    if os.path.exists(cache_dir):
        shutil.move(cache_dir, os.path.join(obsolete_dir, "googleapi_cache"))
    if backup_dir:
        bkp = (
            backup_dir if os.path.isabs(backup_dir) else os.path.join(root, backup_dir)
        )
        if os.path.exists(bkp):
            shutil.move(bkp, os.path.join(obsolete_dir, os.path.basename(bkp)))


def main() -> None:
    """Parse arguments and perform the migration."""
    parser = argparse.ArgumentParser(description="Migrate JSON cache to SQLite.")
    parser.add_argument(
        "--root", default="./src", help="Root directory with authors and cache"
    )
    parser.add_argument(
        "--backup_dir",
        help="Optional path to a legacy backup cache directory",
        default=None,
    )
    args = parser.parse_args()
    migrate(args.root, args.backup_dir)


if __name__ == "__main__":
    main()
