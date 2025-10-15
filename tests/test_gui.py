#!/usr/bin/env python3
"""Tests for gui.py - Flask web interface."""

import json
import sqlite3
import tempfile
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, Mock, patch

import pytest

# Import the Flask app and key functions from gui module
import gui
from gui import (
    _clear_cache,
    _load_settings,
    _load_slack_config,
    _refresh,
    _remove_author,
    _run_sql,
    _save_settings,
    _save_slack_config,
    app,
)


@pytest.fixture
def test_db():
    """Create temporary test databases."""
    with tempfile.TemporaryDirectory() as tmpdir:
        authors_db = Path(tmpdir) / "authors.db"
        publications_db = Path(tmpdir) / "publications.db"

        # Create authors table
        conn = sqlite3.connect(authors_db)
        conn.execute(
            "CREATE TABLE authors (name TEXT, id TEXT PRIMARY KEY)"
        )
        conn.execute("INSERT INTO authors VALUES (?, ?)", ("Test Author", "test123"))
        conn.commit()
        conn.close()

        # Create publications table
        conn = sqlite3.connect(publications_db)
        conn.execute(
            """
            CREATE TABLE publications (
                author_id TEXT,
                title TEXT,
                year INTEGER,
                url TEXT,
                citations INTEGER,
                PRIMARY KEY (author_id, title)
            )
            """
        )
        conn.execute(
            "INSERT INTO publications VALUES (?, ?, ?, ?, ?)",
            ("test123", "Test Paper", 2023, "http://example.com", 10),
        )
        conn.commit()
        conn.close()

        yield SimpleNamespace(
            authors_db=str(authors_db),
            publications_db=str(publications_db),
            tmpdir=tmpdir,
        )


@pytest.fixture
def client(test_db):
    """Create a test client for the Flask app."""
    # Patch the database paths
    with patch.object(gui, "AUTHORS_DB", Path(test_db.authors_db)), patch.object(
        gui, "PUBLICATIONS_DB", Path(test_db.publications_db)
    ):
        app.config["TESTING"] = True
        with app.test_client() as client:
            yield client


@pytest.fixture
def temp_settings_file():
    """Create a temporary settings file."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        settings = {
            "authors_db": "./test_authors.db",
            "publications_db": "./test_pubs.db",
            "slack_config_path": "./test_slack.config",
            "api_call_delay": "1.5",
        }
        json.dump(settings, f)
        temp_path = f.name

    yield Path(temp_path)
    # Cleanup
    Path(temp_path).unlink(missing_ok=True)


class TestSettings:
    """Tests for settings management functions."""

    def test_load_settings_defaults(self):
        """Test that _load_settings() returns defaults when file doesn't exist."""
        with patch.object(gui, "SETTINGS_FILE", Path("/nonexistent/settings.json")):
            settings = _load_settings()

        assert "authors_db" in settings
        assert "publications_db" in settings
        assert "slack_config_path" in settings
        assert "api_call_delay" in settings
        assert settings["authors_db"] == "./src/authors.db"

    def test_load_settings_from_file(self, temp_settings_file):
        """Test loading settings from an existing file."""
        with patch.object(gui, "SETTINGS_FILE", temp_settings_file):
            settings = _load_settings()

        assert settings["authors_db"] == "./test_authors.db"
        assert settings["api_call_delay"] == "1.5"

    def test_save_settings(self):
        """Test saving settings to file."""
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False
        ) as temp_file:
            temp_path = Path(temp_file.name)

        try:
            with patch.object(gui, "SETTINGS_FILE", temp_path):
                gui.settings = {
                    "authors_db": "./new_authors.db",
                    "publications_db": "./new_pubs.db",
                    "slack_config_path": "./new_slack.config",
                    "api_call_delay": "2.0",
                }
                _save_settings()

            # Verify file was written correctly
            with open(temp_path, "r") as f:
                saved = json.load(f)

            assert saved["authors_db"] == "./new_authors.db"
            assert saved["api_call_delay"] == "2.0"
        finally:
            temp_path.unlink(missing_ok=True)


class TestSlackConfig:
    """Tests for Slack configuration functions."""

    def test_load_slack_config_nonexistent(self):
        """Test loading Slack config when file doesn't exist."""
        with patch.object(gui, "settings", {"slack_config_path": "/nonexistent.config"}):
            config = _load_slack_config()

        # Should return defaults with empty strings
        assert config["api_token"] == ""
        assert config["channel_name"] == ""
        assert config["workspace"] == ""

    def test_load_slack_config_existing(self):
        """Test loading Slack config from existing file."""
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".config", delete=False
        ) as temp_file:
            temp_file.write("[slack]\n")
            temp_file.write("api_token = xoxb-test-token\n")
            temp_file.write("channel_name = test-channel\n")
            temp_file.write("workspace = test-workspace\n")
            temp_path = temp_file.name

        try:
            with patch.object(gui, "settings", {"slack_config_path": temp_path}):
                config = _load_slack_config()

            assert config["api_token"] == "xoxb-test-token"
            assert config["channel_name"] == "test-channel"
            assert config["workspace"] == "test-workspace"
        finally:
            Path(temp_path).unlink(missing_ok=True)

    def test_save_slack_config(self):
        """Test saving Slack config to file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "slack.config"

            with patch.object(
                gui, "settings", {"slack_config_path": str(config_path)}
            ), patch.object(
                gui,
                "slack_settings",
                {
                    "api_token": "xoxb-new-token",
                    "channel_name": "new-channel",
                    "workspace": "new-workspace",
                },
            ):
                _save_slack_config()

            # Verify file was created and contains correct values
            assert config_path.exists()
            import configparser

            cfg = configparser.ConfigParser()
            cfg.read(config_path)
            assert cfg["slack"]["api_token"] == "xoxb-new-token"
            assert cfg["slack"]["channel_name"] == "new-channel"


class TestSQLHelpers:
    """Tests for SQL helper functions."""

    def test_run_sql_creates_table(self, test_db):
        """Test that _run_sql() creates the publications table if needed."""
        # Use a fresh database
        temp_db = Path(test_db.tmpdir) / "fresh.db"

        with patch.object(gui, "PUBLICATIONS_DB", temp_db):
            _run_sql("SELECT 1")  # Dummy query

        # Verify table was created
        conn = sqlite3.connect(temp_db)
        cursor = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='publications'"
        )
        assert cursor.fetchone() is not None
        conn.close()

    def test_run_sql_executes_query(self, test_db):
        """Test that _run_sql() executes the provided query."""
        with patch.object(gui, "PUBLICATIONS_DB", Path(test_db.publications_db)):
            _run_sql(
                "INSERT INTO publications VALUES (?, ?, ?, ?, ?)",
                ("new_id", "New Paper", 2024, "http://new.com", 5),
            )

        # Verify insertion
        conn = sqlite3.connect(test_db.publications_db)
        cursor = conn.execute(
            "SELECT title FROM publications WHERE author_id=?", ("new_id",)
        )
        result = cursor.fetchone()
        conn.close()

        assert result is not None
        assert result[0] == "New Paper"

    def test_remove_author(self, test_db):
        """Test removing an author and their publications."""
        with patch.object(gui, "AUTHORS_DB", Path(test_db.authors_db)), patch.object(
            gui, "PUBLICATIONS_DB", Path(test_db.publications_db)
        ):
            _remove_author("test123")

        # Verify author was removed
        conn = sqlite3.connect(test_db.authors_db)
        cursor = conn.execute("SELECT * FROM authors WHERE id=?", ("test123",))
        assert cursor.fetchone() is None
        conn.close()

        # Verify publications were removed
        conn = sqlite3.connect(test_db.publications_db)
        cursor = conn.execute(
            "SELECT * FROM publications WHERE author_id=?", ("test123",)
        )
        assert cursor.fetchone() is None
        conn.close()

    def test_clear_cache_all(self, test_db):
        """Test clearing all cached publications."""
        with patch.object(gui, "PUBLICATIONS_DB", Path(test_db.publications_db)):
            _clear_cache()

        # Verify all publications were cleared
        conn = sqlite3.connect(test_db.publications_db)
        cursor = conn.execute("SELECT COUNT(*) FROM publications")
        count = cursor.fetchone()[0]
        conn.close()

        assert count == 0

    def test_clear_cache_specific_author(self, test_db):
        """Test clearing cache for a specific author."""
        # Add another author's publication first
        conn = sqlite3.connect(test_db.publications_db)
        conn.execute(
            "INSERT INTO publications VALUES (?, ?, ?, ?, ?)",
            ("other_id", "Other Paper", 2024, "http://other.com", 3),
        )
        conn.commit()
        conn.close()

        with patch.object(gui, "PUBLICATIONS_DB", Path(test_db.publications_db)):
            _clear_cache(author_id="test123")

        # Verify only test123's publications were cleared
        conn = sqlite3.connect(test_db.publications_db)
        cursor = conn.execute("SELECT COUNT(*) FROM publications")
        total_count = cursor.fetchone()[0]
        cursor = conn.execute(
            "SELECT COUNT(*) FROM publications WHERE author_id=?", ("other_id",)
        )
        other_count = cursor.fetchone()[0]
        conn.close()

        assert total_count == 1
        assert other_count == 1


class TestRefresh:
    """Tests for the _refresh() function."""

    @patch("gui.fetch_pubs_dictionary")
    def test_refresh_calls_fetch(self, mock_fetch, test_db):
        """Test that _refresh() calls fetch_pubs_dictionary."""
        authors = [("Test Author", "test123")]

        _refresh(authors)

        mock_fetch.assert_called_once()
        args = mock_fetch.call_args[0][1]  # Get the SimpleNamespace args
        assert args.update_cache is False
        assert args.test_fetching is False

    @patch("gui.fetch_pubs_dictionary")
    def test_refresh_with_multiple_authors(self, mock_fetch):
        """Test refreshing multiple authors."""
        authors = [("Author 1", "id1"), ("Author 2", "id2"), ("Author 3", "id3")]

        _refresh(authors)

        # Verify all authors were passed to fetch
        call_args = mock_fetch.call_args[0]
        assert call_args[0] == authors


class TestFlaskRoutes:
    """Tests for Flask route handlers."""

    def test_index_route(self, client, test_db):
        """Test the index page loads."""
        response = client.get("/")

        assert response.status_code == 200
        assert b"Scholar Slack Bot" in response.data
        assert b"Test Author" in response.data

    def test_add_author_route(self, client, test_db):
        """Test adding a new author."""
        with patch("gui.add_new_author_to_json") as mock_add:
            response = client.post(
                "/add-author", data={"scholar_id": "new_scholar_456"}
            )

            assert response.status_code == 302  # Redirect
            mock_add.assert_called_once()

    def test_add_bulk_route(self, client, test_db):
        """Test adding multiple authors in bulk."""
        with patch("gui.add_new_author_to_json") as mock_add:
            scholar_ids = "id1\nid2\nid3"
            response = client.post("/add-bulk", data={"scholar_ids": scholar_ids})

            assert response.status_code == 302
            assert mock_add.call_count == 3

    def test_remove_author_route(self, client, test_db):
        """Test removing an author."""
        response = client.post("/remove/test123")

        assert response.status_code == 302

        # Verify author was removed from database
        conn = sqlite3.connect(test_db.authors_db)
        cursor = conn.execute("SELECT * FROM authors WHERE id=?", ("test123",))
        assert cursor.fetchone() is None
        conn.close()

    @patch("gui._refresh")
    def test_refresh_author_route(self, mock_refresh, client, test_db):
        """Test refreshing a specific author."""
        response = client.post("/refresh/test123")

        assert response.status_code == 302
        mock_refresh.assert_called_once()
        # Verify the correct author tuple was passed
        authors = mock_refresh.call_args[0][0]
        assert len(authors) == 1
        assert authors[0][1] == "test123"

    @patch("gui._refresh")
    def test_refresh_all_route(self, mock_refresh, client, test_db):
        """Test refreshing all authors."""
        response = client.post("/refresh-all")

        assert response.status_code == 302
        mock_refresh.assert_called_once()

    def test_clear_cache_route(self, client, test_db):
        """Test clearing all cached publications."""
        response = client.post("/clear-cache")

        assert response.status_code == 302

        # Verify cache was cleared
        conn = sqlite3.connect(test_db.publications_db)
        cursor = conn.execute("SELECT COUNT(*) FROM publications")
        count = cursor.fetchone()[0]
        conn.close()
        assert count == 0

    def test_clear_author_cache_route(self, client, test_db):
        """Test clearing cache for a specific author."""
        response = client.post("/clear-cache/test123")

        assert response.status_code == 302

        # Verify author's cache was cleared
        conn = sqlite3.connect(test_db.publications_db)
        cursor = conn.execute(
            "SELECT COUNT(*) FROM publications WHERE author_id=?", ("test123",)
        )
        count = cursor.fetchone()[0]
        conn.close()
        assert count == 0

    def test_update_settings_route(self, client, test_db):
        """Test updating settings via the form."""
        with patch("gui._save_settings") as mock_save, patch(
            "gui._save_slack_config"
        ) as mock_save_slack:
            response = client.post(
                "/update-settings",
                data={
                    "authors_db": "./new_authors.db",
                    "slack_api_token": "new-token",
                },
            )

            assert response.status_code == 302
            mock_save.assert_called_once()
            mock_save_slack.assert_called_once()

    def test_publications_route(self, client, test_db):
        """Test viewing publications."""
        response = client.get("/publications")

        assert response.status_code == 200
        assert b"Cached Publications" in response.data
        assert b"Test Paper" in response.data

    def test_publications_route_with_filter(self, client, test_db):
        """Test viewing publications filtered by author."""
        response = client.get("/publications?author_id=test123")

        assert response.status_code == 200
        assert b"Test Paper" in response.data

    @patch("gui.run")
    def test_run_tests_route(self, mock_run, client, test_db):
        """Test running pytest from the GUI."""
        mock_result = Mock()
        mock_result.stdout = "test output"
        mock_result.stderr = ""
        mock_run.return_value = mock_result

        response = client.post("/run-tests")

        assert response.status_code == 200
        assert b"pytest" in response.data
        mock_run.assert_called_once()

    @patch("gui.run_workflow")
    def test_run_main_workflow_route_success(self, mock_workflow, client, test_db):
        """Test running the main workflow from the GUI."""
        mock_workflow.return_value = SimpleNamespace(
            test_arg="value", another_arg=123
        )

        response = client.post("/run-main-workflow")

        assert response.status_code == 200
        assert b"Main Workflow" in response.data
        assert b"executed successfully" in response.data
        mock_workflow.assert_called_once()

    @patch("gui.run_workflow")
    def test_run_main_workflow_route_failure(self, mock_workflow, client, test_db):
        """Test main workflow failure handling."""
        mock_workflow.side_effect = RuntimeError("Workflow failed!")

        response = client.post("/run-main-workflow")

        assert response.status_code == 200
        assert b"failed" in response.data


class TestIntegration:
    """Integration tests for the GUI."""

    def test_full_author_workflow(self, client, test_db):
        """Test adding, refreshing, and removing an author."""
        # Add author
        with patch("gui.add_new_author_to_json") as mock_add:
            mock_add.return_value = {"name": "New Author", "id": "new123"}
            response = client.post("/add-author", data={"scholar_id": "new123"})
            assert response.status_code == 302

        # Refresh author
        with patch("gui._refresh") as mock_refresh:
            response = client.post("/refresh/new123")
            assert response.status_code == 302

        # Remove author
        response = client.post("/remove/new123")
        assert response.status_code == 302

    def test_settings_persistence(self, client, test_db):
        """Test that settings are saved and reloaded correctly."""
        with tempfile.TemporaryDirectory() as tmpdir:
            settings_file = Path(tmpdir) / "settings.json"

            with patch.object(gui, "SETTINGS_FILE", settings_file):
                # Update settings
                gui.settings["authors_db"] = "./new_path.db"
                _save_settings()

                # Reload settings
                loaded = _load_settings()
                assert loaded["authors_db"] == "./new_path.db"
