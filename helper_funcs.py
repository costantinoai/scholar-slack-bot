#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Sat Oct  7 14:04:23 2023

@author: costantino_ai
"""
import json

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

def clean_pubs(fetched_pubs, to_year=2023, exclude_not_cited_papers=False):
    """
    Filters and processes the fetched publications based on specified criteria.
    
    Parameters:
        fetched_pubs (list): List of raw publication data fetched from Google Scholar.
        to_year (int, optional): Minimum year to include publications. Defaults to 2023.
        exclude_not_cited_papers (bool, optional): If True, excludes papers that haven't been cited. Defaults to False.
    
    Returns:
        list: A list of dictionaries containing cleaned and processed publication data.
    
    Example:
        cleaned_publications = clean_pubs(raw_publications, 2020, True)
    """
    
    # Initialize a list to hold publications that match the specified criteria
    relevant_pubs = [
        {
            # Extract and store the title of the publication
            "title": pub["bib"]["title"],
            
            # Extract authors, replace 'and' with ', ', and store them
            "authors": pub["bib"]["author"].replace(" and ", ", "),
            
            # Extract and store the abstract, or provide a default if it doesn't exist
            "abstract": pub["bib"].get("abstract", "No abstract available"),
            
            # Extract and store the publication year
            "year": pub["bib"]["pub_year"],
            
            # Extract and store the number of citations
            "num_citations": pub["num_citations"],
            
            # Extract and store the citation (often represents the journal or conference)
            "journal": pub["bib"]["citation"],
            
            # Extract and store the URL for the publication, or None if not present
            "pub_url": pub["pub_url"] if "pub_url" in pub.keys() else None,
        }
        
        # Loop through each publication in fetched_pubs
        for pub in fetched_pubs
        
        # Only include publications that have a specified publication year and meet the year criterion
        # Optionally exclude publications that haven't been cited based on the exclude_not_cited_papers flag
        if pub["bib"].get("pub_year")
        and int(pub["bib"]["pub_year"]) <= int(to_year)
        and (not exclude_not_cited_papers or pub["num_citations"] > 0)
    ]

    # Sort the list of relevant publications by the number of citations in descending order
    sorted_pubs = sorted(relevant_pubs, key=lambda x: x["num_citations"], reverse=True)
    
    # Return the cleaned and sorted list of publications
    return sorted_pubs
