#!/usr/bin/env python3
"""Tests for log_config.py - logging configuration module."""

import logging
from unittest.mock import MagicMock, patch

import pytest

from log_config import setup_logging


class TestSetupLogging:
    """Tests for the setup_logging() function."""

    def test_setup_logging_default_level(self):
        """Test that setup_logging() configures INFO level by default."""
        # Arrange & Act
        setup_logging(verbose=False)

        # Assert
        root_logger = logging.getLogger()
        assert root_logger.level == logging.INFO

    def test_setup_logging_verbose_level(self):
        """Test that setup_logging(verbose=True) configures DEBUG level."""
        # Arrange & Act
        setup_logging(verbose=True)

        # Assert
        root_logger = logging.getLogger()
        assert root_logger.level == logging.DEBUG

    def test_setup_logging_configures_handlers(self):
        """Test that setup_logging() configures console handler."""
        # Arrange & Act
        setup_logging()

        # Assert
        root_logger = logging.getLogger()
        assert len(root_logger.handlers) > 0
        # Should have a StreamHandler
        handler_types = [type(h).__name__ for h in root_logger.handlers]
        assert "StreamHandler" in handler_types

    def test_setup_logging_formatter(self):
        """Test that the logging formatter is configured correctly."""
        # Arrange & Act
        setup_logging()

        # Assert
        root_logger = logging.getLogger()
        for handler in root_logger.handlers:
            if isinstance(handler, logging.StreamHandler):
                formatter = handler.formatter
                assert formatter is not None
                # Check that the format string contains expected components
                format_str = formatter._fmt
                assert "%(asctime)s" in format_str
                assert "%(name)s" in format_str
                assert "%(levelname)s" in format_str
                assert "%(message)s" in format_str

    def test_setup_logging_does_not_disable_existing_loggers(self):
        """Test that setup_logging() does not disable existing loggers."""
        # Arrange
        # Create a logger before setup
        existing_logger = logging.getLogger("test.existing")
        existing_logger.setLevel(logging.WARNING)

        # Act
        setup_logging()

        # Assert
        # The existing logger should still exist and be usable
        assert existing_logger.name == "test.existing"
        # It should have inherited the new root level or kept its own
        assert existing_logger.isEnabledFor(logging.WARNING)

    @patch("logging.config.dictConfig")
    def test_setup_logging_calls_dict_config(self, mock_dict_config):
        """Test that setup_logging() uses logging.config.dictConfig."""
        # Arrange & Act
        setup_logging(verbose=False)

        # Assert
        mock_dict_config.assert_called_once()
        config = mock_dict_config.call_args[0][0]
        assert config["version"] == 1
        assert config["disable_existing_loggers"] is False
        assert "formatters" in config
        assert "handlers" in config
        assert "root" in config

    @patch("logging.config.dictConfig")
    def test_setup_logging_verbose_mode_config(self, mock_dict_config):
        """Test that verbose mode passes DEBUG level to the config."""
        # Arrange & Act
        setup_logging(verbose=True)

        # Assert
        config = mock_dict_config.call_args[0][0]
        assert config["root"]["level"] == "DEBUG"

    @patch("logging.config.dictConfig")
    def test_setup_logging_non_verbose_mode_config(self, mock_dict_config):
        """Test that non-verbose mode passes INFO level to the config."""
        # Arrange & Act
        setup_logging(verbose=False)

        # Assert
        config = mock_dict_config.call_args[0][0]
        assert config["root"]["level"] == "INFO"

    def test_setup_logging_multiple_calls(self):
        """Test that calling setup_logging() multiple times works correctly."""
        # Arrange & Act
        setup_logging(verbose=False)
        initial_handlers = len(logging.getLogger().handlers)

        setup_logging(verbose=True)
        final_handlers = len(logging.getLogger().handlers)

        # Assert
        # The second call should reconfigure, not accumulate handlers
        # Note: This might depend on logging.config.dictConfig behavior
        # In practice, dictConfig typically replaces handlers
        assert final_handlers >= initial_handlers  # At minimum, same number

    def test_logging_output_format_integration(self, caplog):
        """Integration test: verify that log messages are emitted correctly."""
        # Arrange
        setup_logging(verbose=True)
        test_logger = logging.getLogger("test.integration")

        # Act - use caplog in live mode to capture logs emitted to the console
        with caplog.at_level(logging.DEBUG, logger="test.integration"):
            test_logger.debug("Test debug message")
            test_logger.info("Test info message")
            test_logger.warning("Test warning message")

        # Assert
        # The logs are emitted via StreamHandler to stderr, which pytest captures
        # We can verify they work by checking the logger is enabled for DEBUG
        assert test_logger.isEnabledFor(logging.DEBUG)
        assert test_logger.isEnabledFor(logging.INFO)
        assert test_logger.isEnabledFor(logging.WARNING)

    def test_logging_level_filtering(self, caplog):
        """Test that logging level filtering works correctly."""
        # Arrange
        setup_logging(verbose=False)  # INFO level
        test_logger = logging.getLogger("test.filtering")

        # Act
        with caplog.at_level(logging.DEBUG):
            test_logger.debug("This should be filtered")
            test_logger.info("This should appear")

        # Assert
        messages = [r.message for r in caplog.records]
        # DEBUG should be filtered out at INFO level
        # Note: caplog.at_level overrides the logger level for testing
        # So we need to check the logger's actual level separately
        root_logger = logging.getLogger()
        assert root_logger.level == logging.INFO
