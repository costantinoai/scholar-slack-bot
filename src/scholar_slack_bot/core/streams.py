#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Fri Oct 20 17:02:03 2023

@author: costantino_ai
"""
import os
import shutil
import logging
from ..utils.helpers import (
    confirm_temp_cache,
    add_new_author_to_json,
    convert_json_to_tuple,
)
from .fetcher import fetch_from_json, fetch_pubs_dictionary
from ..slack.client import make_slack_msg, send_to_slack

logger = logging.getLogger(__name__)


def update_cache_only(args):
    """Move fetched publications from the temp directory to cache.

    Args:
        temp_cache_path (str): Path to the temporary cache.
        cache_path (str): Path to the actual cache.
    """
    confirm_temp_cache(args.temp_cache_path, args.cache_path)
    logger.info("Fetched pubs successfully moved to cache and temporary cache cleared.")


def test_fetch_and_message(args, ch_name, token):
    """
    Test fetching of articles and send formatted messages to a Slack channel.

    This function is used for tests when:
    - Not adding a scholar by ID (`add_scholar_id` is not provided).
    - Not updating the cache only (`update-cache` is False).
    - The test arguments set `test_message` (and optionally a testing flag
      to limit fetching) to verify fetching and messaging together.

    Args:
        args: Arguments used by the `fetch_from_json` function.
        ch_name (str): The channel name to send the message to.
        token (str): The token used for communication with Slack.

    Returns:
        None

    For each fetched article, a test message is created and sent.
    """

    # Fetch details for up to 3 authors.
    authors, articles = fetch_from_json(args, idx=3)

    # Convert fetched details into formatted messages suitable for Slack.
    formatted_messages = make_slack_msg(authors, articles)
    logger.info(f"Formatted test messages for {len(authors)} authors.")

    test_header = "!!! This is a test message !!!"
    success = True  # To track if all messages are sent successfully.

    # Loop through each formatted message and send it to Slack.
    for formatted_message in formatted_messages:
        formatted_message = f"```\n{test_header}\n{formatted_message}\n```"
        response_json = send_to_slack(ch_name, formatted_message, token)

        # Update success status based on the response.
        if not response_json["ok"]:
            success = False
            e = response_json["error"]
            # It might be useful to log failures as they happen.
            logger.warning(f"Failed to send a test message due to: {e}")

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

    # Fetch all authors' details from the provided path.
    authors, articles = fetch_from_json(args)

    # Convert fetched details into messages suitable for Slack.
    formatted_messages = make_slack_msg(authors, articles)
    logger.info(f"Formatted messages for {len(authors)} authors.")

    # Initialize a success flag to track message sending process.
    success = True
    error_message = None  # To store any error encountered.

    # Send each formatted message to Slack.
    for formatted_message in formatted_messages:
        response_json = send_to_slack(ch_name, formatted_message, token)

        # If any message fails, update the success flag and store the error.
        if not response_json["ok"]:
            success = False
            error_message = response_json.get("error", "Unknown error")
            logger.warning(f"Failed to send a message due to: {error_message}")

    # Handle post-message actions based on the success flag.
    if success:
        confirm_temp_cache(args.temp_cache_path, args.cache_path)
        logger.info(
            "Fetched publications successfully moved to cache. Temporary cache cleared."
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
