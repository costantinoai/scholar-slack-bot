#!/usr/bin/env python3
"""Tests for streams_funcs.py - workflow orchestration functions."""

import os
import shutil
import tempfile
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, call, patch

import pytest

from streams_funcs import (
    add_scholar_and_fetch,
    refetch_and_update,
    regular_fetch_and_message,
    update_cache_only,
)

# Note: test_fetch_and_message is imported separately to avoid pytest
# collecting it as a test function (it's a source function, not a test)
from streams_funcs import test_fetch_and_message as _test_fetch_and_message


@pytest.fixture
def temp_cache_dirs():
    """Create temporary cache directories for testing."""
    with tempfile.TemporaryDirectory() as cache_dir, tempfile.TemporaryDirectory() as temp_cache_dir:
        yield SimpleNamespace(
            cache_path=cache_dir,
            temp_cache_path=temp_cache_dir,
        )


@pytest.fixture
def mock_args(temp_cache_dirs):
    """Create mock arguments for testing."""
    return SimpleNamespace(
        cache_path=temp_cache_dirs.cache_path,
        temp_cache_path=temp_cache_dirs.temp_cache_path,
        authors_path="./src/authors.db",
        add_scholar_id="test_scholar_123",
        update_cache=False,
        test_fetching=False,
    )


class TestUpdateCacheOnly:
    """Tests for update_cache_only() function."""

    @patch("streams_funcs.confirm_temp_cache")
    def test_update_cache_only_calls_confirm(self, mock_confirm, mock_args):
        """Test that update_cache_only() calls confirm_temp_cache."""
        # Arrange & Act
        update_cache_only(mock_args)

        # Assert
        mock_confirm.assert_called_once_with(
            mock_args.temp_cache_path, mock_args.cache_path
        )

    @patch("streams_funcs.confirm_temp_cache")
    @patch("streams_funcs.logger")
    def test_update_cache_only_logs_success(self, mock_logger, mock_confirm, mock_args):
        """Test that update_cache_only() logs success message."""
        # Arrange & Act
        update_cache_only(mock_args)

        # Assert
        mock_logger.info.assert_called_once()
        assert "successfully moved to cache" in mock_logger.info.call_args[0][0]


class TestTestFetchAndMessage:
    """Tests for test_fetch_and_message() function."""

    @patch("streams_funcs.fetch_from_json")
    @patch("streams_funcs.make_slack_msg")
    @patch("streams_funcs.send_to_slack")
    def test_test_fetch_and_message_basic_flow(
        self, mock_send, mock_make_msg, mock_fetch, mock_args
    ):
        """Test the basic flow of test_fetch_and_message()."""
        # Arrange
        mock_authors = [("Author 1", "id1"), ("Author 2", "id2")]
        mock_articles = {"id1": [], "id2": []}
        mock_fetch.return_value = (mock_authors, mock_articles)
        mock_make_msg.return_value = ["Message 1", "Message 2"]
        mock_send.return_value = {"ok": True}

        # Act
        _test_fetch_and_message(mock_args, "test-channel", "test-token", limit=2)

        # Assert
        mock_fetch.assert_called_once_with(mock_args, idx=2)
        mock_make_msg.assert_called_once_with(mock_authors, mock_articles)
        assert mock_send.call_count == 2

    @patch("streams_funcs.fetch_from_json")
    @patch("streams_funcs.make_slack_msg")
    @patch("streams_funcs.send_to_slack")
    def test_test_fetch_and_message_adds_test_header(
        self, mock_send, mock_make_msg, mock_fetch, mock_args
    ):
        """Test that test messages include the test header."""
        # Arrange
        mock_fetch.return_value = ([("Author", "id")], {"id": []})
        mock_make_msg.return_value = ["Original message"]
        mock_send.return_value = {"ok": True}

        # Act
        _test_fetch_and_message(mock_args, "test-channel", "test-token")

        # Assert
        sent_message = mock_send.call_args[0][1]
        assert "!!! This is a test message !!!" in sent_message
        assert "Original message" in sent_message

    @patch("streams_funcs.fetch_from_json")
    @patch("streams_funcs.make_slack_msg")
    @patch("streams_funcs.send_to_slack")
    @patch("streams_funcs.logger")
    def test_test_fetch_and_message_handles_failure(
        self, mock_logger, mock_send, mock_make_msg, mock_fetch, mock_args
    ):
        """Test that failures are logged correctly."""
        # Arrange
        mock_fetch.return_value = ([("Author", "id")], {"id": []})
        mock_make_msg.return_value = ["Message"]
        mock_send.return_value = {"ok": False, "error": "rate_limited"}

        # Act
        _test_fetch_and_message(mock_args, "test-channel", "test-token")

        # Assert
        mock_logger.warning.assert_called()
        assert "Failed to send" in mock_logger.warning.call_args[0][0]
        mock_logger.error.assert_called()

    @patch("streams_funcs.fetch_from_json")
    @patch("streams_funcs.make_slack_msg")
    @patch("streams_funcs.send_to_slack")
    def test_test_fetch_and_message_custom_limit(
        self, mock_send, mock_make_msg, mock_fetch, mock_args
    ):
        """Test that custom limit is respected."""
        # Arrange
        mock_fetch.return_value = ([], {})
        mock_make_msg.return_value = []
        mock_send.return_value = {"ok": True}

        # Act
        _test_fetch_and_message(mock_args, "test-channel", "test-token", limit=5)

        # Assert
        mock_fetch.assert_called_once_with(mock_args, idx=5)


class TestRegularFetchAndMessage:
    """Tests for regular_fetch_and_message() function."""

    @patch("streams_funcs.fetch_from_json")
    @patch("streams_funcs.make_slack_msg")
    @patch("streams_funcs.send_to_slack")
    @patch("streams_funcs.confirm_temp_cache")
    def test_regular_fetch_success(
        self, mock_confirm, mock_send, mock_make_msg, mock_fetch, mock_args
    ):
        """Test successful fetch and message workflow."""
        # Arrange
        mock_authors = [("Author 1", "id1")]
        mock_articles = {"id1": []}
        mock_fetch.return_value = (mock_authors, mock_articles)
        mock_make_msg.return_value = ["Message"]
        mock_send.return_value = {"ok": True}

        # Act
        regular_fetch_and_message(mock_args, "channel", "token")

        # Assert
        mock_fetch.assert_called_once_with(mock_args)
        mock_make_msg.assert_called_once_with(mock_authors, mock_articles)
        mock_send.assert_called_once()
        mock_confirm.assert_called_once_with(
            mock_args.temp_cache_path, mock_args.cache_path
        )

    @patch("streams_funcs.fetch_from_json")
    @patch("streams_funcs.make_slack_msg")
    @patch("streams_funcs.send_to_slack")
    @patch("streams_funcs.confirm_temp_cache")
    @patch("streams_funcs.logger")
    def test_regular_fetch_failure_no_cache_update(
        self, mock_logger, mock_confirm, mock_send, mock_make_msg, mock_fetch, mock_args
    ):
        """Test that cache is not updated on Slack failure."""
        # Arrange
        mock_fetch.return_value = ([("Author", "id")], {"id": []})
        mock_make_msg.return_value = ["Message"]
        mock_send.return_value = {"ok": False, "error": "invalid_auth"}

        # Act
        regular_fetch_and_message(mock_args, "channel", "token")

        # Assert
        # Cache should NOT be confirmed/updated
        mock_confirm.assert_not_called()
        # Error should be logged
        mock_logger.error.assert_called()
        assert "invalid_auth" in str(mock_logger.error.call_args)

    @patch("streams_funcs.fetch_from_json")
    @patch("streams_funcs.make_slack_msg")
    @patch("streams_funcs.send_to_slack")
    @patch("streams_funcs.confirm_temp_cache")
    def test_regular_fetch_multiple_messages(
        self, mock_confirm, mock_send, mock_make_msg, mock_fetch, mock_args
    ):
        """Test sending multiple messages."""
        # Arrange
        mock_fetch.return_value = ([("A1", "id1"), ("A2", "id2")], {"id1": [], "id2": []})
        mock_make_msg.return_value = ["Message 1", "Message 2", "Message 3"]
        mock_send.return_value = {"ok": True}

        # Act
        regular_fetch_and_message(mock_args, "channel", "token")

        # Assert
        assert mock_send.call_count == 3
        # All succeeded, so cache should be updated
        mock_confirm.assert_called_once()

    @patch("streams_funcs.fetch_from_json")
    @patch("streams_funcs.make_slack_msg")
    @patch("streams_funcs.send_to_slack")
    @patch("streams_funcs.confirm_temp_cache")
    def test_regular_fetch_partial_failure(
        self, mock_confirm, mock_send, mock_make_msg, mock_fetch, mock_args
    ):
        """Test that one failure prevents cache update."""
        # Arrange
        mock_fetch.return_value = ([("A", "id")], {"id": []})
        mock_make_msg.return_value = ["Msg1", "Msg2", "Msg3"]
        # First two succeed, third fails
        mock_send.side_effect = [
            {"ok": True},
            {"ok": True},
            {"ok": False, "error": "network_error"},
        ]

        # Act
        regular_fetch_and_message(mock_args, "channel", "token")

        # Assert
        # Cache should NOT be updated
        mock_confirm.assert_not_called()


class TestRefetchAndUpdate:
    """Tests for refetch_and_update() function."""

    @patch("streams_funcs.fetch_from_json")
    @patch("streams_funcs.update_cache_only")
    @patch("shutil.rmtree")
    @patch("os.path.isdir")
    def test_refetch_deletes_old_cache(
        self, mock_isdir, mock_rmtree, mock_update, mock_fetch, mock_args
    ):
        """Test that old cache is deleted."""
        # Arrange
        mock_isdir.return_value = True
        mock_fetch.return_value = ([], {})

        # Act
        refetch_and_update(mock_args)

        # Assert
        mock_rmtree.assert_called_once_with(mock_args.cache_path)

    @patch("streams_funcs.fetch_from_json")
    @patch("streams_funcs.update_cache_only")
    @patch("shutil.rmtree")
    @patch("os.path.isdir")
    def test_refetch_fetches_all_authors(
        self, mock_isdir, mock_rmtree, mock_update, mock_fetch, mock_args
    ):
        """Test that all authors are fetched."""
        # Arrange
        mock_isdir.return_value = True
        mock_fetch.return_value = ([], {})

        # Act
        refetch_and_update(mock_args)

        # Assert
        mock_fetch.assert_called_once_with(mock_args)

    @patch("streams_funcs.fetch_from_json")
    @patch("streams_funcs.update_cache_only")
    @patch("shutil.rmtree")
    @patch("os.path.isdir")
    def test_refetch_updates_cache(
        self, mock_isdir, mock_rmtree, mock_update, mock_fetch, mock_args
    ):
        """Test that cache is updated after refetch."""
        # Arrange
        mock_isdir.return_value = True
        mock_fetch.return_value = ([], {})

        # Act
        refetch_and_update(mock_args)

        # Assert
        mock_update.assert_called_once_with(mock_args)

    @patch("streams_funcs.fetch_from_json")
    @patch("streams_funcs.update_cache_only")
    @patch("shutil.rmtree")
    @patch("os.path.isdir")
    @patch("streams_funcs.logger")
    def test_refetch_handles_delete_error(
        self, mock_logger, mock_isdir, mock_rmtree, mock_update, mock_fetch, mock_args
    ):
        """Test that delete errors are logged but don't stop the workflow."""
        # Arrange
        mock_isdir.return_value = True
        mock_rmtree.side_effect = PermissionError("Access denied")
        mock_fetch.return_value = ([], {})

        # Act
        refetch_and_update(mock_args)

        # Assert
        mock_logger.error.assert_called()
        # Workflow should continue
        mock_fetch.assert_called_once()
        mock_update.assert_called_once()

    @patch("streams_funcs.fetch_from_json")
    @patch("streams_funcs.update_cache_only")
    @patch("shutil.rmtree")
    @patch("os.path.isdir")
    def test_refetch_skips_delete_if_no_temp_dir(
        self, mock_isdir, mock_rmtree, mock_update, mock_fetch, mock_args
    ):
        """Test that delete is skipped if temp directory doesn't exist."""
        # Arrange
        mock_isdir.return_value = False
        mock_fetch.return_value = ([], {})

        # Act
        refetch_and_update(mock_args)

        # Assert
        # Should not try to delete
        mock_rmtree.assert_not_called()
        # But should still fetch and update
        mock_fetch.assert_called_once()
        mock_update.assert_called_once()


class TestAddScholarAndFetch:
    """Tests for add_scholar_and_fetch() function."""

    @patch("streams_funcs.add_new_author_to_json")
    @patch("streams_funcs.convert_json_to_tuple")
    @patch("streams_funcs.fetch_pubs_dictionary")
    @patch("streams_funcs.update_cache_only")
    @patch("os.path.exists")
    def test_add_scholar_basic_flow(
        self,
        mock_exists,
        mock_update,
        mock_fetch_pubs,
        mock_convert,
        mock_add_author,
        mock_args,
    ):
        """Test the basic flow of adding a new scholar."""
        # Arrange
        mock_exists.return_value = False  # Scholar not cached yet
        mock_author_dict = {"name": "Test Author", "id": "test_scholar_123"}
        mock_add_author.return_value = mock_author_dict
        mock_convert.return_value = [("Test Author", "test_scholar_123")]
        mock_fetch_pubs.return_value = []

        # Act
        add_scholar_and_fetch(mock_args)

        # Assert
        mock_add_author.assert_called_once_with(
            mock_args.authors_path, mock_args.add_scholar_id
        )
        mock_convert.assert_called_once_with([mock_author_dict])
        mock_fetch_pubs.assert_called_once()
        mock_update.assert_called_once_with(mock_args)

    @patch("streams_funcs.add_new_author_to_json")
    @patch("os.path.exists")
    @patch("streams_funcs.logger")
    def test_add_scholar_skips_if_already_cached(
        self, mock_logger, mock_exists, mock_add_author, mock_args
    ):
        """Test that adding is skipped if scholar already has cached pubs."""
        # Arrange
        mock_exists.return_value = True  # Scholar already cached

        # Act
        add_scholar_and_fetch(mock_args)

        # Assert
        # Should not try to add or fetch
        mock_add_author.assert_not_called()
        # Should log info message
        mock_logger.info.assert_called()
        assert "already has cached publications" in mock_logger.info.call_args[0][0]

    @patch("streams_funcs.add_new_author_to_json")
    @patch("streams_funcs.convert_json_to_tuple")
    @patch("streams_funcs.fetch_pubs_dictionary")
    @patch("streams_funcs.update_cache_only")
    @patch("os.path.exists")
    @patch("streams_funcs.logger")
    def test_add_scholar_logs_progress(
        self,
        mock_logger,
        mock_exists,
        mock_update,
        mock_fetch_pubs,
        mock_convert,
        mock_add_author,
        mock_args,
    ):
        """Test that progress is logged at each step."""
        # Arrange
        mock_exists.return_value = False
        mock_add_author.return_value = {"name": "Test", "id": "123"}
        mock_convert.return_value = [("Test", "123")]
        mock_fetch_pubs.return_value = [{"title": "Paper 1"}, {"title": "Paper 2"}]

        # Act
        add_scholar_and_fetch(mock_args)

        # Assert
        # Should have multiple log calls
        assert mock_logger.debug.call_count >= 2
        assert mock_logger.info.call_count >= 2
        # Check for specific log messages
        log_messages = [call[0][0] for call in mock_logger.info.call_args_list]
        assert any("Fetched" in msg for msg in log_messages)
        assert any("Cache successfully updated" in msg for msg in log_messages)

    @patch("streams_funcs.add_new_author_to_json")
    @patch("streams_funcs.convert_json_to_tuple")
    @patch("streams_funcs.fetch_pubs_dictionary")
    @patch("streams_funcs.update_cache_only")
    @patch("os.path.exists")
    def test_add_scholar_constructs_correct_filepath(
        self,
        mock_exists,
        mock_update,
        mock_fetch_pubs,
        mock_convert,
        mock_add_author,
        mock_args,
    ):
        """Test that the correct JSON filepath is constructed for existence check."""
        # Arrange
        mock_exists.return_value = False
        mock_add_author.return_value = {"name": "Test", "id": "test_scholar_123"}
        mock_convert.return_value = [("Test", "test_scholar_123")]
        mock_fetch_pubs.return_value = []

        # Act
        add_scholar_and_fetch(mock_args)

        # Assert
        # Check that os.path.exists was called with the correct path
        expected_path = os.path.join(
            mock_args.cache_path, f"{mock_args.add_scholar_id}.json"
        )
        mock_exists.assert_called_once_with(expected_path)
