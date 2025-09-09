#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Fri Oct  6 21:07:18 2023

@author: costantino_ai
"""
import requests
import configparser
import logging

logger = logging.getLogger(__name__)


def send_test_msg(token, ch_name):
    """
    Send a test message to a specified Slack channel.

    The message will be framed with '#' characters for visibility.
    It's intended for testing purposes only and does not perform
    any fetch or save operations.

    Parameters:
    - token (str): The Slack API token.
    - ch_name (str): The name of the Slack channel to send the message to.

    Returns:
    None
    """

    # Initialize the test message to be sent.
    unformatted_msg = "This is a test message"

    # Calculate the width for the formatted message.
    # The '+2' is added to account for the '#' characters padding on either side of the message.
    width = len(unformatted_msg) + 2

    # Create a string of '#' characters of calculated width for the top and bottom borders.
    top_bottom = "#" * width

    # Format the message to be sent with markdown-like code blocks and '#' borders.
    formatted_msg = f"```\n{top_bottom}\n#{unformatted_msg}#\n{top_bottom}```"

    # Send the formatted message to the Slack channel using the send_to_slack function.
    response_json = send_to_slack(ch_name, formatted_msg, token)

    # Check if the message was sent successfully and log the outcome.
    if response_json["ok"]:
        logger.info(f"Test message successfully sent to #{ch_name}")


def make_slack_msg(authors: list, articles: list) -> list:
    """
    Create Slack messages by combining author details and article details.

    Parameters:
    - authors (list): List of author details.
    - articles (list): List of article details for the provided authors.

    Returns:
    - list: Formatted Slack messages, one for each author.

    Each message starts with a brief introduction of the author, followed by
    a list of their articles.
    """

    # Start by creating a message about the authors
    authors_msg = format_authors_message(authors)

    # For each article, create a message using the provided formatting function
    if len(articles) > 0:
        # Clean the list (remove duplicates)
        seen_titles = set()
        unique_list_of_articles = [
            seen_titles.add(d["title"]) or d
            for d in articles
            if d["title"] not in seen_titles
        ]

        # Build the message
        pubs_messages = ["List of publications since my last check:\n"] + [
            format_pub_message(article) for article in unique_list_of_articles
        ]
    else:
        pubs_messages = ["No new publications since my last check."]

    # Combine the authors' message with their respective articles' messages
    formatted_messages = [authors_msg] + pubs_messages

    return formatted_messages


def get_slack_config(slack_config_path="./data/slack.config"):
    """
    Retrieves the Slack configuration details from a configuration file.

    Parameters:
    - slack_config_path (str): Path to the Slack configuration file.

    Returns:
    - dict: Slack configuration details.
    """
    config = configparser.ConfigParser()
    config.read(slack_config_path)

    slack_config = {
        "api_token": config.get("slack", "api_token"),
        "channel_name": config.get("slack", "channel_name"),
    }

    logger.debug(f"Fetched Slack configuration from {slack_config_path}.")
    return slack_config


def format_pub_message(pub):
    """
    Format an article dictionary for Slack using a specific markdown style.

    The function iterates over a list of article details and returns the last article
    details formatted in a markdown style suitable for Slack:
    - The title is a clickable link with the publication year in bold.
    - Authors are listed on a new line.
    - An empty line is added after the authors.
    - The abstract is displayed on a new line in smaller text.
    - A line of 50 dashes is added at the end.

    Parameters:
    - articles (list of dict): Each dictionary should contain the following keys:
        * 'title' (str): The title of the article.
        * 'authors' (str): Comma-separated string of authors.
        * 'year' (str): Publication year.
        * 'abstract' (str): Abstract of the article.
        * 'pub_url' (str): URL of the article.
        * 'journal'

    Returns:
    - str: A formatted string suitable for Slack of the last article in the list.
    """
    details = []  # Initializing an empty list to store formatted details of the article
    details.append("-" * 50)  # Appending a line with 50 dashes
    details.append("")  # Adding an empty line at the end

    # Adding the title with year in bold, formatted as a clickable link to the details list
    title = f"*<{pub['pub_url']}|{pub['title']}>*"
    details.append(title)

    # Splitting the authors string into a list of individual authors
    authors = pub["authors"].split(",")
    # Checking if there are fewer than 5 authors
    if len(authors) < 5:
        details.append(f"Authors: {pub['authors']}")
    else:
        # If more than 4 authors, display the first author, the count of authors in between, and the last author
        details.append(f"Authors: {authors[0]}, [+{len(authors)-2}], {authors[-1]}")

    details.append(f"Journal: {pub['journal']}")
    details.append("")  # Adding an empty line after the authors
    # Adding the article abstract in smaller text
    details.append(f"Abstract: _{pub['abstract']}_")
    details.append("")  # Adding an empty line at the end

    # Joining the details list into a single string separated by newline characters
    message = "\n".join(details)
    logger.debug(message)

    return message  # Returning the formatted message


def format_authors_message(authors: list) -> str:
    """
    Formats a list of authors into a pretty message suitable for Slack.

    Parameters:
    - authors: List of items where each item is a tuple (author_name, author_id)

    Returns:
    - str: A string message with each author and their associated ID, each on a new line.
    """

    # Order the authors alphabetically by name
    authors_sorted = sorted(authors, key=lambda x: x[0].lower())

    # Construct the message by listing each author with their ID on separate lines, indented
    formatted_authors = "\n".join(
        [
            f"\t{author[0]},\t\tGoogle Scholar ID: {author[1]}"
            for author in authors_sorted
        ]
    )

    # Add the code block delimiters and the description
    formatted_message = "List of monitored authors:\n```" + formatted_authors + "```"

    # Return the formatted message
    return formatted_message


def get_channel_id_by_name(channel_name, token):
    """
    Returns the channel ID given a channel name, or None if not found.
    This uses the conversations.list API endpoint and checks 'name' for a match.
    """
    url = "https://slack.com/api/conversations.list"
    headers = {"Authorization": f"Bearer {token}"}
    params = {
        "types": "public_channel, private_channel",  # Adjust if needed
        "limit": 1000,  # Slack pages results, adjust or paginate if your workspace has many channels
    }

    while True:
        response = requests.get(url, headers=headers, params=params).json()
        if not response["ok"]:
            logger.warning(f"Failed to list channels: {response['error']}")
            return None

        for channel in response["channels"]:
            # 'channel["name"]' is the channel's actual short name without '#'
            if channel["name"] == channel_name:
                return channel["id"]

        # Pagination: if there's more, update 'cursor' and keep fetching
        if response.get("response_metadata", {}).get("next_cursor"):
            params["cursor"] = response["response_metadata"]["next_cursor"]
        else:
            break

    return None


def get_user_id_by_name(user_name, token):
    """
    Returns the user ID for a given user name, or None if not found.
    This uses the users.list API endpoint and checks either 'name' or 'real_name'.
    Adjust logic if you want to match display_name or something else.
    """
    url = "https://slack.com/api/users.list"
    headers = {"Authorization": f"Bearer {token}"}
    params = {"limit": 1000}

    while True:
        response = requests.get(url, headers=headers, params=params).json()
        if not response["ok"]:
            logger.warning(f"Failed to list users: {response['error']}")
            return None

        for member in response["members"]:
            user_handle = member.get(
                "name", ""
            )  # Default to empty string if key is missing
            real_name = member.get(
                "real_name", ""
            )  # Default to empty string if key is missing

            if user_handle == user_name or real_name == user_name:
                return member["id"]

        # Pagination
        if response.get("response_metadata", {}).get("next_cursor"):
            params["cursor"] = response["response_metadata"]["next_cursor"]
        else:
            break

    return None


def open_im_channel(user_id, token):
    """
    Opens (or retrieves) a DM channel with a user.
    Returns the channel ID if successful, None otherwise.
    """
    url = "https://slack.com/api/conversations.open"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json; charset=utf-8",
    }
    data = {"users": user_id}

    response = requests.post(url, headers=headers, json=data).json()
    if not response["ok"]:
        logger.warning(f"Error opening DM for user {user_id}: {response}")
        return None

    return response["channel"]["id"]


def send_to_slack(channel_or_user_name, message, token):
    """
    Sends a given message to a specified Slack channel name or user name.
    - If channel_or_user_name is a Slack channel (e.g., "general"), it sends directly.
    - If it's a user name, it opens a DM and sends privately.
    - Otherwise, it logs an error.
    """

    # 1. Try to resolve as a channel name
    channel_id = get_channel_id_by_name(channel_or_user_name, token)
    if channel_id:
        # We found a matching channel name
        response = _send_message_to_channel(channel_id, message, token)
        return response

    # 2. Otherwise, try to resolve as a user name
    user_id = get_user_id_by_name(channel_or_user_name, token)
    if user_id:
        # Found a matching user; open DM and send the message
        dm_channel_id = open_im_channel(user_id, token)
        if dm_channel_id:
            response = _send_message_to_channel(dm_channel_id, message, token)
        return response

    # 3. If neither was found, log an error
    logger.error(
        f"Error: '{channel_or_user_name}' is not a valid channel or user in this workspace."
    )


def _send_message_to_channel(channel_id, message, token):
    """
    Internal helper that directly posts to a channel (public, private, or DM).
    """
    url = "https://slack.com/api/chat.postMessage"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json; charset=utf-8",
    }
    data = {"channel": channel_id, "text": message}
    response = requests.post(url, headers=headers, json=data).json()

    if not response.get("ok"):
        logger.warning(
            f"Sending message to #{channel_id} failed. Error: {response.get('error')}. "
            f"Message:\n{message}"
        )
    else:
        logger.debug(f"Message successfully sent to #{channel_id}.")

    return response
