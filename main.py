#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Sat Oct  7 02:46:59 2023

@author: costantino_ai
"""

import sys
import argparse
import logging

from slack_bot import send_to_slack, get_slack_config, make_slack_msg, send_test_msg
from fetch_scholar import fetch_pubs_dictionary
from helper_funcs import convert_json_to_tuple, get_authors_json, add_new_author_to_json
from log_config import MIN, STANDARD

# Configure logging
logging.basicConfig(level=STANDARD)

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
    parser.add_argument('--test_fetching', action='store_true', help='Test fetching functions. Do not send message (unless --test_message) or save cache.')
    parser.add_argument('--test_message', action='store_true', help='Send test message. Do not fetch, send message (unless --test_fetching) or save cache.')
    parser.add_argument('--update_cache', action='store_true', help='Re-fetch pubs for all authors and save them to cache. Do not send message.')
    parser.add_argument('--add_scholar_id', help='Add a new scholar by Google Scholar ID to the file specified in --authors_path, fetch publications and save them to cache (do not send message).')

    args = parser.parse_args()

    return parser, args

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
        parser, args = get_args()
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
                self.update_cache = False

        args = IDEArgs()
        logging.log(MIN, "Using default configurations.")
    
    # Manually checking for mutual exclusivity
    if args.add_scholar_id and (args.test_fetching or args.test_message or args.update_cache):
        if len(sys.argv) > 1:
             raise ValueError("--add_scholar_id and --update_cache cannot be used together or with --test_fetching, --test_message")
        else:
            parser.error("--add_scholar_id and --update_cache cannot be used together or with --test_fetching, --test_message")
            
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
    
    if args.test_message == True and args.test_fetching == False:
        send_test_msg(token, ch_name)
        return
        
    
    if args.add_scholar_id != None: # In this case we want to add a new author and fetch
        # Save new json with added author
        author_dict = add_new_author_to_json(args.authors_path, args.add_scholar_id)
            
        # Select only new author for fetching
        authors_json = [author_dict]

    else: 
        # Retrieve authors' details from the given JSON path
        authors_json = get_authors_json(args.authors_path)
        logging.log(STANDARD, f"Fetched authors' details from {args.authors_path}.")

    # Convert JSON data of authors to a tuple representation
    authors = convert_json_to_tuple(authors_json)
    logging.log(STANDARD, "Converted authors' JSON data into tuple representation.")

    # Get publication details for each author from the scholarly database
    articles = fetch_pubs_dictionary(authors, args)
    logging.log(MIN, f"Fetched {len(articles)} articles for the provided authors.")

    if not args.add_scholar_id and not args.update_cache and args.test_fetching == args.test_message:
		# This block is entered under the following scenarios:
		# 1. When `add_scholar_id` is not provided (i.e., its value is None).
		#    This means that we are not in the mode to add a scholar by ID.
		# 
		# AND
		#
		# 2a. Both `test_fetching` and `test_message` are True.
		#     This indicates that we want to perform a test fetch and also send a test message.
		#
		# OR
		#
		# 2b. Both `test_fetching` and `test_message` are False.
		#     This is the normal situation where no specific "test" flags are active.

		# Create Slack messages for each author using the provided articles' details
        formatted_messages = make_slack_msg(authors, articles)
        logging.log(MIN, f"Formatted messages for {len(authors)} authors.")
            
        for formatted_message in formatted_messages:
    		# Send each of the formatted messages to the configured Slack channel
    		# If both args are True, it means we want to send a test message with the fetched pubs.
    		# Therefore we are going to send a first warning that this is a test message and not the real fetch.
            if args.test_fetching == args.test_message == True:
                test_header = '!!! This is a test message !!!'
                formatted_message = f'```\n{test_header}\n{formatted_message}\n```'
                
            send_to_slack(ch_name, formatted_message, token)

if __name__ == "__main__":
    main()



