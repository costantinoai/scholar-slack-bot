#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Sat Oct  7 02:46:59 2023

@author: costantino_ai
"""

import sys
import argparse

from slack_bot import format_pub_message, send_to_slack, get_slack_config, format_authors_message
from fetch_scholar import fetch_pubs_dictionary, set_debug
from helper_funcs import convert_json_to_tuple, get_authors_json

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
    Main execution function for the script.
    
    - Parses command-line arguments.
    - Retrieves Slack configuration.
    - Converts authors' JSON data into tuple representation.
    - Fetches publication dictionary for each author.
    - Formats each article for Slack and sends it.
    """
    print("Initializing...")
    
    # Determine if the script is run from the IDE or command-line
    if len(sys.argv) > 1:
        # Running from command line: Parse command-line arguments
        args = get_args()
    else:
        # Running from IDE: Use hardcoded configurations
        args = {}
        args['slack_config_path'] = './src/slack.config'
        if DEBUG_FLAG:
            args['authors_path'] = './src/authors_short.json'  # Adjusted for debug
            args['debug'] = True
        else:
            args['authors_path'] = './src/authors.json'  # Default
            args['debug'] = False
            
    # Set the debug state in fetch_scholar.py
    set_debug(args['debug'])

    # Fetching Slack configuration from the given path
    slack_config = get_slack_config(args['slack_config_path'])
    
    token = slack_config['api_token']
    ch_name = slack_config['channel_name']
    
    # Fetching authors' details from the given path
    authors_json = get_authors_json(args['authors_path'])
    
    # Convert authors' JSON data into tuple representation
    authors = convert_json_to_tuple(authors_json)
    
    # Fetch publication dictionary for each author
    articles = fetch_pubs_dictionary(authors)
    
    def make_slack_msg(authors: list, articles: list) -> list:
        authors_msg = format_authors_message(authors)
        pubs_messages = ['List of publications since my last check:\n'] + [format_pub_message(article) for article in articles]
        formatted_messages = [authors_msg] + pubs_messages
        return formatted_messages
    
    # Make new slack messages (one per author)
    formatted_messages = make_slack_msg(authors, articles)
    
    # Send each formatted message to Slack
    for formatted_message in formatted_messages:
        send_to_slack(ch_name, formatted_message, token)
        
# Define a DEBUG_FLAG at the top of your script, just after imports
DEBUG_FLAG = True

if __name__ == "__main__":
    main()



