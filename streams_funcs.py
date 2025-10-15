#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Fri Oct 20 17:02:03 2023

@author: costantino_ai
"""
import os
import shutil
import logging
from helper_funcs import (
    confirm_temp_cache,
    add_new_author_to_json,
    convert_json_to_tuple,
)
from fetch_scholar import fetch_from_json, fetch_pubs_dictionary
from slack_bot import make_slack_msg
from plugins.registry import get_global_registry
from plugins.slack import SlackPlugin

logger = logging.getLogger(__name__)


def update_cache_only(args):
    """Move fetched publications from the temp directory to cache.

    Args:
        temp_cache_path (str): Path to the temporary cache.
        cache_path (str): Path to the actual cache.
    """
    confirm_temp_cache(args.temp_cache_path, args.cache_path)
    logger.info("Fetched pubs successfully moved to cache and temporary cache cleared.")


def test_fetch_and_message(args, ch_name, token, limit: int = 2) -> None:
    """Fetch a limited number of authors and send test messages to Slack.

    The helper exercises the full fetching and messaging workflow without
    persisting any results to the cache. It is intended for dry runs where a
    small subset of authors is processed and their publications are posted to
    Slack with a clear test header.

    Args:
        args: Arguments passed through to :func:`fetch_from_json`.
        ch_name: Target Slack channel or user.
        token: Slack API token used for authentication.
        limit: Maximum number of authors to include in the test run. Defaults
            to ``2`` so the call remains lightweight.

    Returns:
        None

    For each fetched article, a test message is created and sent.
    """

    # Fetch a limited number of authors from the database.
    authors, articles = fetch_from_json(args, idx=limit)

    # Convert fetched details into formatted messages suitable for Slack.
    formatted_messages = make_slack_msg(authors, articles)
    logger.info(f"Formatted test messages for {len(authors)} authors.")

    test_header = "!!! This is a test message !!!"
    success = True  # To track if all messages are sent successfully.

    # Loop through each formatted message and send it to Slack.
    # Send via plugin registry (preferred)
    registry = get_global_registry()
    try:
        # Register once if not present
        if "slack" not in registry.list_plugins():
            registry.register(SlackPlugin)
        plugin = registry.create_instance("slack", {"api_token": token, "default_channel": ch_name}, cache=True)
    except Exception as e:
        logger.error(f"Failed to initialize Slack plugin: {e}")
        return

    for formatted_message in formatted_messages:
        formatted_message = f"```\n{test_header}\n{formatted_message}\n```"
        ok = plugin.send_message(formatted_message, ch_name)
        if not ok:
            success = False
            logger.warning("Failed to send a test message via Slack plugin")

    # Log overall success or failure.
    if success:
        logger.info("All test messages sent successfully.")
    else:
        logger.error("There was a problem sending one or more test messages.")


def regular_fetch_and_message(args, ch_name, token):
    """
    Regularly fetch articles and send messages to a Slack channel.
    If all messages are sent successfully, the cache will be updated.
    If any message fails, the temporary cache will be cleared.

    This function operates under the following conditions:
    - Not adding a scholar by ID (`add_scholar_id` is not provided).
    - Not updating the cache only (`update_cache` is False).
    - `test_message` is False.

    Args:
        args (argparse.Namespace): The argument object.
        ch_name (str): The channel name to send messages to.
        token (str): The token used for communication with Slack.

    """

    logger.info(
        "Starting fetch & send workflow: target=%s (messages will be sent)", ch_name
    )
    # Fetch all authors' details from the provided path.
    authors, articles = fetch_from_json(args)

    # Convert fetched details into messages suitable for Slack.
    formatted_messages = make_slack_msg(authors, articles)
    logger.info(f"Formatted messages for {len(authors)} authors.")

    # Initialize a success flag to track message sending process.
    success = True
    error_message = None  # To store any error encountered.

    # Send each formatted message via Slack plugin
    registry = get_global_registry()
    try:
        if "slack" not in registry.list_plugins():
            registry.register(SlackPlugin)
        plugin = registry.create_instance("slack", {"api_token": token, "default_channel": ch_name}, cache=True)
    except Exception as e:
        logger.error(f"Failed to initialize Slack plugin: {e}")
        plugin = None

    for formatted_message in formatted_messages:
        if plugin is None:
            break
        ok = plugin.send_message(formatted_message, ch_name)
        if not ok:
            success = False
            error_message = "send_message returned False"
            logger.warning(f"Failed to send a message due to: {error_message}")

    # Handle post-message actions based on the success flag.
    if success:
        confirm_temp_cache(args.temp_cache_path, args.cache_path)
        logger.info(
            "All messages sent. Moved fetched publications to cache and cleared temp cache."
        )
    else:
        # Clear the temporary cache due to the failure in sending messages.
        logger.error(
            f"Problem sending one or more messages to Slack. Cache was not updated. Error: {error_message}"
        )


def refetch_and_update(args):
    """
    Refetch author and publication details, and update the cache.

    This function deletes the old cache, refetches all the authors and
    their publication details, and subsequently updates the cache with
    the new fetched data.

    Parameters:
    - args: Arguments containing paths for cache, temp cache, and other relevant data.

    Returns:
    None
    """

    # Attempt to delete the old cache.
    if os.path.isdir(args.temp_cache_path):
        try:
            shutil.rmtree(args.cache_path)
            logger.debug(f"Deleted old cache at {args.cache_path}")
        except Exception as e:  # Handle specific exception to avoid broad except.
            logger.error(
                f"Failed to delete old cache at {args.cache_path}. Reason: {str(e)}"
            )

    # Refetch all the author and publication details.
    _ = fetch_from_json(args)

    # Update the cache with newly fetched data.
    update_cache_only(args)
    logger.info(
        "Re-fetched all publications. Data successfully moved to cache and temporary cache cleared."
    )


def add_scholar_and_fetch(args):
    """Add a new scholar, fetch publications, and update the cache.

    The author roster is now stored in a SQLite database. This helper inserts a
    new scholar into that database, retrieves their publications, and persists
    the results to the cache.

    Args:
        args: Object containing paths for the authors database, cache, and the
            identifier of the new author to add.
    """

    json_filename = f"{args.add_scholar_id}.json"
    json_filepath = os.path.join(args.cache_path, json_filename)

    if os.path.exists(json_filepath):
        logger.info(
            f"Author with scholar ID {args.add_scholar_id} already has cached publications. Fetching is skipped."
        )
        return

    author_dict = add_new_author_to_json(args.authors_path, args.add_scholar_id)
    logger.debug(
        f"Added new author with scholar ID {args.add_scholar_id} to authors database."
    )

    authors_json = [author_dict]
    authors = convert_json_to_tuple(authors_json)
    logger.debug("Converted new author's record into tuple representation.")

    articles = fetch_pubs_dictionary(authors, args)
    logger.info(f"Fetched {len(articles)} articles for the new author.")

    update_cache_only(args)
    logger.info(
        "Added author to database. Cache successfully updated with new author's data."
    )
