#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Wed Sep  6 14:06:56 2023

@author: costantino_ai
"""

import os
import platform
import sqlite3
from scholarly import scholarly
import logging
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading
from tqdm import tqdm

from helper_funcs import (
    clean_pubs,
    get_authors_json,
    convert_json_to_tuple,
    ensure_output_folder,
    migrate_legacy_files,
)

logger = logging.getLogger(__name__)

MAX_RETRIES = 3
DELAYS = [20, 40, 60]
DEFAULT_SRC_DIR = "./src"
DB_NAME = "publications.db"
DEFAULT_DB_DIR = DEFAULT_SRC_DIR
DEFAULT_DB_PATH = os.path.join(DEFAULT_DB_DIR, DB_NAME)

# Each thread receives its own Scholarly session to avoid cross-thread
# interference that previously resulted in closed-client errors.
thread_local = threading.local()


def get_scholarly_client():
    """Return a thread-local :mod:`scholarly` client instance.

    The `scholarly` library is not thread-safe, so sharing a single client across
    threads can result in the underlying HTTP session being closed unexpectedly.
    By maintaining a distinct client per thread we keep requests isolated and
    avoid concurrent access issues.
    """

    client = getattr(thread_local, "scholarly", None)
    if client is None:
        client = scholarly.__class__()
        thread_local.scholarly = client
    return client


def reset_scholarly_session() -> None:
    """Create a fresh :mod:`scholarly` session for the current thread.

    When Google Scholar throttles requests, the underlying HTTP client may be
    closed, causing subsequent requests to fail. Replacing the client within the
    thread-local storage keeps the workflow resilient without affecting other
    threads.
    """

    thread_local.scholarly = scholarly.__class__()


def _init_db(db_path: str) -> sqlite3.Connection:
    """Ensure the SQLite database and table exist.

    Args:
        db_path: Location of the SQLite database file.

    Returns:
        sqlite3.Connection: Open connection to the database.
    """

    # Auto-migrate any legacy JSON caches before interacting with the database.
    migrate_legacy_files(os.path.dirname(db_path))

    conn = sqlite3.connect(db_path)
    conn.execute(
        """CREATE TABLE IF NOT EXISTS publications (
                author_id TEXT,
                title TEXT,
                year INTEGER,
                abstract TEXT,
                url TEXT,
                citations INTEGER,
                PRIMARY KEY (author_id, title)
            )"""
    )
    return conn


def fetch_from_json(args, idx=None):
    """Fetch author and publication details based on a specified index.

    Author information is now stored in a SQLite database. This helper reads the
    database located at ``args.authors_path``, converts the records into tuples,
    and fetches publication details for a subset of these authors from Google
    Scholar. The subset size is determined by ``idx``.

    Args:
        args: Namespace containing the path to the authors database and other
            relevant options.
        idx: Optional limit on the number of authors to process. ``None`` means
            all authors are fetched.

    Returns:
        tuple: A pair consisting of the selected authors and their publications.
    """

    authors_json = get_authors_json(args.authors_path)
    logger.debug(f"Fetched authors' details from {args.authors_path}.")

    authors = convert_json_to_tuple(authors_json)
    logger.debug("Converted authors' records into tuple representation.")

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
        logger.error("No authors listed in the authors database.")
        return

    # Fetch publication details for the determined number of authors from the scholarly database.
    articles = fetch_pubs_dictionary(authors[:idx], args)
    logger.info(f"Fetched {len(articles)} articles for the provided authors.")
    logger.info("Publications fetched correctly")

    return authors[:idx], articles


def fetch_publication_details(pub):
    """Populate a publication dictionary with details from Google Scholar.

    The scholarly library occasionally closes its internal HTTP session when
    hitting rate limits. If that happens we recreate the session and retry the
    request to avoid losing data mid-run.

    Args:
        pub: The publication skeleton returned by :mod:`scholarly`.

    Returns:
        dict | None: The enriched publication dictionary, or ``None`` if all
        retries fail.
    """

    # Log fetching details only when logging level allows for debug information
    title = pub["bib"]["title"]
    logger.debug("Fetching details for publication %s.", title)

    for retry in range(MAX_RETRIES):
        try:
            # Attempt to fetch publication details with the thread's session
            client = get_scholarly_client()
            return client.fill(pub)
        except RuntimeError as err:
            # When the HTTP client has been closed, reset the session and retry
            if "client has been closed" in str(err) and retry < MAX_RETRIES - 1:
                logger.warning(
                    "Scholarly session closed while fetching '%s'. Resetting session.",
                    title,
                )
                reset_scholarly_session()
                time.sleep(DELAYS[retry])
                continue
            logger.error("Runtime error fetching '%s': %s", title, err)
            return None
        except Exception as err:
            logger.error("Error fetching publication '%s': %s", title, err)
            if retry < MAX_RETRIES - 1:
                time.sleep(DELAYS[retry])
                continue
            return None

    logger.error("Max retries exceeded for publication '%s'.", title)
    return None


def fetch_author_details(author_id):
    """Retrieve publications for a given author ID.

    Google Scholar may abruptly close connections which propagates as
    ``RuntimeError`` from the :mod:`scholarly` library. To keep the workflow
    resilient we recreate the session and retry.

    Args:
        author_id: Google Scholar identifier of the author.

    Returns:
        list: Publications associated with the author. An empty list is
        returned if the author cannot be fetched.
    """

    for retry in range(MAX_RETRIES):
        try:
            client = get_scholarly_client()
            author = client.search_author_id(author_id)
            author = client.fill(author)
            return author["publications"]
        except RuntimeError as err:
            if "client has been closed" in str(err) and retry < MAX_RETRIES - 1:
                logger.warning(
                    "Scholarly session closed while fetching author %s. Resetting session.",
                    author_id,
                )
                reset_scholarly_session()
                time.sleep(DELAYS[retry])
                continue
            logger.error("Runtime error fetching author %s: %s", author_id, err)
            return []
        except Exception as err:
            logger.error("Error fetching author details for ID %s. %s", author_id, err)
            if retry < MAX_RETRIES - 1:
                time.sleep(DELAYS[retry])
                continue
            return []

    logger.error("Max retries exceeded for author %s.", author_id)
    return []


def load_cache(author_id, output_folder=DEFAULT_DB_DIR):
    """Load cached publications for an author from the SQLite database.

    Args:
        author_id: Google Scholar identifier for the author.
        output_folder: Directory where the cache database is stored.

    Returns:
        list: Publications previously cached for the author.
    """

    db_path = os.path.join(output_folder, DB_NAME)
    conn = _init_db(db_path)
    try:
        cursor = conn.execute(
            "SELECT title, year, abstract, url, citations FROM publications WHERE author_id=?",
            (author_id,),
        )
        rows = cursor.fetchall()
        cached = [
            {
                "bib": {"title": title, "pub_year": str(year), "abstract": abstract},
                "pub_url": url,
                "num_citations": citations,
            }
            for title, year, abstract, url, citations in rows
        ]
        return cached
    except Exception as e:
        logger.warning(f"Error loading cache for author {author_id}. {e}")
        return []
    finally:
        conn.close()


def get_pubs_to_fetch(author_pubs, cached_pubs, from_year, args):
    """
    Determines the publications that need to be fetched based on cached data and the specified year.

    Returns:
    - list: List of publications to fetch.
    """
    test_fetching = getattr(args, "test_fetching", False)
    if test_fetching:
        logging.warning(
            f"--test_fetching flag True. Loading only cached papers < {str(from_year)}"
        )

    # Extract titles from cached publications, only titles before from_year if test_fetching is True
    cached_titles = (
        [pub["bib"]["title"] for pub in cached_pubs]
        if not test_fetching
        else [
            pub["bib"]["title"]
            for pub in cached_pubs
            if "pub_year" in pub["bib"].keys()
            and int(pub["bib"]["pub_year"]) < int(from_year)
        ]
    )

    if args.update_cache:
        # Do not filter pubs. If this is True, it means we want to update the cache. So we fetch
        # all the author's pubs for the last year
        logger.info(
            "--update_cache flag True. Re-fetching author's pubs and generating new cache."
        )
        pubs_to_fetch = [
            item
            for item in author_pubs
            if "pub_year" in item["bib"].keys()
            and int(item["bib"]["pub_year"]) >= int(from_year)
        ]
    else:
        # Filter out publications to fetch based on title and year, only titles >= from_year if test_fetching == True
        pubs_to_fetch = [
            item
            for item in author_pubs
            if not any(
                item["bib"]["title"].split(" …")[0] in title for title in cached_titles
            )  # this handles the titles that are cut with ' …'
            # if item["bib"]["title"] not in cached_titles # this was wrong.. longer titles get cut with ' …' so they get loaded again every time if we use this
            and "pub_year" in item["bib"].keys()
            and int(item["bib"]["pub_year"]) >= int(from_year)
        ]

    return pubs_to_fetch


def fetch_selected_pubs(pubs_to_fetch):
    """Fetch selected publications concurrently.

    Each worker thread uses its own :mod:`scholarly` session, preventing shared
    state from causing ``RuntimeError`` due to closed HTTP clients. The amount
    of parallelism is intentionally limited to avoid overwhelming Google
    Scholar.

    Args:
        pubs_to_fetch: Publications to enrich.

    Returns:
        list: Successfully fetched publications.
    """

    if not pubs_to_fetch:
        logger.debug("No new publications. Skipping..")
        return []

    fetched_pubs = []
    max_workers = min(4, len(pubs_to_fetch))
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = [
            executor.submit(fetch_publication_details, pub) for pub in pubs_to_fetch
        ]
        iterator = as_completed(futures)
        if logger.getEffectiveLevel() == logging.INFO:
            iterator = tqdm(iterator, total=len(futures), desc="Fetching publications")
        for future in iterator:
            try:
                result = future.result()
            except Exception as err:
                logger.error("Unhandled error fetching publication: %s", err)
                continue
            if result is not None:
                fetched_pubs.append(result)

    return fetched_pubs


def save_updated_cache(
    fetched_pubs, cached_pubs, author_id, output_folder=DEFAULT_DB_DIR, args=None
):
    """Persist fetched publications to the SQLite cache.

    Parameters:
    - fetched_pubs (list): List of newly fetched publications.
    - cached_pubs (list): Unused; retained for backward compatibility.
    - output_folder (str, optional): Directory where the cache database is stored.
      Defaults to ``DEFAULT_DB_DIR``.
    - args (argparse.Namespace, optional): Object with the ``update_cache`` flag.
    """

    db_path = os.path.join(output_folder, DB_NAME)
    conn = _init_db(db_path)
    logger.debug(f"Updating cache for author {author_id}.")
    try:
        update_cache = getattr(args, "update_cache", False)
        if update_cache:
            conn.execute("DELETE FROM publications WHERE author_id=?", (author_id,))
        for pub in fetched_pubs:
            title = pub["bib"]["title"]
            year = pub["bib"].get("pub_year")
            year_val = int(year) if year else None
            abstract = pub["bib"].get("abstract")
            url = pub.get("pub_url")
            citations = pub.get("num_citations")
            conn.execute(
                "INSERT OR REPLACE INTO publications (author_id, title, year, abstract, url, citations) VALUES (?, ?, ?, ?, ?, ?)",
                (author_id, title, year_val, abstract, url, citations),
            )
        conn.commit()
    finally:
        conn.close()


def fetch_publications_by_id(
    author_id,
    output_folder=DEFAULT_DB_DIR,
    args=None,
    from_year=2023,
    exclude_not_cited_papers=False,
):
    """
    Fetches and caches publications of a specific author using their Google Scholar ID.

    Parameters:
    - author_id (str): Google Scholar ID of the author.
    - output_folder (str, optional): Directory where the fetched publications will be cached.
      Defaults to ``DEFAULT_DB_DIR``.
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
    # Ensure the cache directory exists
    ensure_output_folder(output_folder)
    author_pubs = fetch_author_details(author_id)
    cached_pubs = load_cache(author_id, output_folder)
    pubs_to_fetch = get_pubs_to_fetch(author_pubs, cached_pubs, from_year, args)
    fetched_pubs = fetch_selected_pubs(pubs_to_fetch)
    test_fetching = getattr(args, "test_fetching", False)
    if not test_fetching:
        save_updated_cache(fetched_pubs, cached_pubs, author_id, output_folder, args)
    return clean_pubs(fetched_pubs, from_year, exclude_not_cited_papers)


def fetch_pubs_dictionary(authors, args, output_dir=DEFAULT_DB_DIR):
    """
    Fetch publications for a list of authors for the current year,
    and store them in a cache. Only non-duplicate publications compared
    to the cache are returned.

    :param authors: List of tuples containing author name and author ID.
    :param output_dir: Directory where the cache database will be stored.
    :return: A dictionary containing non-duplicate publications.
    """

    current_year = time.strftime("%Y")  # Get the current year
    test_fetching = getattr(args, "test_fetching", False)
    params = {
        "authors": authors if not test_fetching else authors[:2],
        "from_year": current_year,
        "output_root": output_dir,
    }

    # Determine database directory. If no path is provided, fall back to the
    # user's desktop for visibility during ad-hoc runs.
    if params["output_root"] is None:
        if platform.system() == "Windows":
            output_folder = os.path.join(os.environ["USERPROFILE"], "Desktop")
        else:
            output_folder = os.path.join(os.path.expanduser("~"), "Desktop")
    else:
        output_folder = params["output_root"]

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
