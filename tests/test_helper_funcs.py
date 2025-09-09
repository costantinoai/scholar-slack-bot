from types import SimpleNamespace
from unittest.mock import patch
import sqlite3

from helper_funcs import (
    add_new_author_to_json,
    clean_pubs,
    convert_json_to_tuple,
    ensure_output_folder,
    has_conflicting_args,
    confirm_temp_cache,
)


def test_clean_pubs_filters_duplicates_and_citations():
    fetched = [
        {
            "bib": {
                "pub_year": "2023",
                "title": "Paper A",
                "author": "Alice",
                "abstract": "A",
                "citation": "Journal A",
            },
            "num_citations": 5,
            "pub_url": "http://a",
        },
        {
            "bib": {
                "pub_year": "2024",
                "title": "Paper B",
                "author": "Bob",
                "abstract": "B",
                "citation": "Journal B",
            },
            "num_citations": 10,
            "pub_url": "http://b",
        },
        {
            "bib": {
                "pub_year": "2023",
                "title": "Paper A",
                "author": "Alice",
                "abstract": "A",
                "citation": "Journal A",
            },
            "num_citations": 5,
            "pub_url": "http://a2",
        },
        {
            "bib": {
                "pub_year": "2022",
                "title": "Paper C",
                "author": "Carol",
                "abstract": "C",
                "citation": "Journal C",
            },
            "num_citations": 0,
            "pub_url": "http://c",
        },
    ]

    result = clean_pubs(fetched, from_year=2023, exclude_not_cited_papers=True)

    assert result == [
        {
            "title": "Paper A",
            "authors": "Alice",
            "abstract": "A",
            "year": "2023",
            "num_citations": 5,
            "journal": "Journal A",
            "pub_url": "http://a",
        }
    ]


def test_convert_json_to_tuple():
    authors_json = [{"name": "Alice", "id": "A1"}, {"name": "Bob", "id": "B2"}]
    assert convert_json_to_tuple(authors_json) == [("Alice", "A1"), ("Bob", "B2")]


def test_has_conflicting_args_detects_conflict():
    args = SimpleNamespace(
        test_message=True,
        add_scholar_id=True,
        update_cache=False,
    )
    assert has_conflicting_args(args)


def test_has_conflicting_args_no_conflict():
    args = SimpleNamespace(
        test_message=True,
        add_scholar_id=False,
        update_cache=False,
    )
    assert not has_conflicting_args(args)


def test_ensure_output_folder_creates(tmp_path):
    folder = tmp_path / "out"
    ensure_output_folder(folder)
    assert folder.exists()


@patch("helper_funcs.scholarly")
def test_add_new_author_to_json(mock_scholarly, tmp_path):
    authors_path = tmp_path / "authors.db"
    mock_scholarly.search_author_id.return_value = {"name": "New"}
    added = add_new_author_to_json(str(authors_path), "N1")
    conn = sqlite3.connect(authors_path)
    rows = set(conn.execute("SELECT name, id FROM authors"))
    conn.close()
    assert added == {"name": "New", "id": "N1"}
    assert ("New", "N1") in rows


def test_confirm_temp_cache_moves_files(tmp_path):
    temp_dir = tmp_path / "tmp"
    cache_dir = tmp_path / "cache"
    temp_dir.mkdir()
    (temp_dir / "file.json").write_text("data")

    confirm_temp_cache(str(temp_dir), str(cache_dir))

    assert (cache_dir / "file.json").exists()
    assert not temp_dir.exists()
