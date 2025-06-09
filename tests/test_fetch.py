import json
from types import SimpleNamespace

import pytest

from scholar_slack_bot import fetch_scholar as fs
from scholar_slack_bot import helper_funcs as hf


def test_get_pubs_to_fetch_filters():
    args = SimpleNamespace(test_fetching=False, update_cache=False)
    author_pubs = [
        {"bib": {"title": "A", "pub_year": "2024"}},
        {"bib": {"title": "B", "pub_year": "2024"}},
    ]
    cached_pubs = [{"bib": {"title": "A", "pub_year": "2024"}}]
    pubs = fs.get_pubs_to_fetch(author_pubs, cached_pubs, 2023, args)
    assert [p["bib"]["title"] for p in pubs] == ["B"]


def test_get_pubs_to_fetch_update_cache():
    args = SimpleNamespace(test_fetching=False, update_cache=True)
    author_pubs = [
        {"bib": {"title": "A", "pub_year": "2024"}},
        {"bib": {"title": "B", "pub_year": "2024"}},
        {"bib": {"title": "C", "pub_year": "2022"}},
    ]
    cached_pubs = [{"bib": {"title": "A", "pub_year": "2024"}}]
    pubs = fs.get_pubs_to_fetch(author_pubs, cached_pubs, 2023, args)
    assert [p["bib"]["title"] for p in pubs] == ["A", "B"]


def test_clean_pubs_deduplicate():
    fetched = [
        {"bib": {"title": "T1", "author": "A and B", "abstract": "Abs1", "pub_year": "2023", "citation": "J"}, "num_citations": 1, "pub_url": "u"},
        {"bib": {"title": "T1", "author": "A and B", "abstract": "Abs1", "pub_year": "2023", "citation": "J"}, "num_citations": 0, "pub_url": "u"},
        {"bib": {"title": "T2", "author": "A and B", "abstract": "Abs2", "pub_year": "2022", "citation": "J"}, "num_citations": 0, "pub_url": "u"},
    ]
    cleaned = hf.clean_pubs(fetched, 2023, exclude_not_cited_papers=True)
    assert len(cleaned) == 1
    assert cleaned[0]["title"] == "T1"


def test_fetch_selected_pubs_success(monkeypatch):
    results = []
    def fake_fetch(x):
        results.append(x)
        return x
    monkeypatch.setattr(fs, "fetch_publication_details", fake_fetch)
    pubs = fs.fetch_selected_pubs([1, 2, 3])
    assert pubs == [1, 2, 3]
    assert results == [1, 2, 3]


def test_fetch_selected_pubs_retry(monkeypatch):
    def fail(pub):
        raise RuntimeError('boom')
    monkeypatch.setattr(fs, 'fetch_publication_details', fail)
    monkeypatch.setattr(fs, 'DELAYS', [0,0,0])
    monkeypatch.setattr(fs.time, 'sleep', lambda x: None)
    pubs = fs.fetch_selected_pubs([1])
    assert pubs == []


def test_fetch_pubs_dictionary_subset(tmp_path, monkeypatch):
    called = []
    def fake_fetch(author_id, output_folder, args, from_year=2023, exclude_not_cited_papers=False):
        called.append(author_id)
        return [{"bib": {"title": author_id, "author": "A", "abstract": "", "pub_year": "2023", "citation": "J"}, "num_citations": 0, "pub_url": "u"}]
    monkeypatch.setattr(fs, 'fetch_publications_by_id', fake_fetch)
    monkeypatch.setattr(fs.time, 'strftime', lambda x: '2023')
    args = SimpleNamespace(test_fetching=True)
    authors = [('A','id1'),('B','id2'),('C','id3')]
    pubs = fs.fetch_pubs_dictionary(authors, args, output_dir=tmp_path)
    assert called == ['id1','id2']
    assert len(pubs) == 2


def test_add_new_author_to_json(tmp_path, monkeypatch):
    f = tmp_path/'authors.json'
    json.dump([{"name":"Old","id":"old"}], f.open('w'))
    hf.scholarly = SimpleNamespace(search_author_id=lambda x: {"name": "New"})
    hf.add_new_author_to_json(str(f), 'new')
    data = json.load(f.open())
    assert any(a['id']=='new' for a in data)


def test_get_authors_json(tmp_path):
    p = tmp_path/'a.json'
    authors = [{"name":"A","id":"1"}]
    p.write_text(json.dumps(authors))
    assert hf.get_authors_json(str(p)) == authors


def test_confirm_temp_cache(tmp_path):
    temp_dir = tmp_path/'tmp'
    old_dir = tmp_path/'cache'
    temp_dir.mkdir(); old_dir.mkdir()
    (temp_dir/'f.txt').write_text('hi')
    hf.confirm_temp_cache(str(temp_dir), str(old_dir))
    assert not temp_dir.exists()
    assert (old_dir/'f.txt').exists()
