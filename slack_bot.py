#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Fri Oct  6 21:07:18 2023

@author: costantino_ai
"""
import requests
import configparser

def get_slack_config(slack_config_path='./src/slack.config'):
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
        'api_token': config.get('slack', 'api_token'),
        'channel_name': config.get('slack', 'channel_name'),
        'channel_id': config.get('slack', 'channel_id')
    }
    
    return slack_config

def send_to_slack(channel_id, message, token):
    """
    Sends a given message to a specified Slack channel using the provided authorization token.
    
    :param channel_id: The ID of the Slack channel to send the message to.
    :param message: The content of the message to be sent.
    :param token: The Slack API authorization token.
    :return: A dictionary containing the response from the Slack API.
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
    return response.json()

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
    details.append("-" * 50)  # Appending a line with 50 dashes
    details.append("")  # Adding an empty line at the end

    # Joining the details list into a single string separated by newline characters
    message = "\n".join(details)
    print(message)  # Printing the formatted message

    return message  # Returning the formatted message


def format_authors_message(authors: list) -> str:
    """
    Formats a list of authors into a pretty message suitable for Slack. 
    
    :param authors: List of authors where each author is a dictionary with 'name' and 'id' keys.
    :return: A string message with each author and their associated ID, each on a new line.
    """
    
    # Construct the message by listing each author with their ID on separate lines, indented
    formatted_authors = '\n'.join([f"\t{author[0]}, Google Scholar ID: {author[1]}" for author in authors])

    # Add the code block delimiters and the description
    formatted_message = 'List of monitored authors:\n```\n' + formatted_authors + '\n```'

    # Return the formatted message
    return formatted_message