#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Fri Oct  6 21:07:18 2023

@author: costantino_ai
"""
import requests
import configparser
import logging

from log_config import MIN, STANDARD


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
    config = configparser.ConfigParser()
    config.read(slack_config_path)

    slack_config = {
        "api_token": config.get("slack", "api_token"),
        "channel_name": config.get("slack", "channel_name"),
    }

    logging.log(STANDARD, f"Fetched Slack configuration from {slack_config_path}.")
    return slack_config


def send_to_slack(channel_id, message, token):
    """
    Sends a given message to a specified Slack channel using the provided authorization token.

    """

    url = "https://slack.com/api/chat.postMessage"  # The Slack API endpoint for posting messages

    # Define the request headers, including authorization and content type
    headers = {
        "Authorization": f"Bearer {token}",  # Use the provided token for authorization
        "Content-Type": "application/json; charset=utf-8",  # Specify the content type as JSON
    }

    # Define the request data, which includes the channel ID and the message
    data = {"channel": channel_id, "text": message}

    # Send a POST request to the Slack API with the headers and data
    response = requests.post(url, headers=headers, json=data)

    # Return the JSON response from the Slack API
    response_json = response.json()

    if response_json["ok"] == False:
        logging.warning(
            f"Sending message to #{channel_id} failed. Error: {response_json['error']}. Message:\n{message}"
        )
    else:
        logging.log(STANDARD, f"Message succesfully sent to #{channel_id}.")

    return response_json


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
