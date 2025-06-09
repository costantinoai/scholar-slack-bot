#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Sat Oct  7 02:46:59 2023

@author: costantino_ai
"""

import os
import sys
import argparse
import logging
import shutil

from .slack_bot import get_slack_config, send_test_msg
from .fetch_scholar import fetch_from_json
from .helper_funcs import has_conflicting_args, delete_temp_cache
from .streams_funcs import (
    test_fetch_and_message,
    refetch_and_update,
    add_scholar_and_fetch,
    regular_fetch_and_message,
)
from .log_config import MIN, STANDARD, configure_logging


def get_args():
    """Return argument parser and parsed args."""
    parser = argparse.ArgumentParser(description="Fetch publication history and send to Slack.")
    parser.add_argument("--authors_path", default="./src/authors.json", help="Path to authors.json")
    parser.add_argument("--slack_config_path", default="./src/slack.config", help="Path to slack.config")
    parser.add_argument("--verbose", action="store_true", help="Verbose output")

    sub = parser.add_subparsers(dest="command")
    sub.add_parser("send", help="Fetch, send message and update cache")
    sub.add_parser("update-cache", help="Re-fetch all authors and update cache")
    add_parser = sub.add_parser("add-author", help="Add a new scholar id and fetch")
    add_parser.add_argument("scholar_id")
    test_parser = sub.add_parser("test", help="Test fetching and/or messaging")
    test_parser.add_argument("--fetch", action="store_true", help="Fetch publications during test")
    test_parser.add_argument("--message", action="store_true", help="Send Slack message during test")

    # Keep old flags for backward compatibility
    parser.add_argument("--test_fetching", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--test_message", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--update_cache", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--add_scholar_id", help=argparse.SUPPRESS)

    args = parser.parse_args()
    return parser, args


def initialize_args():
    """
    Initialize arguments based on the mode of execution (Command Line vs IDE).

    When executed via command line, the function will parse the provided command-line arguments.
    If executed from an IDE, it will use default configurations.

    Returns:
        argparse.Namespace or IDEArgs: Argument object based on the mode of execution.
    """

    # Check if the script is executed via command line
    if len(sys.argv) > 1:
        parser, args = get_args()
        logging.log(MIN, "Parsed command-line arguments.")

        # Map subcommands to legacy flags
        if args.command == "send" or args.command is None:
            pass
        elif args.command == "update-cache":
            args.update_cache = True
        elif args.command == "add-author":
            args.add_scholar_id = args.scholar_id
        elif args.command == "test":
            args.test_fetching = args.fetch
            args.test_message = args.message
        # Ensure default values for optional flags
        args.test_fetching = getattr(args, "test_fetching", False)
        args.test_message = getattr(args, "test_message", False)
        args.update_cache = getattr(args, "update_cache", False)
        args.add_scholar_id = getattr(args, "add_scholar_id", None)
    else:
        # Default configurations for execution in IDE
        class IDEArgs:
            def __init__(self):
                self.slack_config_path = "./src/slack-test.config"
                self.authors_path = "./src/authors.json"
                self.verbose = True
                self.test_fetching = True
                self.test_message = True
                self.add_scholar_id = None
                self.update_cache = False

        args = IDEArgs()

    # Checking for mutual exclusivity of the arguments
    if has_conflicting_args(args):
        raise ValueError(
            "--add_scholar_id and --update_cache cannot be used together or with --test_fetching, --test_message"
        )

    # Configure logging based on --verbose flag
    configure_logging(verbose=args.verbose)
    logging.debug("Debug logging activated" if args.verbose else "Info logging activated")

    # Display the arguments being used
    for arg, value in vars(args).items():
        logging.log(STANDARD, f"Argument {arg} = {value}")

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
    logging.log(MIN, "Initializing...")

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
    logging.log(MIN, f"Target Slack channel: {ch_name}.")

    # Scenario 1: Test message. No fetching or cache update.
    if args.test_message and not args.test_fetching:
        send_test_msg(token, ch_name)

    # Scenario 2: Test fetching. No message or cache update.
    elif not args.test_message and args.test_fetching:
        _ = fetch_from_json(args)

    # Scenario 3: Test fetching + message. No cache update.
    elif args.test_message and args.test_fetching:
        test_fetch_and_message(args, ch_name, token)

    # Scenario 4: Re-fetch all the authors and update cache. No message.
    elif args.update_cache:
        refetch_and_update(args)

    # Scenario 5: Add a new scholar ID and fetch. No message.
    elif args.add_scholar_id:
        add_scholar_and_fetch(args)

    # Scenario 6: Regular stream. Fetch, send message and update cache.
    else:
        regular_fetch_and_message(args, ch_name, token)

    # Attempt to clean the new temporary cache
    delete_temp_cache(args)

    logging.log(MIN, "Done.")
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
