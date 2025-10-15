"""Tests for per-author actions: refresh-cache and fetch-and-send.

These tests avoid external calls by mocking fetching and plugin sending.
"""

import os
import sqlite3
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest
from fastapi.testclient import TestClient

from src.api.app import app


@pytest.fixture
def temp_dbs(tmp_path, monkeypatch):
    authors_db = tmp_path / "authors.db"
    pubs_db = tmp_path / "publications.db"

    # Point API deps to temporary DBs
    monkeypatch.setenv("AUTHORS_DB_PATH", str(authors_db))
    monkeypatch.setenv("PUBLICATIONS_DB_PATH", str(pubs_db))

    # Initialize tables and seed one author
    conn = sqlite3.connect(authors_db)
    conn.execute("CREATE TABLE authors (name TEXT, id TEXT PRIMARY KEY)")
    conn.execute("INSERT INTO authors VALUES (?, ?)", ("Test Author", "test123"))
    conn.commit()
    conn.close()

    yield authors_db, pubs_db


def test_refresh_cache_author(temp_dbs):
    client = TestClient(app)

    with patch("src.api.routes.authors.fetch_publications_by_id") as mock_fetch:
        mock_fetch.return_value = [{"title": "A", "year": 2024}]
        res = client.post("/api/v1/authors/test123/refresh-cache")
        assert res.status_code == 200
        data = res.json()
        assert data["success"] is True
        assert data["author_id"] == "test123"
        assert data["count"] == 1


def test_fetch_and_send_author(temp_dbs, monkeypatch):
    # Configure plugin via env to avoid file reads
    monkeypatch.setenv("SLACK_API_TOKEN", "xoxb-test")
    monkeypatch.setenv("SLACK_DEFAULT_CHANNEL", "test")

    client = TestClient(app)

    with patch("src.api.routes.authors.fetch_publications_by_id") as mock_fetch, \
         patch("plugins.slack.plugin.requests.post") as mock_post, \
         patch("plugins.slack.plugin.requests.get") as mock_get:
        mock_fetch.return_value = [{
            "title": "A",
            "authors": "Auth",
            "year": 2024,
            "abstract": "Abs",
            "pub_url": "http://example.com",
            "journal": "J",
            "num_citations": 0,
        }]
        mock_get.return_value.json.return_value = {"ok": True}
        mock_post.return_value.json.return_value = {"ok": True}

        res = client.post("/api/v1/authors/test123/fetch-and-send")
        assert res.status_code == 200
        data = res.json()
        assert data["success"] is True
        assert data["sent_count"] == 1

