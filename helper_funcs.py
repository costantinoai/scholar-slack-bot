#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Sat Oct  7 14:04:23 2023

@author: costantino_ai
"""
import os
import shutil
import logging
import json
from scholarly import scholarly

logger = logging.getLogger(__name__)


def delete_temp_cache(args):
    if os.path.isdir(args.temp_cache_path):
        try:
            shutil.rmtree(args.temp_cache_path)
            logger.debug("Temporary cache cleared.")
        except Exception as e:
            logger.error(
                f"Failed to delete cache at {args.temp_cache_path}. Please delete the folder manually."
            )
            logger.error(f"Reason: {str(e)}")
    else:
        logger.debug(f"Temporary cache not found at {args.temp_cache_path}.")


def confirm_temp_cache(temp_cache_path="./src/temp_cache", old_cache_path="./src/googleapi_cache"):
    """
    Moves the contents of the temporary cache directory to the old cache directory.

    After ensuring that both paths exist, this function moves every file from the
    temp_cache_path to the old_cache_path, overwriting files with the same name.
    Once all files are moved, the temporary cache directory is deleted.

    Parameters:
    - temp_cache_path (str): Path to the temporary cache directory.
    - old_cache_path (str): Path to the old cache directory (to be updated with new files).

    Returns:
    None
    """

    # Check if temp_cache_path exists
    if not os.path.exists(temp_cache_path):
        logger.warning(
            f"Temporary cache path '{temp_cache_path}' does not exist. New articles are NOT saved to cache."
        )
        return

    # Check if old_cache_path exists
    if not os.path.exists(old_cache_path):
        logger.info(f"Cache path '{old_cache_path}' does not exist. Creating.")
        os.makedirs(old_cache_path, exist_ok=True)

    # Log the beginning of the process
    logger.debug("Starting to move files from temporary cache to old cache.")

    # Iterate over every file in the temporary cache path
    for file_name in os.listdir(temp_cache_path):
        source_path = os.path.join(temp_cache_path, file_name)
        destination_path = os.path.join(old_cache_path, file_name)

        # Move file from temporary cache to old cache, overwriting if necessary
        shutil.move(source_path, destination_path)
        logger.debug(f"Moved '{file_name}' from temporary cache to old cache.")

    # After moving all files, remove the temporary cache directory
    os.rmdir(temp_cache_path)
    logger.debug(f"Temporary cache path '{temp_cache_path}' has been deleted.")

    return


def has_conflicting_args(args):
    """Check if any of the conflicting arguments are set to True or have values.

    Args:
        args (argparse.Namespace): The argument object.

    Returns:
        bool: True if any conflicting arguments are set, otherwise False.
    """

    if args.test_message:
        return any([args.add_scholar_id, args.update_cache])

    if args.add_scholar_id:
        return any([args.test_message, args.update_cache])

    if args.update_cache:
        return any([args.test_message, args.add_scholar_id])

    return False


def add_new_author_to_json(authors_path, scholar_id):
    """
    Add a new author to the existing authors JSON file using the provided Google Scholar ID.

    Parameters:
    - authors_path (str): Path to the authors JSON file.
    - scholar_id (str): Google Scholar ID of the author to be added.

    Returns:
    None

    Raises:
    - Exception: If an error occurs while fetching the author using the `scholarly` module.
    """

    logger.info(f"Adding author ID {scholar_id} to {authors_path}.")
    # Get the old authors json
    with open(authors_path, "r") as f:
        old_authors_json = json.load(f)

    # Fetch the author's details from Google Scholar using the provided ID
    try:
        author_fetched = scholarly.search_author_id(scholar_id)
    except Exception as e:
        logger.error(f"Error encountered: {e}")
        raise  # this will raise the caught exception and stop the code

    # Extract the name of the author and create a dictionary entry
    author_name = author_fetched["name"]
    author_dict = {"name": author_name, "id": scholar_id}

    # Append the new author's details to the existing list
    # Check if the author with the given scholar_id already exists in the old_authors_json
    if not any(author["id"] == scholar_id for author in old_authors_json):
        # Append the new author's details to the existing list
        old_authors_json.append(author_dict)
    else:
        # Handle the case where the author already exists, e.g., log a message
        logger.info(
            f"Author with ID {scholar_id} already exists in the list and will not be added again."
        )

    try:
        # Save the updated list of authors back to the JSON file
        with open(authors_path, "w") as f:
            json.dump(old_authors_json, f, indent=4)
        logger.debug(f"Author {author_name} added to {authors_path}.")
    except:
        logger.error(f"There was an error adding {author_name} to {authors_path}.")

    return author_dict


def convert_json_to_tuple(authors_json: list) -> list:
    """
    Converts the authors' details from a JSON file into a Python tuple representation.

    Parameters:
    - authors_path (str): Path to the authors' JSON file.

    Returns:
    - str: A Python string representation of authors as a list of tuples.
    """

    authors_list = []

    # Iterate through each author in the JSON
    for author in authors_json:
        # Formatting the authors as tuples
        author_tuple = (author["name"], author["id"])
        authors_list.append(author_tuple)

    return authors_list


def get_authors_json(authors_path: str) -> list:
    """
    Retrieves authors' details from a JSON file.

    Parameters:
    - authors_path (str): Path to the authors' JSON file.

    Returns:
    - list[dict]: List of authors in JSON format.
    """
    with open(authors_path, "r") as file:
        authors = json.load(file)
    return authors


def clean_pubs(fetched_pubs, from_year=2023, exclude_not_cited_papers=False):
    """
    Filters and processes the fetched publications based on specified criteria.

    Parameters:
        fetched_pubs (list): List of raw publication data fetched from Google Scholar.
        from_year (int, optional): Minimum year to include publications. Defaults to 2023.
        exclude_not_cited_papers (bool, optional): If True, excludes papers that haven't been cited. Defaults to False.

    Returns:
        list: A list of dictionaries containing cleaned and processed publication data.

    Example:
        cleaned_publications = clean_pubs(raw_publications, 2020, True)
    """

    # Set to keep track of seen titles to avoid double publications
    seen_titles = set()

    # Initialize a list to hold publications that match the specified criteria
    relevant_pubs = []

    for pub in fetched_pubs:
        # Check if the publication meets the year criterion and hasn't been seen before
        if (
            pub["bib"].get("pub_year")  # if the publication has a 'year' field
            and int(pub["bib"]["pub_year"]) <= int(from_year)  # if the pub year is >= from_year
            and (
                not exclude_not_cited_papers or pub["num_citations"] > 0
            )  # if exclude_not_cited_papers is True, then we select only papers with citations
            and pub["bib"]["title"] not in seen_titles
        ):  # only add the pub if it is the only pub with this title (avoid dupes)

            # Add the title to the seen set
            seen_titles.add(pub["bib"]["title"])

            # Append the relevant publication to the list
            relevant_pubs.append(
                {
                    "title": pub["bib"]["title"],
                    "authors": pub["bib"]["author"].replace(" and ", ", "),
                    "abstract": pub["bib"].get("abstract", "No abstract available"),
                    "year": pub["bib"]["pub_year"],
                    "num_citations": pub["num_citations"],
                    "journal": pub["bib"]["citation"],
                    "pub_url": pub["pub_url"] if "pub_url" in pub.keys() else None,
                }
            )

    # Sort the list of relevant publications by the number of citations in descending order
    sorted_pubs = sorted(relevant_pubs, key=lambda x: x["num_citations"], reverse=True)

    # Return the cleaned and sorted list of publications
    return sorted_pubs


def ensure_output_folder(output_folder):
    """
    Checks for the existence of the output folder, and if it doesn't exist, creates it.

    Raises:
    - Exception: If there's any error during folder creation.
    """
    if not os.path.exists(output_folder):  # Check if directory exists
        logger.info(f"Output folder '{output_folder}' does not exist. Creating it.")
        os.makedirs(output_folder)  # Create directory
