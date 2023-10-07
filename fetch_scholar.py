#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Wed Sep  6 14:06:56 2023

@author: costantino_ai
"""

import json
import os
import platform
from scholarly import scholarly
from concurrent.futures import ThreadPoolExecutor
import logging
import time
from tqdm import tqdm  # Progress bar library

from helper_funcs import clean_pubs
from log_config import MIN, STANDARD

# Get global debug flag
DEBUG = False

def set_debug(state):
    global DEBUG
    DEBUG = state


def fetch_publication_details(pub):
    """
    Fetch and fill details for a given publication.

    Parameters:
        pub (dict): The scholarly publication dictionary to fetch details for.

    Returns:
        dict: A scholarly publication dictionary populated with additional details.

    Example:
        publication = fetch_publication_details(some_scholarly_dict)
    """
    # Log fetching details only when level is MIN
    logging.log(STANDARD, f"Fetching details for publication {pub['bib']['title']}.")
    try:
        return scholarly.fill(pub)
    except Exception as e:
        logging.error(f"Error fetching publication: {e}")
        return None

def fetch_publications_by_id(author_id, output_folder, to_year=2023, exclude_not_cited_papers=False):
    """
    Fetches publications for an author using their Google Scholar ID and caches the data.

    Parameters:
        author_id (str): Google Scholar ID of the author.
        output_folder (str): Directory where the publication cache will be stored.
        to_year (int, optional): Fetch articles up to this year. Defaults to 2023.
        exclude_not_cited_papers (bool, optional): If True, exclude uncited papers. Defaults to False.

    Returns:
        list: Filtered, sorted, and sliced list of relevant publications.

    Raises:
        FileNotFoundError: If the output folder doesn't exist.
        Exception: For unexpected errors during the process.

    Example:
        publications = fetch_publications_by_id("some_google_scholar_id", "/path/to/output/folder")
    """

    # Check if the specified output folder exists
    if not os.path.exists(output_folder):
        logging.error(f"Output folder '{output_folder}' does not exist.")
        raise FileNotFoundError(f"Output folder '{output_folder}' not found.")

    # Log the initiation of the fetch process
    logging.log(STANDARD, f"Initiating fetch for author ID: {author_id}")

    # Construct the path for the cached publications for the author
    cache_path = os.path.join(output_folder, f"{author_id}.json")

    # Fetch author details from Google Scholar
    try:
        author = scholarly.search_author_id(author_id)
        author = scholarly.fill(author)
        author_pubs = author['publications']
    except Exception as e:
        logging.error(f"Error fetching details for author ID: {author_id}. Error: {e}")
        raise

    # Load cached publications, if available
    cached_pubs = []
    if os.path.exists(cache_path):
        logging.log(STANDARD, f"Attempting to load cache for author {author_id}.")
        try:
            with open(cache_path, "r") as f:
                cached_pubs = json.load(f)
        except Exception as e:
            logging.warning(f"Failed to load cache for author {author_id}. Error: {e}")

    # Extract titles from cached publications for comparison
    cached_titles = [pub['bib']['title'] for pub in cached_pubs]

    # Filter the author's publications to exclude cached ones and those before the desired year
    pubs_to_fetch = [item for item in author_pubs if item['bib']['title'] not in cached_titles and item['bib']['pub_year'] >= to_year]

    # List to store fetched publications
    fetched_pubs = []

    # Display tqdm progress bar if logging level is set to MIN
    show_progress = logging.getLogger().getEffectiveLevel() == MIN

    # Determine the iterable based on whether to show progress
    iterable = tqdm(pubs_to_fetch, desc="\tFetching new publications..") if show_progress else pubs_to_fetch

    # Define maximum number of retry attempts if fetching fails
    max_retries = 5
    
    # Define delay (in seconds) between each retry attempt
    retry_delay = 60
    
    # Iterate through each publication that needs to be fetched
    for pub in iterable:
    
        # Flag to determine if the publication was successfully fetched
        success = False
    
        # Counter to keep track of the number of retry attempts made
        retries = 0
    
        # Retry fetching until either successful or max retries are reached
        while not success and retries < max_retries:
            try:
                # Use ThreadPoolExecutor to fetch publication details concurrently
                with ThreadPoolExecutor() as executor:
                    # Fetch details for the current publication and store the result
                    fetched_pub = next(executor.map(fetch_publication_details, [pub]))
                
                # If successfully fetched, add the publication to the fetched_pubs list
                fetched_pubs.append(fetched_pub)
                
                # Update success flag
                success = True
    
            # Handle exceptions during the fetch attempt
            except Exception as e:
                # Increment retry counter
                retries += 1
                
                # Log a warning message with details of the failed fetch attempt
                logging.warning(f"Error fetching '{pub['bib']['title']}'. Attempt {retries}/{max_retries}. Error: {e}")
                
                # If not reached the max retry limit, wait for a defined delay before retrying
                if retries < max_retries:
                    logging.info(f"Pausing for {retry_delay} seconds before retrying...")
                    time.sleep(retry_delay)
    
        # If max retries are reached and publication is still not fetched, log an error
        if not success:
            logging.error(f"Failed fetching '{pub['bib']['title']}' after {max_retries} attempts. Skipping.")
    
    # Try to cache (save) the fetched publications
    try:
        # Open the cache file in write mode
        with open(cache_path, "w") as f:
            # Save both newly fetched and previously cached publications to the file
            # Check if DEBUG_FLAG is set
            if DEBUG_FLAG:
                json.dump(cached_pubs, f, indent=4)
            else:
                json.dump(fetched_pubs + cached_pubs, f, indent=4)        
                # Log a message indicating successful caching
                logging.log(STANDARD, f"Publications for author {author_id} cached.")
    
    # Handle exceptions during caching
    except Exception as e:
        # Log an error message with details of the caching failure
        logging.error(f"Error caching publications for {author_id}. Error: {e}")
    
    # Process the fetched publications (e.g., filter, sort) using a helper function
    clean_pubs_list = clean_pubs(fetched_pubs, to_year, exclude_not_cited_papers)
    
    # Return the processed list of publications
    return clean_pubs_list

def fetch_pubs_dictionary(authors, output_dir="./src"):
    """
    Fetch publications for a list of authors for the current year, 
    and store them in a cache. Only non-duplicate publications compared 
    to the cache are returned.
    
    :param authors: List of tuples containing author name and author ID.
    :param output_dir: Directory where the cache file will be saved/loaded from.
    :return: A dictionary containing non-duplicate publications.
    """

    current_year = time.strftime("%Y")  # Get the current year
    params = {
        "authors": authors,
        "to_year": current_year,
        "output_root": output_dir,
    }

    # Determine cache directory.
    if params["output_root"] is None:
        if platform.system() == "Windows":
            desktop = os.path.join(os.path.join(os.environ["USERPROFILE"]), "Desktop")
        else:
            desktop = os.path.join(os.path.expanduser("~"), "Desktop")
        output_folder = os.path.join(desktop, "googleapi_cache")
    else:
        output_folder = os.path.join(params["output_root"], "googleapi_cache")

    # Ensure the output directory exists.
    if not os.path.exists(output_folder):
        logging.log(MIN, f"Creating output folder at {output_folder}.")
        os.makedirs(output_folder)

    # Fetch the publications of the current year.
    authors_publications = []
    total_authors = len(params["authors"])

    for i, (author, author_id) in enumerate(params["authors"]):
        logging.log(MIN, f"Progress: {i+1}/{total_authors} - {author}")
        author_publications = fetch_publications_by_id(
            author_id,
            output_folder,
            to_year=params["to_year"]
        )
        authors_publications = authors_publications + author_publications
       
    return authors_publications
