#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Sat Oct  7 02:46:59 2023

@author: costantino_ai
"""

import os
import argparse
import logging
import shutil

from slack_bot import get_slack_config, send_test_msg
from helper_funcs import delete_temp_cache
from streams_funcs import (
    refetch_and_update,
    add_scholar_and_fetch,
    regular_fetch_and_message,
    test_fetch_and_message,
)
from fetch_scholar import fetch_author_details
from log_config import setup_logging

logger = logging.getLogger(__name__)


def handle_fetch(args: argparse.Namespace, ch_name: str, token: str) -> None:
    """Fetch publications and post formatted messages to Slack."""
    # Execute the standard workflow of fetching publications and sending them.
    regular_fetch_and_message(args, ch_name, token)


def handle_send(args: argparse.Namespace, ch_name: str, token: str) -> None:
    """Send a test message to Slack without touching the cache."""
    # No fetching occurs here; simply verify connectivity to Slack.
    send_test_msg(token, ch_name)


def handle_add_author(args: argparse.Namespace, ch_name: str, token: str) -> None:
    """Validate and add a new scholar, then update the cache."""
    # The subparser ensures ``add_scholar_id`` exists, but double-check for safety.
    if not args.add_scholar_id:
        raise ValueError("add-author requires a Google Scholar ID.")
    add_scholar_and_fetch(args)


def handle_update_cache(args: argparse.Namespace, ch_name: str, token: str) -> None:
    """Re-fetch publications for all authors and update the cache."""
    # This mode refreshes the cache without sending any Slack messages.
    refetch_and_update(args)


def handle_test_fetch(args: argparse.Namespace, ch_name: str, token: str) -> None:
    """Fetch publications for a single author without side effects."""
    # Retrieve publications for the provided scholar ID and log how many were found.
    pubs = fetch_author_details(args.scholar_id)
    logger.info(
        "Fetched %d publications for scholar %s without caching or messaging.",
        len(pubs),
        args.scholar_id,
    )


def handle_test_run(args: argparse.Namespace, ch_name: str, token: str) -> None:
    """Dry run fetching and messaging for a small set of authors."""
    # Exercise the full workflow but limit the number of authors and avoid updating the cache.
    test_fetch_and_message(args, ch_name, token, limit=args.limit)


def get_args():
    """Build the CLI parser and return parsed arguments."""
    parser = argparse.ArgumentParser(
        description="Fetch publication history and send to slack."
    )

    # Global options available to all subcommands.
    parser.add_argument(
        "--authors_path", default="./src/authors.db", help="Path to authors database"
    )
    parser.add_argument(
        "--slack_config_path", default="./src/slack.config", help="Path to slack.config"
    )
    parser.add_argument("--verbose", action="store_true", help="Verbose output.")

    # Define subcommands replacing the previous boolean flags.
    subparsers = parser.add_subparsers(dest="command", required=True)

    fetch_parser = subparsers.add_parser(
        "fetch", help="Fetch publications and send messages to Slack."
    )
    fetch_parser.set_defaults(
        func=handle_fetch, test_message=False, update_cache=False, add_scholar_id=None
    )

    send_parser = subparsers.add_parser(
        "send", help="Send a test message to the configured Slack channel."
    )
    send_parser.set_defaults(
        func=handle_send, test_message=True, update_cache=False, add_scholar_id=None
    )

    add_parser = subparsers.add_parser(
        "add-author",
        help="Add a scholar by Google Scholar ID and update the cache without messaging.",
    )
    add_parser.add_argument("add_scholar_id", help="Google Scholar ID to add.")
    add_parser.set_defaults(
        func=handle_add_author, test_message=False, update_cache=False
    )

    update_parser = subparsers.add_parser(
        "update-cache",
        help="Re-fetch publications for all authors and update the cache only.",
    )
    update_parser.set_defaults(
        func=handle_update_cache,
        test_message=False,
        update_cache=True,
        add_scholar_id=None,
    )

    test_fetch_parser = subparsers.add_parser(
        "test-fetch",
        help="Fetch publications for a scholar without caching or messaging.",
    )
    test_fetch_parser.add_argument("scholar_id", help="Google Scholar ID to fetch.")
    test_fetch_parser.set_defaults(
        func=handle_test_fetch,
        test_message=False,
        update_cache=False,
        add_scholar_id=None,
    )

    test_run_parser = subparsers.add_parser(
        "test-run",
        help="Run the full workflow for a limited number of authors without caching.",
    )
    test_run_parser.add_argument(
        "--limit",
        type=int,
        default=2,
        help="Number of authors to include in the test run (default: 2).",
    )
    test_run_parser.set_defaults(
        func=handle_test_run,
        test_message=True,
        update_cache=False,
        add_scholar_id=None,
    )

    args = parser.parse_args()
    return parser, args


def initialize_args():
    """Parse command-line arguments and configure logging.

    The function always relies on the command-line interface, even when the
    script is launched without additional arguments (such as from an IDE).
    Default values defined in :func:`get_args` are therefore applied.

    Returns:
        argparse.Namespace: Object holding parsed command-line arguments.
    """

    # Parse the arguments using the standard CLI interface.
    parser, args = get_args()
    logger.info("Parsed command-line arguments.")

    # Configure logging based on requested verbosity.
    setup_logging(verbose=args.verbose)
    if args.verbose:
        logger.debug("Verbose log mode activated.")
    else:
        logger.info("Minimal log mode activated.")

    # Display the arguments being used to aid debugging.
    for arg, value in vars(args).items():
        logger.debug(f"Argument {arg} = {value}")

    return args


def main():
    """
    The main function to orchestrate the process of fetching scholarly articles,
    formatting them, and sending them to Slack.

    Main workflow:
    1. Determine execution mode: IDE vs Command-line.
    2. Configure logging based on debug mode.
    3. Fetch Slack configurations.
    4. Retrieve authors' details.
    5. Fetch publication details for each author.
    6. Format messages to be sent to Slack.
    7. Send messages to Slack.

    The exact workflow depends on the active flags.
    See 'Scenario #' in the code below for more info.

    Note: If running from an IDE, configurations are hardcoded.

    """
    setup_logging()
    logger.info("Initializing...")

    # Get the arguments
    args = initialize_args()

    # Set importnant directories
    root = os.path.dirname(args.authors_path)
    args.cache_path = os.path.join(root, "googleapi_cache")
    args.temp_cache_path = os.path.join(args.cache_path, "tmp")

    # Attempt to clean the old temporary cache if present
    delete_temp_cache(args)

    # Extract Slack configurations from the provided path
    slack_config = get_slack_config(args.slack_config_path)

    # Assign Slack API token and channel name from the config
    token = slack_config["api_token"]
    ch_name = slack_config["channel_name"]
    logger.info(f"Target Slack channel: {ch_name}.")

    # Delegate execution to the subcommand handler selected by the user.
    args.func(args, ch_name, token)

    # Attempt to clean the new temporary cache
    delete_temp_cache(args)

    logger.info("Done.")
    return args


if __name__ == "__main__":
    try:
        args = main()
    except Exception as e:
        # If an error occurs, attempt to delete the folder at args.temp_cache_path
        if hasattr(args, "temp_cache_path") and os.path.exists(args.temp_cache_path):
            shutil.rmtree(args.temp_cache_path)
        # Re-raise the exception after cleanup
        raise e
