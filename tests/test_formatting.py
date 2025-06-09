import pytest
from scholar_slack_bot.slack_bot import format_authors_message, format_pub_message, make_slack_msg


def test_format_authors_message():
    authors = [("Alice", "id1"), ("Bob", "id2")]
    msg = format_authors_message(authors)
    assert "Alice" in msg and "Bob" in msg


def test_format_pub_message():
    pub = {
        "title": "Test Paper",
        "authors": "Alice, Bob",
        "abstract": "Something",
        "year": "2023",
        "num_citations": 0,
        "journal": "Test Journal",
        "pub_url": "http://example.com",
    }
    text = format_pub_message(pub)
    assert "Test Paper" in text


def test_make_slack_msg():
    authors = [("Alice", "id1")]
    articles = [
        {
            "title": "Test Paper",
            "authors": "Alice, Bob",
            "abstract": "Something",
            "year": "2023",
            "num_citations": 0,
            "journal": "Test Journal",
            "pub_url": "http://example.com",
        }
    ]
    msgs = make_slack_msg(authors, articles)
    assert len(msgs) > 1
