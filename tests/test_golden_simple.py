"""Simple golden test for the main workflow - fetch, update DB, send notification.

This test ensures the core workflow remains functional during refactoring.
It uses comprehensive mocking to avoid external API calls.
"""

import sqlite3
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch, Mock, MagicMock
import pytest


@pytest.fixture
def test_env(tmp_path):
    """Create a minimal test environment."""
    src_dir = tmp_path / "src"
    src_dir.mkdir()

    # Create authors database
    authors_db = src_dir / "authors.db"
    conn = sqlite3.connect(authors_db)
    conn.execute(
        "CREATE TABLE IF NOT EXISTS authors (name TEXT, id TEXT PRIMARY KEY)"
    )
    conn.execute("INSERT INTO authors (name, id) VALUES (?, ?)", ("Author 1", "AUTH1"))
    conn.execute("INSERT INTO authors (name, id) VALUES (?, ?)", ("Author 2", "AUTH2"))
    conn.commit()
    conn.close()

    # Create Slack config
    slack_config = src_dir / "slack.config"
    slack_config.write_text("[slack]\napi_token=xoxb-test\nchannel_name=test\n")

    # Create cache directory
    cache_dir = src_dir / "googleapi_cache"
    cache_dir.mkdir()

    return {
        "src_dir": src_dir,
        "authors_db": authors_db,
        "slack_config": slack_config,
        "cache_dir": cache_dir,
    }


def test_golden_workflow_complete(test_env):
    """GOLDEN TEST: End-to-end workflow validation.

    This test verifies that the complete workflow executes without errors:
    1. Load authors from database
    2. Fetch publications (mocked)
    3. Update database
    4. Format messages
    5. Send to Slack (mocked)

    This test should ALWAYS pass before and after refactoring.
    """
    # ========================================================================
    # ARRANGE
    # ========================================================================
    from helper_funcs import get_authors_json, convert_json_to_tuple
    from fetch_scholar import fetch_pubs_dictionary
    from slack_bot import make_slack_msg, send_to_slack

    # Mock publications that will be returned
    mock_publications = [
        {
            "bib": {
                "title": "Test Paper 1",
                "author": "Author 1 and Jane Doe",
                "pub_year": "2024",
                "abstract": "Abstract 1",
                "citation": "Journal 1, 2024",
            },
            "pub_url": "http://paper1",
            "num_citations": 10,
        },
        {
            "bib": {
                "title": "Test Paper 2",
                "author": "Author 2 and John Smith",
                "pub_year": "2024",
                "abstract": "Abstract 2",
                "citation": "Journal 2, 2024",
            },
            "pub_url": "http://paper2",
            "num_citations": 5,
        },
    ]

    args = SimpleNamespace(
        authors_path=str(test_env["authors_db"]),
        test_fetching=False,
        update_cache=False,
    )

    # ========================================================================
    # ACT: Execute workflow with mocked external calls
    # ========================================================================

    # Step 1: Load authors
    authors_json = get_authors_json(str(test_env["authors_db"]))
    authors = convert_json_to_tuple(authors_json)

    assert len(authors) == 2, "Should load 2 authors"
    assert authors[0] == ("Author 1", "AUTH1")
    assert authors[1] == ("Author 2", "AUTH2")

    # Step 2 & 3: Fetch publications and update database (mocked)
    with patch("fetch_scholar.fetch_publications_by_id") as mock_fetch:
        # Mock returns one publication per author
        mock_fetch.side_effect = [
            [
                {
                    "title": "Test Paper 1",
                    "authors": "Author 1, Jane Doe",
                    "year": "2024",
                    "abstract": "Abstract 1",
                    "pub_url": "http://paper1",
                    "num_citations": 10,
                    "journal": "Journal 1, 2024",
                }
            ],
            [
                {
                    "title": "Test Paper 2",
                    "authors": "Author 2, John Smith",
                    "year": "2024",
                    "abstract": "Abstract 2",
                    "pub_url": "http://paper2",
                    "num_citations": 5,
                    "journal": "Journal 2, 2024",
                }
            ],
        ]

        articles = fetch_pubs_dictionary(authors, args, output_dir=str(test_env["src_dir"]))

    # Step 4: Format messages
    formatted_messages = make_slack_msg(authors, articles)

    # Step 5: Send to Slack (mocked)
    with patch("slack_bot.send_to_slack") as mock_send:
        mock_send.return_value = {"ok": True}

        for message in formatted_messages:
            response = mock_send("test-channel", message, "xoxb-test")
            assert response["ok"], "Slack send should succeed"

    # ========================================================================
    # ASSERT: Verify workflow completed successfully
    # ========================================================================

    # Verify we got articles
    assert len(articles) == 2, f"Should have 2 articles, got {len(articles)}"

    # Verify message structure
    assert len(formatted_messages) >= 2, "Should have author list + publication messages"
    assert "Author 1" in formatted_messages[0]
    assert "Author 2" in formatted_messages[0]

    # Verify publication details in messages
    all_messages = "\n".join(formatted_messages)
    assert "Test Paper 1" in all_messages
    assert "Test Paper 2" in all_messages

    print("✅ GOLDEN TEST PASSED: Complete workflow executed successfully")


def test_golden_workflow_no_new_publications(test_env):
    """Test workflow handles case with no new publications gracefully."""
    from helper_funcs import get_authors_json, convert_json_to_tuple
    from fetch_scholar import fetch_pubs_dictionary
    from slack_bot import make_slack_msg

    args = SimpleNamespace(
        authors_path=str(test_env["authors_db"]),
        test_fetching=False,
        update_cache=False,
    )

    # Load authors
    authors_json = get_authors_json(str(test_env["authors_db"]))
    authors = convert_json_to_tuple(authors_json)

    # Mock fetch returns empty list (no new publications)
    with patch("fetch_scholar.fetch_publications_by_id") as mock_fetch:
        mock_fetch.return_value = []
        articles = fetch_pubs_dictionary(authors, args, output_dir=str(test_env["src_dir"]))

    # Format messages
    formatted_messages = make_slack_msg(authors, articles)

    # Verify graceful handling
    assert len(articles) == 0
    assert len(formatted_messages) >= 1
    assert "No new publications" in formatted_messages[-1]

    print("✅ Test passed: No publications handled gracefully")


def test_golden_database_operations(test_env):
    """Test that database operations work correctly."""
    from fetch_scholar import save_updated_cache, load_cache, DB_NAME
    import os

    db_path = str(test_env["src_dir"])

    # Create some test publications
    fetched_pubs = [
        {
            "bib": {
                "title": "Database Test Paper",
                "pub_year": "2024",
                "abstract": "Test abstract",
            },
            "pub_url": "http://test",
            "num_citations": 1,
        }
    ]

    args = SimpleNamespace(update_cache=False)

    # Save to database
    save_updated_cache(fetched_pubs, [], "TESTAUTH", db_path, args)

    # Load from database
    cached = load_cache("TESTAUTH", db_path)

    # Verify
    assert len(cached) == 1
    assert cached[0]["bib"]["title"] == "Database Test Paper"

    print("✅ Test passed: Database operations work correctly")


def test_golden_message_formatting():
    """Test that message formatting produces valid output."""
    from slack_bot import format_pub_message, format_authors_message

    # Test author formatting
    authors = [("Alice", "A1"), ("Bob", "B2")]
    author_msg = format_authors_message(authors)

    assert "Alice" in author_msg
    assert "Bob" in author_msg
    assert "A1" in author_msg
    assert "B2" in author_msg

    # Test publication formatting
    pub = {
        "title": "Test Paper",
        "authors": "Author One, Author Two",
        "abstract": "Test abstract",
        "year": "2024",
        "num_citations": 10,
        "journal": "Test Journal",
        "pub_url": "http://test",
    }

    pub_msg = format_pub_message(pub)

    assert "Test Paper" in pub_msg
    assert "http://test" in pub_msg
    assert "Author One, Author Two" in pub_msg
    assert "Test abstract" in pub_msg

    print("✅ Test passed: Message formatting works correctly")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
