"""Top-level package for the Scholar Slack bot.

The project is organised into subpackages to aid maintainability:

* :mod:`.scholar` – utilities for fetching publications from Google Scholar.
* :mod:`.workflow` – routines coordinating fetching and Slack messaging.
* :mod:`.slack` – helpers for interacting with the Slack API.
* :mod:`.ui` – optional web interface for managing authors and settings.
* :mod:`.utils` – helper functions and logging configuration.

Functional behaviour remains unchanged; modules have only been relocated for
clarity."""

__all__ = ["scholar", "workflow", "slack", "ui", "utils"]
