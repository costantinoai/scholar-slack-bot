"""Tests for scholar fetching utilities using the SQLite cache."""

import sqlite3
import json
import logging
from types import SimpleNamespace
from unittest.mock import patch

from scholar_slack_bot.core.fetcher import (
    load_cache,
    save_updated_cache,
    get_pubs_to_fetch,
    fetch_publications_by_id,
    fetch_pubs_dictionary,
)


def test_load_cache_reads_existing_file(tmp_path):
    """Existing database entries should be returned by ``load_cache``."""
    db = sqlite3.connect(tmp_path / "publications.db")
    db.execute(
        "CREATE TABLE publications (author_id TEXT, title TEXT, year INTEGER, abstract TEXT, url TEXT, citations INTEGER, PRIMARY KEY(author_id, title))"
    )
    db.execute(
        "INSERT INTO publications VALUES (?,?,?,?,?,?)",
        ("A1", "T", 2024, "abs", "u", 1),
    )
    db.commit()
    db.close()
    result = load_cache("A1", tmp_path)
    assert result == [
        {
            "bib": {"title": "T", "pub_year": "2024", "abstract": "abs"},
            "pub_url": "u",
            "num_citations": 1,
        }
    ]


def test_load_cache_returns_empty_for_missing(tmp_path):
    """When no cache exists, an empty list should be returned."""
    result = load_cache("missing", tmp_path)
    assert result == []


def test_migrate_legacy_files(tmp_path, caplog):
    """Legacy JSON files should be migrated automatically to SQLite."""
    cache_dir = tmp_path / "googleapi_cache"
    cache_dir.mkdir()
    legacy_pub = [
        {
            "bib": {"title": "T", "pub_year": "2024", "abstract": "abs"},
            "pub_url": "u",
            "num_citations": 1,
        }
    ]
    (cache_dir / "A1.json").write_text(json.dumps(legacy_pub))
    (tmp_path / "authors.json").write_text(json.dumps([{"name": "Author", "id": "A1"}]))
    (tmp_path / "googleapi_cache_bkp").mkdir()
    with caplog.at_level(logging.INFO):
        result = load_cache("A1", tmp_path)
    assert result == legacy_pub
    conn = sqlite3.connect(tmp_path / "authors.db")
    rows = list(conn.execute("SELECT name, id FROM authors"))
    conn.close()
    assert rows == [("Author", "A1")]
    obsolete = tmp_path / "obsolete"
    assert (obsolete / "googleapi_cache").exists()
    assert (obsolete / "authors.json").exists()
    assert (obsolete / "googleapi_cache_bkp").exists()
    assert "Legacy cache detected" in caplog.text


def test_save_updated_cache_combines_and_writes(tmp_path):
    """``save_updated_cache`` should insert new rows and optionally replace old ones."""
    # Pre-populate cache with an existing publication
    db = sqlite3.connect(tmp_path / "publications.db")
    db.execute(
        "CREATE TABLE publications (author_id TEXT, title TEXT, year INTEGER, abstract TEXT, url TEXT, citations INTEGER, PRIMARY KEY(author_id, title))"
    )
    db.execute(
        "INSERT INTO publications VALUES (?,?,?,?,?,?)",
        ("A1", "C", 2023, "a", "u1", 1),
    )
    db.commit()
    db.close()

    fetched = [
        {
            "bib": {"title": "F", "pub_year": "2024", "abstract": "b"},
            "pub_url": "u2",
            "num_citations": 2,
        }
    ]
    cached = []
    args = SimpleNamespace(update_cache=False)
    save_updated_cache(fetched, cached, "A1", tmp_path, args)
    db = sqlite3.connect(tmp_path / "publications.db")
    titles = {
        row[0]
        for row in db.execute("SELECT title FROM publications WHERE author_id='A1'")
    }
    assert titles == {"C", "F"}
    db.close()

    # Test update_cache=True replaces previous entries
    db = sqlite3.connect(tmp_path / "publications.db")
    db.execute(
        "INSERT OR REPLACE INTO publications VALUES (?,?,?,?,?,?)",
        ("A2", "C", 2023, "a", "u1", 1),
    )
    db.commit()
    db.close()
    args = SimpleNamespace(update_cache=True)
    save_updated_cache(fetched, cached, "A2", tmp_path, args)
    db = sqlite3.connect(tmp_path / "publications.db")
    titles = {
        row[0]
        for row in db.execute("SELECT title FROM publications WHERE author_id='A2'")
    }
    assert titles == {"F"}
    db.close()


def test_get_pubs_to_fetch_respects_test_fetching():
    """``get_pubs_to_fetch`` should honor the ``test_fetching`` flag."""
    author_pubs = [
        {"bib": {"title": "Old", "pub_year": "2023"}},
        {"bib": {"title": "New", "pub_year": "2024"}},
    ]
    cached_pubs = [
        {"bib": {"title": "Old", "pub_year": "2023"}},
        {"bib": {"title": "Recent", "pub_year": "2024"}},
    ]
    args = SimpleNamespace(test_fetching=True, update_cache=False)
    pubs = get_pubs_to_fetch(author_pubs, cached_pubs, 2024, args)
    assert pubs == [{"bib": {"title": "New", "pub_year": "2024"}}]


@patch("scholar_slack_bot.core.fetcher.save_updated_cache")
@patch(
    "scholar_slack_bot.core.fetcher.fetch_selected_pubs",
    return_value=[{"bib": {"title": "New", "pub_year": "2024"}}],
)
@patch(
    "scholar_slack_bot.core.fetcher.get_pubs_to_fetch",
    return_value=[{"bib": {"title": "New", "pub_year": "2024"}}],
)
@patch(
    "scholar_slack_bot.core.fetcher.load_cache",
    return_value=[{"bib": {"title": "Old", "pub_year": "2023"}}],
)
@patch(
    "scholar_slack_bot.core.fetcher.fetch_author_details",
    return_value=[
        {"bib": {"title": "Old", "pub_year": "2023"}},
        {"bib": {"title": "New", "pub_year": "2024"}},
    ],
)
@patch("scholar_slack_bot.core.fetcher.clean_pubs", return_value=["cleaned"])
def test_fetch_publications_by_id_calls_save(
    mock_clean, mock_fetch_author, mock_load, mock_get, mock_fetch, mock_save, tmp_path
):
    """Saving should occur when not in test mode."""
    args = SimpleNamespace(test_fetching=False, update_cache=False)
    result = fetch_publications_by_id("A1", str(tmp_path), args, from_year=2024)
    assert result == ["cleaned"]
    mock_save.assert_called_once()


@patch("scholar_slack_bot.core.fetcher.save_updated_cache")
@patch(
    "scholar_slack_bot.core.fetcher.fetch_selected_pubs",
    return_value=[{"bib": {"title": "New", "pub_year": "2024"}}],
)
@patch(
    "scholar_slack_bot.core.fetcher.get_pubs_to_fetch",
    return_value=[{"bib": {"title": "New", "pub_year": "2024"}}],
)
@patch(
    "scholar_slack_bot.core.fetcher.load_cache",
    return_value=[{"bib": {"title": "Old", "pub_year": "2023"}}],
)
@patch(
    "scholar_slack_bot.core.fetcher.fetch_author_details",
    return_value=[
        {"bib": {"title": "Old", "pub_year": "2023"}},
        {"bib": {"title": "New", "pub_year": "2024"}},
    ],
)
@patch("scholar_slack_bot.core.fetcher.clean_pubs", return_value=["cleaned"])
def test_fetch_publications_by_id_skips_save_with_test_fetching(
    mock_clean, mock_fetch_author, mock_load, mock_get, mock_fetch, mock_save, tmp_path
):
    """When ``test_fetching`` is True, the cache is not updated."""
    args = SimpleNamespace(test_fetching=True, update_cache=False)
    result = fetch_publications_by_id("A1", str(tmp_path), args, from_year=2024)
    assert result == ["cleaned"]
    mock_save.assert_not_called()


@patch(
    "scholar_slack_bot.core.fetcher.fetch_publications_by_id",
    side_effect=[[{"title": "A"}], [{"title": "B"}], [{"title": "C"}]],
)
def test_fetch_pubs_dictionary_limits_authors_with_test_fetching(mock_fetch, tmp_path):
    """Only the first two authors should be processed in test mode."""
    authors = [("A", "1"), ("B", "2"), ("C", "3")]
    args = SimpleNamespace(test_fetching=True)
    result = fetch_pubs_dictionary(authors, args, output_dir=str(tmp_path))
    assert mock_fetch.call_count == 2
    assert result == [{"title": "A"}, {"title": "B"}]
