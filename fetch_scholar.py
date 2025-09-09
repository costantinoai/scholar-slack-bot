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
from tqdm import tqdm

from helper_funcs import clean_pubs, get_authors_json, convert_json_to_tuple, ensure_output_folder

logger = logging.getLogger(__name__)

MAX_RETRIES = 3
DELAYS = [20, 40, 60]


def fetch_from_json(args, idx=None):
    """
    Fetch author and publication details based on a specified index.

    This function retrieves author details from a given JSON path, converts this
    data into a tuple representation, and fetches publication details for a subset
    of these authors from a scholarly database. The subset size is determined by the
    provided index (idx).

    Parameters:
    - args: Arguments containing the path to the authors' JSON and other relevant data.
    - idx (int, optional): The number of authors for which to fetch publications.
      Defaults to None, which fetches for all authors.

    Returns:
    - tuple: A tuple containing:
        1. A list of selected authors' details.
        2. A dictionary with publication details for each selected author.
    """

    # Retrieve authors' details from the specified JSON path.
    authors_json = get_authors_json(args.authors_path)
    logger.debug(f"Fetched authors' details from {args.authors_path}.")

    # Convert the retrieved JSON data into a tuple representation for easier handling.
    authors = convert_json_to_tuple(authors_json)
    logger.debug("Converted authors' JSON data into tuple representation.")

    # Determine the number of authors to process.
    if idx is not None:
        if idx > len(authors):
            logger.debug(
                f"Requested {idx} authors but only {len(authors)} available. Using all available authors."
            )
            idx = len(authors)
    else:
        idx = len(authors)

    if idx == 0:
        logger.error("No authors listed in the authors.json file.")
        return

    # Fetch publication details for the determined number of authors from the scholarly database.
    articles = fetch_pubs_dictionary(authors[:idx], args)
    logger.info(f"Fetched {len(articles)} articles for the provided authors.")
    logger.info("Publications fetched correctly")

    return authors[:idx], articles


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
    # Log fetching details only when logging level allows for debug information
    logger.debug(f"Fetching details for publication {pub['bib']['title']}.")
    try:
        return scholarly.fill(pub)
    except Exception as e:
        logger.error(f"Error fetching publication: {e}")
        return None


def fetch_author_details(author_id):
    """
    Fetches author details using the scholarly library.

    Returns:
    - dict: Details of the author.

    Raises:
    - Exception: If there's any error during the fetching process.
    """
    try:
        author = scholarly.search_author_id(author_id)
        author = scholarly.fill(author)
        return author["publications"]
    except Exception as e:
        logger.error(f"Error fetching author details for ID: {author_id}. {e}")
        raise e


def load_cache(author_id, output_folder):
    """
    Loads cached publications details from the file system, if available.

    Returns:
    - list: List of cached publications or an empty list if cache is not present or corrupted.

    Raises:
    - Exception: If there's any error during the loading process.
    """
    # Load cached publications if they exist
    cache_path = os.path.join(output_folder, f"{author_id}.json")  # Determine the cache file path
    if os.path.exists(cache_path):
        logger.debug(f"Cache exists for author {author_id}. Loading...")
        try:
            with open(cache_path, "r") as f:
                return json.load(f)
        except Exception as e:
            logger.warning(f"Error loading cache for author {author_id}. {e}")
            return []
    else:
        logger.debug(f"No cache for author {author_id}. Fetching all.")
        return []


def get_pubs_to_fetch(author_pubs, cached_pubs, from_year, args):
    """
    Determines the publications that need to be fetched based on cached data and the specified year.

    Returns:
    - list: List of publications to fetch.
    """
    test_fetching = getattr(args, "test_fetching", False)
    if test_fetching:
        logging.warning(f"--test_fetching flag True. Loading only cached papers < {str(from_year)}")

    # Extract titles from cached publications, only titles before from_year if test_fetching is True
    cached_titles = (
        [pub["bib"]["title"] for pub in cached_pubs]
        if not test_fetching
        else [
            pub["bib"]["title"]
            for pub in cached_pubs
            if "pub_year" in pub["bib"].keys() and int(pub["bib"]["pub_year"]) < int(from_year)
        ]
    )

    if args.update_cache == True:
        # Do not filter pubs. If this is True, it means we want to update the cache. So we fetch
        # all the author's pubs for the last year
        logger.info("--update_cache flag True. Re-fetching author's pubs and generating new cache.")
        pubs_to_fetch = [
            item
            for item in author_pubs
            if "pub_year" in item["bib"].keys() and int(item["bib"]["pub_year"]) >= int(from_year)
        ]
    else:
        # Filter out publications to fetch based on title and year, only titles >= from_year if test_fetching == True
        pubs_to_fetch = [
            item
            for item in author_pubs
            if not any(item["bib"]["title"].split(' …')[0] in title for title in cached_titles) # this handles the titles that are cut with ' …'
            # if item["bib"]["title"] not in cached_titles # this was wrong.. longer titles get cut with ' …' so they get loaded again every time if we use this
            and "pub_year" in item["bib"].keys()
            and int(item["bib"]["pub_year"]) >= int(from_year)
        ]

    return pubs_to_fetch


def fetch_selected_pubs(pubs_to_fetch):
    """
    Fetches selected publications using parallel processing.

    Parameters:
    - pubs_to_fetch (list): List of publications to fetch.

    Returns:
    - list: List of fetched publications.

    Raises:
    - Exception: If there's any error during the fetching process.
    """
    # Loop through the retry attempts
    for retry in range(MAX_RETRIES):
        try:
            # Use a ThreadPoolExecutor to parallelize the fetching of publications
            with ThreadPoolExecutor() as executor:
                # Check if logging level is set to INFO. If so, display a progress bar
                if logger.getEffectiveLevel() == logging.INFO and pubs_to_fetch != []:
                    fetched_pubs = list(
                        tqdm(
                            # Execute fetch_publication_details for each item in pubs_to_fetch concurrently
                            executor.map(fetch_publication_details, pubs_to_fetch),
                            total=len(pubs_to_fetch),
                            desc="Fetching publications",
                        )
                    )
                elif logger.getEffectiveLevel() != logging.INFO and pubs_to_fetch != []:
                    # If not using a progress bar, simply map the function across the publications
                    fetched_pubs = list(executor.map(fetch_publication_details, pubs_to_fetch))
                else:
                    logger.debug("No new publications. Skipping..")
                    fetched_pubs = []
            # Return the fetched publications
            return fetched_pubs
        except Exception as e:
            # If an exception occurs and it's not the last retry attempt, log a warning and delay
            if retry < MAX_RETRIES - 1:
                logger.warning(
                    f"Error fetching publications. Retrying in {DELAYS[retry]} seconds. Error: {e}"
                )
                time.sleep(DELAYS[retry])  # Delay for a specified amount of time before retrying
            else:
                # If it's the last retry attempt, log an error and return an empty list
                logger.error(f"Max retries reached. Exiting fetch process. Error: {e}")
                return []


def save_updated_cache(fetched_pubs, cached_pubs, author_id, output_folder, args):
    """
    Updates the cache by saving the combined list of fetched and cached publications.

    Parameters:
    - fetched_pubs (list): List of newly fetched publications.
    - cached_pubs (list): List of previously cached publications.
    - output_folder (str): Directory to save the cache.
    """
    cache_path = os.path.join(output_folder, f"{author_id}.json")
    logger.debug(f"Updating cache for author {author_id}.")
    with open(cache_path, "w") as f:
        combined_pubs = fetched_pubs + cached_pubs if not args.update_cache else fetched_pubs
        json.dump(combined_pubs, f, indent=4)


def fetch_publications_by_id(
    author_id, output_folder, args, from_year=2023, exclude_not_cited_papers=False
):
    """
    Fetches and caches publications of a specific author using their Google Scholar ID.

    Parameters:
    - author_id (str): Google Scholar ID of the author.
    - output_folder (str): Directory where the fetched publications will be cached.
    - from_year (int, optional): Limit publications to this year. Defaults to 2023.
    - exclude_not_cited_papers (bool, optional): If True, only return papers that have been cited. Defaults to False.

    Returns:
    - list: A list of publications, filtered and processed based on given parameters.

    Raises:
    - FileNotFoundError: If the specified output folder doesn't exist.
    - Exception: For unexpected errors during the fetch process.

    How it works:
    1. Check if the output folder exists. If not, it creates it.
    2. Fetch author details from Google Scholar.
    3. Load cached publications if available.
    4. Filter out already cached publications.
    5. Fetch details of the new publications in parallel.
    6. Cache the updated list of publications to a temporary folder.
    7. Process the fetched list based on parameters (e.g., year, citations).

    Note:
    - This function uses the 'scholarly' library to interact with Google Scholar.
    - Fetching too many papers in a short time might lead to a temporary block by Google Scholar.
    """
    # Make temp dir path
    temp_output_folder = os.path.join(output_folder, "tmp")
    # Check if the output folder exists or create it
    ensure_output_folder(temp_output_folder)
    # Fetch author details from Google Scholar
    author_pubs = fetch_author_details(author_id)
    # Load cached publications if available
    cached_pubs = load_cache(author_id, output_folder)
    # Determine the list of publications to fetch
    pubs_to_fetch = get_pubs_to_fetch(author_pubs, cached_pubs, from_year, args)
    # Fetch selected publications
    fetched_pubs = fetch_selected_pubs(pubs_to_fetch)
    # Update cache with newly fetched publications
    if not getattr(args, "test_fetching", False):
        save_updated_cache(fetched_pubs, cached_pubs, author_id, temp_output_folder, args)
    # Return cleaned list of publications
    return clean_pubs(fetched_pubs, from_year, exclude_not_cited_papers)


def fetch_pubs_dictionary(authors, args, output_dir="./src"):
    """
    Fetch publications for a list of authors for the current year,
    and store them in a cache. Only non-duplicate publications compared
    to the cache are returned.

    :param authors: List of tuples containing author name and author ID.
    :param output_dir: Directory where the cache file will be saved/loaded from.
    :return: A dictionary containing non-duplicate publications.
    """

    current_year = time.strftime("%Y")  # Get the current year
    test_fetching = getattr(args, "test_fetching", False)
    params = {
        "authors": authors if not test_fetching else authors[:2],
        "from_year": current_year,
        "output_root": output_dir,
    }

    # Determine cache directory
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
        logger.info(f"Creating output folder at {output_folder}.")
        os.makedirs(output_folder)

    # Fetch the publications of the current year.
    authors_publications = []
    total_authors = len(params["authors"])

    for i, (author, author_id) in enumerate(params["authors"]):
        logger.info(f"Progress: {i+1}/{total_authors} - {author}")
        author_publications = fetch_publications_by_id(
            author_id, output_folder, args, from_year=params["from_year"]
        )
        authors_publications = authors_publications + author_publications

    return authors_publications
