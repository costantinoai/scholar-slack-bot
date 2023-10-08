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
from fetch_scholar import fetch_pubs_dictionary
from helper_funcs import convert_json_to_tuple, get_authors_json, add_new_author_to_json
from log_config import MIN, STANDARD

# Configure logging
logging.basicConfig(level=STANDARD)

def send_test_msg(token, ch_name):  
    formatted_message = ['This is a test message.']
    send_to_slack(ch_name, formatted_message, token)
    logging.log(MIN, f"Test message sent to #{ch_name}")
    return

def get_args():
    """
    Parses command-line arguments for the script.
    
    Returns:
    - argparse.Namespace: Parsed arguments.
    """
    parser = argparse.ArgumentParser(description='Fetch publication history and send to slack.')
    
    # Add command-line arguments
    parser.add_argument('--authors_path', default='./src/authors.json', help='Path to authors.json')
    parser.add_argument('--slack_config_path', default='./src/slack.config', help='Path to slack.config')
    parser.add_argument('--verbose', action='store_true', help='Verbose output.')

    # Mutually exclusive arguments group
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument('--test_fetching', action='store_true', help='Test fetching functions (do not send message or save cache).')
    group.add_argument('--test_message', action='store_true', help='Send test message (do not fetch, send message or save cache).')
    group.add_argument('--add_scholar_id', help='Add a new scholar by Google Scholar ID to the file specified in --authors_path, fetch publications and save them to cache (do not send message).')

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
    
    # Check if the script is executed via command line or from an IDE
    if len(sys.argv) > 1:
        # Parse command-line arguments
        args = get_args()
        logging.log(MIN, "Parsed command-line arguments.")
    else:
        class IDEArgs:
            def __init__(self):
                self.slack_config_path = './src/slack.config'
                self.authors_path = './src/authors.json'
                self.verbose = True
                self.test_fetching = False
                self.test_message = False
                self.add_scholar_id = None

        args = IDEArgs()
        logging.log(MIN, "Using hardcoded configurations for IDE execution.")
        
    # Reconfigure logging based on DEBUG_FLAG's value
    if args.verbose:
        logging.basicConfig(level=STANDARD)
        logging.log(STANDARD, "STANDARD log mode activated.")
    else:
        logging.basicConfig(level=MIN)
        logging.log(MIN, "MIN log mode activated.")

    # Extract Slack configurations from the provided path
    slack_config = get_slack_config(args.slack_config_path)
    logging.log(STANDARD, f"Fetched Slack configuration from {args.slack_config_path}.")

    # Assign Slack API token and channel name from the config
    token = slack_config['api_token']
    ch_name = slack_config['channel_name']
    logging.log(MIN, f"Target Slack channel: {ch_name}.")
    
    if args.test_message == True:
        send_test_msg(token, ch_name)
        return
        
    # Retrieve authors' details from the given JSON path
    if args.add_scholar_id != None:
        # Save new json with added author
        author_dict = add_new_author_to_json(args.authors_path, args.add_scholar_id)
            
        # Select only new author for fetching
        authors_json = [author_dict]

    else: 
        authors_json = get_authors_json(args.authors_path)
        logging.log(STANDARD, f"Fetched authors' details from {args.authors_path}.")

    # Convert JSON data of authors to a tuple representation
    authors = convert_json_to_tuple(authors_json)
    logging.log(STANDARD, "Converted authors' JSON data into tuple representation.")

    # Get publication details for each author from the scholarly database
    articles = fetch_pubs_dictionary(authors, args)
    logging.log(MIN, f"Fetched {len(articles)} articles for the provided authors.")

    if args.add_scholar_id == None and args.test_message == False and args.test_fetching == False:
        # Create Slack messages for each author using the provided articles' details
        formatted_messages = make_slack_msg(authors, articles)
        logging.log(MIN, f"Formatted messages for {len(authors)} authors.")
    
        # Send each of the formatted messages to the configured Slack channel
        for formatted_message in formatted_messages:
            send_to_slack(ch_name, formatted_message, token)
            logging.log(STANDARD, "Sent message to Slack.")  # Preview first 50 chars for brevity

if __name__ == "__main__":
    main()



