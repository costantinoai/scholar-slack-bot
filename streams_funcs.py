#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Fri Oct 20 17:02:03 2023

@author: costantino_ai
"""
import os
import logging
from log_config import MIN, STANDARD
from helper_funcs import confirm_temp_cache, add_new_author_to_json, convert_json_to_tuple
from fetch_scholar import fetch_from_json, fetch_pubs_dictionary
from slack_bot import make_slack_msg, send_to_slack

def update_cache_only(args):
    """Move fetched publications from the temp directory to cache.
    
    Args:
        temp_cache_path (str): Path to the temporary cache.
        cache_path (str): Path to the actual cache.
    """
    confirm_temp_cache(args.temp_cache_path, args.cache_path)
    logging.log(MIN, "Fetched pubs successfully moved to cache and temporary cache cleared.")


def test_fetch_and_message(args, ch_name, token):
    """
    Test fetching of articles and send formatted messages to a Slack channel.
    
    This function is used when:
    - Not adding a scholar by ID (`add_scholar_id` is not provided).
    - Not updating the cache only (`update-cache` is False).
    - Both `test_fetching` and `test_message` are True, indicating a desire 
      to test fetch and send a message for the fetched data.
    
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
    logging.log(MIN, f"Formatted test messages for {len(authors)} authors.")
    
    test_header = '!!! This is a test message !!!'
    success = True  # To track if all messages are sent successfully.
    
    # Loop through each formatted message and send it to Slack.
    for formatted_message in formatted_messages:
        formatted_message = f'```\n{test_header}\n{formatted_message}\n```'
        response_json = send_to_slack(ch_name, formatted_message, token)
        
        # Update success status based on the response.
        if not response_json['ok']:
            success = False
            e = response_json['error']
            # It might be useful to log failures as they happen.
            logging.warning(f"Failed to send a test message due to: {e}")
        
    # Log overall success or failure.
    if success:
        logging.log(MIN, "All test messages sent successfully.")
    else:
        logging.error("There was a problem sending one or more test messages.")
        
        
def regular_fetch_and_message(args, ch_name, token):
    """
    Regularly fetch articles and send messages to a Slack channel.
    If all messages are sent successfully, the cache will be updated.
    If any message fails, the temporary cache will be cleared.

    This function operates under the following conditions:
    - Not adding a scholar by ID (`add_scholar_id` is not provided).
    - Not updating the cache only (`update-cache` is False).
    - Both `test_fetching` and `test_message` are False.

    Args:
        args (argparse.Namespace): The argument object.
        ch_name (str): The channel name to send messages to.
        token (str): The token used for communication with Slack.

    """
    
    # Fetch all authors' details from the provided path.
    authors, articles = fetch_from_json(args)
    
    # Convert fetched details into messages suitable for Slack.
    formatted_messages = make_slack_msg(authors, articles)
    logging.log(MIN, f"Formatted messages for {len(authors)} authors.")
    
    # Initialize a success flag to track message sending process.
    success = True
    error_message = None  # To store any error encountered.
    
    # Send each formatted message to Slack.
    for formatted_message in formatted_messages:
        response_json = send_to_slack(ch_name, formatted_message, token)
        
        # If any message fails, update the success flag and store the error.
        if not response_json['ok']:
            success = False
            error_message = response_json.get('error', 'Unknown error')
            logging.warning(f"Failed to send a message due to: {error_message}")
    
    # Handle post-message actions based on the success flag.
    if success:
        confirm_temp_cache(args.temp_cache_path, args.cache_path)
        logging.log(MIN, "Fetched publications successfully moved to cache. Temporary cache cleared.")
    else:
        # Clear the temporary cache due to the failure in sending messages.
        try:
            os.rmdir(args.temp_cache_path)
            logging.info("Temporary cache cleared due to a message send failure.")
        except Exception as e:
            logging.warning(f"Failed to clear the temporary cache. Reason: {str(e)}")
        
        logging.error(f"Problem sending one or more messages to Slack. Cache was not updated. Error: {error_message}")

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
    try:
        os.rmdir(args.cache_path)
        logging.log(STANDARD, f"Deleted old cache at {args.cache_path}")
    except Exception as e:  # Handle specific exception to avoid broad except.
        logging.error(f"Failed to delete cache at {args.cache_path}. Reason: {str(e)}")

    # Refetch all the author and publication details.
    _ = fetch_from_json(args)

    # Update the cache with newly fetched data.
    update_cache_only(args)
    logging.log(MIN, "Re-fetched all publications. Data successfully moved to cache and temporary cache cleared.")

def add_scholar_and_fetch(args):
    """
    Add a new scholar's data, fetch their publications, and update the cache.
    
    This function adds a new scholar to the specified JSON, fetches their publications, 
    and updates the cache with the newly fetched data.
    
    Parameters:
    - args: Arguments containing paths for authors' JSON, cache, temp cache, and other 
            relevant data, as well as the scholar ID of the new author.
    
    Returns:
    None
    """
    
    # Check if an author's JSON file with the same ID already exists in the cache path.
    json_filename = f"{args.add_scholar_id}.json"
    json_filepath = os.path.join(args.cache_path, json_filename)
    
    if os.path.exists(json_filepath):
        logging.log(MIN, f"Author with scholar ID {args.add_scholar_id} is already in the authors JSON file. Fetching is skipped.")
        return

    # Add the new author's data to the authors' JSON file and get their dictionary representation.
    author_dict = add_new_author_to_json(args.authors_path, args.add_scholar_id)
    logging.log(STANDARD, f"Added new author with scholar ID {args.add_scholar_id} to authors' JSON.")

    # Create a single-entry list with the new author's data for subsequent processing.
    authors_json = [author_dict]

    # Convert the retrieved JSON data of the new author into a tuple representation for easier handling.
    authors = convert_json_to_tuple(authors_json)
    logging.log(STANDARD, "Converted new author's JSON data into tuple representation.")
    
    # Fetch publication details for the new author from the scholarly database.
    articles = fetch_pubs_dictionary(authors, args)
    logging.log(MIN, f"Fetched {len(articles)} articles for the new author.")
    
    # Update the cache with the newly fetched data for the new author.
    update_cache_only(args)
    logging.log(MIN, "Added author to JSON. Cache successfully updated with new author's data.")