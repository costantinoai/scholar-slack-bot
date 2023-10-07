#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Sat Oct  7 02:46:59 2023

@author: costantino_ai
"""

import sys
import argparse
import logging

from slack_bot import send_to_slack, get_slack_config, make_slack_msg
from fetch_scholar import fetch_pubs_dictionary, set_debug
from helper_funcs import convert_json_to_tuple, get_authors_json
from log_config import MIN, STANDARD

# Default DEBUG_FLAG is set to False
DEBUG_FLAG = False

# Configure logging
if DEBUG_FLAG:
    logging.basicConfig(level=STANDARD)
else:
    logging.basicConfig(level=MIN)
    
def get_args():
    """
    Parses command-line arguments for the script.
    
    Returns:
    - argparse.Namespace: Parsed arguments.
    """
    parser = argparse.ArgumentParser(description='Fetch publication history and send to slack.')
    
    # Add command-line arguments
    parser.add_argument('--authors_path', default='./src/authors_short.json', help='Path to authors.json')
    parser.add_argument('--slack_config_path', default='./src/slack.config', help='Path to slack.config')
    parser.add_argument('--debug', action='store_true', help='Enable debug mode')
    
    return parser.parse_args()

def main():
    """
    The main function to orchestrate the process of fetching scholarly articles, 
    formatting them, and sending them to Slack.
    
    Workflow:
    1. Determine execution mode: IDE vs Command-line.
    2. Configure logging based on debug mode.
    3. Fetch Slack configurations.
    4. Retrieve authors' details.
    5. Fetch publication details for each author.
    6. Format messages to be sent to Slack.
    7. Send messages to Slack.
    
    Note: If running from an IDE, configurations are hardcoded.
    """
    logging.log(MIN, "Initializing...")

    # Use the global DEBUG_FLAG so its value can be modified within this function
    global DEBUG_FLAG
    
    # Check if the script is executed via command line or from an IDE
    if len(sys.argv) > 1:
        # Parse command-line arguments
        args = get_args()
        DEBUG_FLAG = args.debug
        logging.log(STANDARD, "Parsed command-line arguments.")
    else:
        # Use hardcoded configurations suitable for IDE execution
        args = {}
        args['slack_config_path'] = './src/slack.config'
        if DEBUG_FLAG:
            args['authors_path'] = './src/authors_short.json'
        else:
            args['authors_path'] = './src/authors.json'
        logging.log(STANDARD, "Using hardcoded configurations for IDE execution.")

    # Reconfigure logging based on DEBUG_FLAG's value
    if DEBUG_FLAG:
        logging.basicConfig(level=STANDARD)
        logging.log(STANDARD, "Debug mode activated.")
    else:
        logging.basicConfig(level=MIN)
        logging.log(MIN, "Standard mode activated.")

    # Sync the DEBUG_FLAG's value with the fetch_scholar module
    set_debug(DEBUG_FLAG)
    logging.log(STANDARD, f"Set debug mode in fetch_scholar.py to {DEBUG_FLAG}.")

    # Extract Slack configurations from the provided path
    slack_config = get_slack_config(args['slack_config_path'])
    logging.log(STANDARD, f"Fetched Slack configuration from {args['slack_config_path']}.")

    # Assign Slack API token and channel name from the config
    token = slack_config['api_token']
    ch_name = slack_config['channel_name']
    logging.log(MIN, f"Target Slack channel: {ch_name}.")

    # Retrieve authors' details from the given JSON path
    authors_json = get_authors_json(args['authors_path'])
    logging.log(STANDARD, f"Fetched authors' details from {args['authors_path']}.")

    # Convert JSON data of authors to a tuple representation
    authors = convert_json_to_tuple(authors_json)
    logging.log(STANDARD, "Converted authors' JSON data into tuple representation.")

    # Get publication details for each author from the scholarly database
    articles = fetch_pubs_dictionary(authors)
    logging.log(MIN, f"Fetched {len(articles)} articles for the provided authors.")

    # Create Slack messages for each author using the provided articles' details
    formatted_messages = make_slack_msg(authors, articles)
    logging.log(MIN, f"Formatted messages for {len(authors)} authors.")

    # Send each of the formatted messages to the configured Slack channel
    for formatted_message in formatted_messages:
        send_to_slack(ch_name, formatted_message, token)
        logging.log(STANDARD, "Sent message to Slack.")  # Preview first 50 chars for brevity

if __name__ == "__main__":
    main()



