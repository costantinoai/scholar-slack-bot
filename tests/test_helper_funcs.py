import pytest
from helper_funcs import clean_pubs


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
