"""Author management API endpoints."""

import logging
import sqlite3
from typing import List
from fastapi import APIRouter, Depends, HTTPException, status

from src.api.models import AuthorCreate, AuthorResponse, ErrorResponse
from src.api.deps import get_authors_db, get_publications_db, get_current_user
from helper_funcs import add_new_author_to_json, get_authors_json

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/authors",
    tags=["authors"],
    responses={
        401: {"model": ErrorResponse, "description": "Unauthorized"},
        500: {"model": ErrorResponse, "description": "Internal Server Error"},
    }
)


@router.get(
    "",
    response_model=List[AuthorResponse],
    summary="List all authors",
    description="Retrieve a list of all monitored authors with their metadata.",
)
async def list_authors(
    db: sqlite3.Connection = Depends(get_authors_db),
    pub_db: sqlite3.Connection = Depends(get_publications_db),
    user: dict = Depends(get_current_user),
):
    """List all monitored authors.

    Returns:
        List[AuthorResponse]: List of all authors with publication counts

    Example:
        ```bash
        curl http://localhost:8000/api/v1/authors
        ```
    """
    try:
        # Get all authors
        cursor = db.execute("SELECT name, id FROM authors ORDER BY name")
        authors = cursor.fetchall()

        # Get publication counts for each author
        result = []
        for author in authors:
            author_dict = dict(author)

            # Count publications for this author
            pub_cursor = pub_db.execute(
                "SELECT COUNT(*) as count FROM publications WHERE author_id = ?",
                (author_dict["id"],)
            )
            pub_count = pub_cursor.fetchone()["count"]

            result.append(AuthorResponse(
                id=author_dict["id"],
                name=author_dict["name"],
                added_at=None,  # Not tracked in current schema
                publication_count=pub_count
            ))

        logger.info(f"Retrieved {len(result)} authors")
        return result

    except Exception as e:
        logger.error(f"Error listing authors: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve authors: {str(e)}"
        )


@router.post(
    "",
    response_model=AuthorResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Add a new author",
    description="Add a new author to monitor by their Google Scholar ID.",
)
async def create_author(
    author: AuthorCreate,
    db: sqlite3.Connection = Depends(get_authors_db),
    user: dict = Depends(get_current_user),
):
    """Add a new author to monitor.

    This will fetch the author's name from Google Scholar and add them
    to the database.

    Args:
        author: Author creation request with scholar_id

    Returns:
        AuthorResponse: The created author information

    Raises:
        HTTPException: If author already exists or Scholar ID is invalid

    Example:
        ```bash
        curl -X POST http://localhost:8000/api/v1/authors \\
             -H "Content-Type: application/json" \\
             -d '{"scholar_id": "abc123xyz"}'
        ```
    """
    try:
        # Check if author already exists
        cursor = db.execute(
            "SELECT name, id FROM authors WHERE id = ?",
            (author.scholar_id,)
        )
        existing = cursor.fetchone()

        if existing:
            logger.warning(f"Author {author.scholar_id} already exists")
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Author with ID {author.scholar_id} already exists"
            )

        # Add author using existing helper function
        import os
        authors_db_path = os.getenv("AUTHORS_DB_PATH", "./src/authors.db")
        result = add_new_author_to_json(authors_db_path, author.scholar_id)

        logger.info(f"Added author: {result['name']} ({author.scholar_id})")

        return AuthorResponse(
            id=result["id"],
            name=result["name"],
            added_at=None,
            publication_count=0
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error adding author {author.scholar_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to add author: {str(e)}"
        )


@router.get(
    "/{author_id}",
    response_model=AuthorResponse,
    summary="Get author details",
    description="Retrieve detailed information about a specific author.",
)
async def get_author(
    author_id: str,
    db: sqlite3.Connection = Depends(get_authors_db),
    pub_db: sqlite3.Connection = Depends(get_publications_db),
    user: dict = Depends(get_current_user),
):
    """Get detailed information about a specific author.

    Args:
        author_id: Google Scholar ID of the author

    Returns:
        AuthorResponse: Author information with publication count

    Raises:
        HTTPException: If author is not found

    Example:
        ```bash
        curl http://localhost:8000/api/v1/authors/abc123xyz
        ```
    """
    try:
        cursor = db.execute(
            "SELECT name, id FROM authors WHERE id = ?",
            (author_id,)
        )
        author = cursor.fetchone()

        if not author:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Author with ID {author_id} not found"
            )

        author_dict = dict(author)

        # Get publication count
        pub_cursor = pub_db.execute(
            "SELECT COUNT(*) as count FROM publications WHERE author_id = ?",
            (author_id,)
        )
        pub_count = pub_cursor.fetchone()["count"]

        return AuthorResponse(
            id=author_dict["id"],
            name=author_dict["name"],
            added_at=None,
            publication_count=pub_count
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error retrieving author {author_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve author: {str(e)}"
        )


@router.delete(
    "/{author_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete an author",
    description="Remove an author and all their cached publications from the system.",
)
async def delete_author(
    author_id: str,
    db: sqlite3.Connection = Depends(get_authors_db),
    pub_db: sqlite3.Connection = Depends(get_publications_db),
    user: dict = Depends(get_current_user),
):
    """Delete an author and all their publications.

    Args:
        author_id: Google Scholar ID of the author to delete

    Raises:
        HTTPException: If author is not found

    Example:
        ```bash
        curl -X DELETE http://localhost:8000/api/v1/authors/abc123xyz
        ```
    """
    try:
        # Check if author exists
        cursor = db.execute(
            "SELECT name FROM authors WHERE id = ?",
            (author_id,)
        )
        author = cursor.fetchone()

        if not author:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Author with ID {author_id} not found"
            )

        # Delete publications first
        pub_db.execute(
            "DELETE FROM publications WHERE author_id = ?",
            (author_id,)
        )

        # Delete author
        db.execute(
            "DELETE FROM authors WHERE id = ?",
            (author_id,)
        )

        logger.info(f"Deleted author: {author_id}")

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting author {author_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete author: {str(e)}"
        )


@router.get(
    "/{author_id}/publications",
    response_model=List[dict],
    summary="Get author's publications",
    description="Retrieve all cached publications for a specific author.",
)
async def get_author_publications(
    author_id: str,
    limit: int = 100,
    offset: int = 0,
    db: sqlite3.Connection = Depends(get_authors_db),
    pub_db: sqlite3.Connection = Depends(get_publications_db),
    user: dict = Depends(get_current_user),
):
    """Get all publications for a specific author.

    Args:
        author_id: Google Scholar ID of the author
        limit: Maximum number of results (default: 100)
        offset: Number of results to skip (default: 0)

    Returns:
        List[dict]: List of publications

    Raises:
        HTTPException: If author is not found

    Example:
        ```bash
        curl http://localhost:8000/api/v1/authors/abc123xyz/publications?limit=10
        ```
    """
    try:
        # Check if author exists
        cursor = db.execute(
            "SELECT name FROM authors WHERE id = ?",
            (author_id,)
        )
        author = cursor.fetchone()

        if not author:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Author with ID {author_id} not found"
            )

        # Get publications
        pub_cursor = pub_db.execute(
            """SELECT author_id, title, year, abstract, url, citations
               FROM publications
               WHERE author_id = ?
               ORDER BY citations DESC, year DESC
               LIMIT ? OFFSET ?""",
            (author_id, limit, offset)
        )
        publications = pub_cursor.fetchall()

        result = [dict(pub) for pub in publications]
        logger.info(f"Retrieved {len(result)} publications for author {author_id}")

        return result

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error retrieving publications for author {author_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve publications: {str(e)}"
        )
