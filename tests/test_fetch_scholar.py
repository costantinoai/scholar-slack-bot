import json
from types import SimpleNamespace
from unittest.mock import patch

from fetch_scholar import (
    load_cache,
    save_updated_cache,
    get_pubs_to_fetch,
    fetch_publications_by_id,
    fetch_pubs_dictionary,
)


def test_load_cache_reads_existing_file(tmp_path):
    data = [{"bib": {"title": "T"}}]
    (tmp_path / "A1.json").write_text(json.dumps(data))
    result = load_cache("A1", tmp_path)
    assert result == data


def test_load_cache_returns_empty_for_missing(tmp_path):
    result = load_cache("missing", tmp_path)
    assert result == []


def test_save_updated_cache_combines_and_writes(tmp_path):
    fetched = [{"bib": {"title": "F"}}]
    cached = [{"bib": {"title": "C"}}]
    args = SimpleNamespace(update_cache=False)
    save_updated_cache(fetched, cached, "A1", tmp_path, args)
    content = json.loads((tmp_path / "A1.json").read_text())
    assert content == fetched + cached

    args = SimpleNamespace(update_cache=True)
    save_updated_cache(fetched, cached, "A2", tmp_path, args)
    content = json.loads((tmp_path / "A2.json").read_text())
    assert content == fetched


def test_get_pubs_to_fetch_respects_test_fetching():
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


@patch("fetch_scholar.save_updated_cache")
@patch(
    "fetch_scholar.fetch_selected_pubs",
    return_value=[{"bib": {"title": "New", "pub_year": "2024"}}],
)
@patch(
    "fetch_scholar.get_pubs_to_fetch",
    return_value=[{"bib": {"title": "New", "pub_year": "2024"}}],
)
@patch(
    "fetch_scholar.load_cache",
    return_value=[{"bib": {"title": "Old", "pub_year": "2023"}}],
)
@patch(
    "fetch_scholar.fetch_author_details",
    return_value=[
        {"bib": {"title": "Old", "pub_year": "2023"}},
        {"bib": {"title": "New", "pub_year": "2024"}},
    ],
)
@patch("fetch_scholar.clean_pubs", return_value=["cleaned"])
def test_fetch_publications_by_id_calls_save(mock_clean, mock_fetch_author, mock_load, mock_get, mock_fetch, mock_save, tmp_path):
    args = SimpleNamespace(test_fetching=False, update_cache=False)
    result = fetch_publications_by_id("A1", str(tmp_path), args, from_year=2024)
    assert result == ["cleaned"]
    mock_save.assert_called_once()


@patch("fetch_scholar.save_updated_cache")
@patch(
    "fetch_scholar.fetch_selected_pubs",
    return_value=[{"bib": {"title": "New", "pub_year": "2024"}}],
)
@patch(
    "fetch_scholar.get_pubs_to_fetch",
    return_value=[{"bib": {"title": "New", "pub_year": "2024"}}],
)
@patch(
    "fetch_scholar.load_cache",
    return_value=[{"bib": {"title": "Old", "pub_year": "2023"}}],
)
@patch(
    "fetch_scholar.fetch_author_details",
    return_value=[
        {"bib": {"title": "Old", "pub_year": "2023"}},
        {"bib": {"title": "New", "pub_year": "2024"}},
    ],
)
@patch("fetch_scholar.clean_pubs", return_value=["cleaned"])
def test_fetch_publications_by_id_skips_save_with_test_fetching(mock_clean, mock_fetch_author, mock_load, mock_get, mock_fetch, mock_save, tmp_path):
    args = SimpleNamespace(test_fetching=True, update_cache=False)
    result = fetch_publications_by_id("A1", str(tmp_path), args, from_year=2024)
    assert result == ["cleaned"]
    mock_save.assert_not_called()


@patch(
    "fetch_scholar.fetch_publications_by_id",
    side_effect=[[{"title": "A"}], [{"title": "B"}], [{"title": "C"}]],
)
def test_fetch_pubs_dictionary_limits_authors_with_test_fetching(mock_fetch, tmp_path):
    authors = [("A", "1"), ("B", "2"), ("C", "3")]
    args = SimpleNamespace(test_fetching=True)
    result = fetch_pubs_dictionary(authors, args, output_dir=str(tmp_path))
    assert mock_fetch.call_count == 2
    assert result == [{"title": "A"}, {"title": "B"}]
