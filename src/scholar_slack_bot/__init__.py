"""Top-level package for the Scholar Slack bot.

The project is organised into subpackages to aid maintainability:

* :mod:`.core` – fetching publications and coordinating workflows.
* :mod:`.slack` – utilities for interacting with the Slack API.
* :mod:`.ui` – optional web interface for managing authors and settings.
* :mod:`.utils` – helper functions and logging configuration.

Functional behaviour remains unchanged; modules have only been relocated for
clarity."""

__all__ = ["core", "slack", "ui", "utils"]
