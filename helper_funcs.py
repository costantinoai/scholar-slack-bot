#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Sat Oct  7 14:04:23 2023

@author: costantino_ai
"""
import json
from scholarly import scholarly

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

    # Get the old authors json
    with open(authors_path, "r") as f:
        old_authors_json = json.load(f)

    # Fetch the author's details from Google Scholar using the provided ID
    try:
        author_fetched = scholarly.search_author_id(scholar_id)
    except Exception as e:
        print(f"Error encountered: {e}")
        raise  # this will raise the caught exception and stop the code

    # Extract the name of the author and create a dictionary entry
    author_name = author_fetched['name']
    author_dict = {
        'name': author_name,
        'id': scholar_id
    }

    # Append the new author's details to the existing list
    old_authors_json.append(author_dict)

    # Save the updated list of authors back to the JSON file
    with open(authors_path, "w") as f:
        json.dump(old_authors_json, f, indent=4)
        
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
    with open(authors_path, 'r') as file:
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
        if (pub["bib"].get("pub_year") # if the publication has a 'year' field
        and int(pub["bib"]["pub_year"]) <= int(from_year) # if the pub year is >= from_year
        and (not exclude_not_cited_papers or pub["num_citations"] > 0) # if exclude_not_cited_papers is True, then we select only papers with citations
        and pub["bib"]["title"] not in seen_titles): # only add the pub if it is the only pub with this title (avoid dupes)

            # Add the title to the seen set
            seen_titles.add(pub["bib"]["title"])

            # Append the relevant publication to the list
            relevant_pubs.append({
                "title": pub["bib"]["title"],
                "authors": pub["bib"]["author"].replace(" and ", ", "),
                "abstract": pub["bib"].get("abstract", "No abstract available"),
                "year": pub["bib"]["pub_year"],
                "num_citations": pub["num_citations"],
                "journal": pub["bib"]["citation"],
                "pub_url": pub["pub_url"] if "pub_url" in pub.keys() else None,
            })

    # Sort the list of relevant publications by the number of citations in descending order
    sorted_pubs = sorted(relevant_pubs, key=lambda x: x["num_citations"], reverse=True)
    
    # Return the cleaned and sorted list of publications
    return sorted_pubs

