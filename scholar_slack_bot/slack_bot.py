#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Fri Oct  6 21:07:18 2023

@author: costantino_ai
"""
import os
import configparser
import logging
import asyncio

from .log_config import MIN, STANDARD


class SlackNotifier:
    """Helper class to send messages to Slack."""

    def __init__(self, token: str):
        self.token = token

    async def _get_channel_id_async(self, name: str):
        """Return channel ID for a channel name asynchronously."""
        import aiohttp

        url = "https://slack.com/api/conversations.list"
        headers = {"Authorization": f"Bearer {self.token}"}
        params = {"types": "public_channel, private_channel", "limit": 1000}
        async with aiohttp.ClientSession() as session:
            while True:
                logging.debug("Listing channels with cursor %s", params.get("cursor"))
                async with session.get(url, headers=headers, params=params) as resp:
                    data = await resp.json()
                if not data.get("ok"):
                    logging.warning("Failed to list channels: %s", data.get("error"))
                    return None
                for ch in data.get("channels", []):
                    if ch.get("name") == name:
                        return ch.get("id")
                cursor = data.get("response_metadata", {}).get("next_cursor")
                if cursor:
                    params["cursor"] = cursor
                else:
                    break
        return None

    def _get_channel_id(self, name: str):
        return asyncio.run(self._get_channel_id_async(name))

    async def _get_user_id_async(self, name: str):
        """Return user ID for a given username or real name asynchronously."""
        import aiohttp

        url = "https://slack.com/api/users.list"
        headers = {"Authorization": f"Bearer {self.token}"}
        params = {"limit": 1000}
        async with aiohttp.ClientSession() as session:
            while True:
                logging.debug("Listing users with cursor %s", params.get("cursor"))
                async with session.get(url, headers=headers, params=params) as resp:
                    data = await resp.json()
                if not data.get("ok"):
                    logging.warning("Failed to list users: %s", data.get("error"))
                    return None
                for member in data.get("members", []):
                    if member.get("name") == name or member.get("real_name") == name:
                        return member.get("id")
                cursor = data.get("response_metadata", {}).get("next_cursor")
                if cursor:
                    params["cursor"] = cursor
                else:
                    break
        return None

    def _get_user_id(self, name: str):
        return asyncio.run(self._get_user_id_async(name))

    async def _open_im_async(self, user_id: str):
        """Open a DM channel with a user and return the channel ID asynchronously."""
        import aiohttp

        url = "https://slack.com/api/conversations.open"
        headers = {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json; charset=utf-8",
        }
        data = {"users": user_id}
        async with aiohttp.ClientSession() as session:
            async with session.post(url, headers=headers, json=data) as resp:
                data = await resp.json()
        if not data.get("ok"):
            logging.warning("Error opening DM for %s: %s", user_id, data)
            return None
        return data["channel"]["id"]

    def _open_im(self, user_id: str):
        return asyncio.run(self._open_im_async(user_id))

    async def _post_message_async(self, channel_id: str, message: str):
        """Send raw message to a channel asynchronously."""
        import aiohttp

        url = "https://slack.com/api/chat.postMessage"
        headers = {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json; charset=utf-8",
        }
        data = {"channel": channel_id, "text": message}
        logging.debug("Posting message to channel %s", channel_id)
        async with aiohttp.ClientSession() as session:
            async with session.post(url, headers=headers, json=data) as resp:
                data = await resp.json()
        if not data.get("ok"):
            logging.warning("Sending message failed: %s", data.get("error"))
        else:
            logging.info("Message successfully sent to %s", channel_id)
        return data

    def _post_message(self, channel_id: str, message: str):
        return asyncio.run(self._post_message_async(channel_id, message))

    async def send_message_async(self, target: str, message: str):
        """Send a message to a channel or user name asynchronously."""
        channel_id = await self._get_channel_id_async(target)
        if channel_id:
            return await self._post_message_async(channel_id, message)
        user_id = await self._get_user_id_async(target)
        if user_id:
            dm_channel = await self._open_im_async(user_id)
            if dm_channel:
                return await self._post_message_async(dm_channel, message)
        logging.error("'%s' is not a valid channel or user", target)
        return {"ok": False, "error": "not_found"}

    def send_message(self, target: str, message: str):
        return asyncio.run(self.send_message_async(target, message))


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

    notifier = SlackNotifier(token)
    response_json = notifier.send_message(ch_name, formatted_msg)

    # Check if the message was sent successfully and log the outcome.
    if response_json["ok"]:
        logging.log(MIN, f"Test message successfully sent to #{ch_name}")


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
            seen_titles.add(d["title"]) or d for d in articles if d["title"] not in seen_titles
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


def get_slack_config(slack_config_path="./src/slack.config"):
    """
    Retrieves the Slack configuration details from a configuration file.

    Parameters:
    - slack_config_path (str): Path to the Slack configuration file.

    Returns:
    - dict: Slack configuration details.
    """
    # Load .env if present
    try:
        from dotenv import load_dotenv
        load_dotenv()
    except ModuleNotFoundError:
        logging.debug("python-dotenv not installed; skipping .env loading")

    token = os.getenv("SLACK_API_TOKEN")
    channel = os.getenv("SLACK_CHANNEL")

    if token and channel:
        logging.log(STANDARD, "Loaded Slack configuration from environment.")
        return {"api_token": token, "channel_name": channel}

    config = configparser.ConfigParser()
    config.read(slack_config_path)

    slack_config = {
        "api_token": config.get("slack", "api_token"),
        "channel_name": config.get("slack", "channel_name"),
    }

    logging.log(STANDARD, f"Fetched Slack configuration from {slack_config_path}.")
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
    print(message)  # Printing the formatted message

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
        [f"\t{author[0]},\t\tGoogle Scholar ID: {author[1]}" for author in authors_sorted]
    )

    # Add the code block delimiters and the description
    formatted_message = "List of monitored authors:\n```" + formatted_authors + "```"

    # Return the formatted message
    return formatted_message


def send_to_slack(channel_or_user_name, message, token):
    """
    Sends a given message to a specified Slack channel name or user name.
    - If channel_or_user_name is a Slack channel (e.g., "general"), it sends directly.
    - If it's a user name, it opens a DM and sends privately.
    - Otherwise, it logs an error.
    """

    notifier = SlackNotifier(token)
    return notifier.send_message(channel_or_user_name, message)

def _send_message_to_channel(channel_id, message, token):
    """Backward compatible helper to send message to a channel."""
    notifier = SlackNotifier(token)
    return notifier._post_message(channel_id, message)


async def send_messages_parallel(target: str, messages: list, token: str):
    """Send multiple messages concurrently to a Slack target."""
    notifier = SlackNotifier(token)

    async def _send(msg):
        return await notifier.send_message_async(target, msg)

    tasks = [_send(m) for m in messages]
    return await asyncio.gather(*tasks)
