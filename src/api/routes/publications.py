"""Publication query API endpoints."""

import logging
import sqlite3
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query

from src.api.models import PublicationResponse, ErrorResponse
from src.api.deps import get_publications_db, get_current_user

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/publications",
    tags=["publications"],
    responses={
        401: {"model": ErrorResponse, "description": "Unauthorized"},
        500: {"model": ErrorResponse, "description": "Internal Server Error"},
    }
)


@router.get(
    "",
    response_model=List[PublicationResponse],
    summary="Query publications",
    description="Search and filter publications across all authors.",
)
async def query_publications(
    author_id: Optional[str] = Query(None, description="Filter by author ID"),
    year: Optional[int] = Query(None, description="Filter by specific year"),
    min_year: Optional[int] = Query(None, description="Minimum year (inclusive)"),
    max_year: Optional[int] = Query(None, description="Maximum year (inclusive)"),
    min_citations: Optional[int] = Query(None, description="Minimum citations"),
    search: Optional[str] = Query(None, description="Search in title and abstract"),
    limit: int = Query(100, ge=1, le=1000, description="Maximum results"),
    offset: int = Query(0, ge=0, description="Results to skip"),
    db: sqlite3.Connection = Depends(get_publications_db),
    user: dict = Depends(get_current_user),
):
    """Query publications with various filters.

    This endpoint supports multiple filter criteria that can be combined:
    - Filter by author
    - Filter by year (exact, range)
    - Filter by minimum citations
    - Full-text search in title and abstract
    - Pagination with limit/offset

    Returns:
        List[PublicationResponse]: Matching publications ordered by citations

    Example:
        ```bash
        # Get recent highly-cited publications
        curl "http://localhost:8000/api/v1/publications?min_year=2023&min_citations=50&limit=20"

        # Search for specific topics
        curl "http://localhost:8000/api/v1/publications?search=neural+networks"

        # Get all publications for an author
        curl "http://localhost:8000/api/v1/publications?author_id=abc123xyz"
        ```
    """
    try:
        # Build dynamic query
        query_parts = ["SELECT author_id, title, year, abstract, url, citations, journal, authors FROM publications WHERE 1=1"]
        params = []

        # Add filters
        if author_id:
            query_parts.append("AND author_id = ?")
            params.append(author_id)

        if year:
            query_parts.append("AND year = ?")
            params.append(year)

        if min_year:
            query_parts.append("AND year >= ?")
            params.append(min_year)

        if max_year:
            query_parts.append("AND year <= ?")
            params.append(max_year)

        if min_citations is not None:
            query_parts.append("AND citations >= ?")
            params.append(min_citations)

        if search:
            query_parts.append("AND (title LIKE ? OR abstract LIKE ?)")
            search_pattern = f"%{search}%"
            params.extend([search_pattern, search_pattern])

        # Add ordering and pagination
        query_parts.append("ORDER BY citations DESC, year DESC LIMIT ? OFFSET ?")
        params.extend([limit, offset])

        # Execute query
        query = " ".join(query_parts)
        cursor = db.execute(query, params)
        publications = cursor.fetchall()

        result = []
        for pub in publications:
            pub_dict = dict(pub)
            result.append(PublicationResponse(
                author_id=pub_dict["author_id"],
                title=pub_dict["title"],
                authors=pub_dict.get("authors") or "",
                year=pub_dict.get("year"),
                abstract=pub_dict.get("abstract"),
                url=pub_dict.get("url"),
                citations=pub_dict.get("citations", 0),
                journal=pub_dict.get("journal")
            ))

        logger.info(f"Retrieved {len(result)} publications (limit={limit}, offset={offset})")
        return result

    except Exception as e:
        logger.error(f"Error querying publications: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to query publications: {str(e)}"
        )


@router.get(
    "/stats",
    summary="Get publication statistics",
    description="Get aggregate statistics about publications in the database.",
)
async def get_publication_stats(
    db: sqlite3.Connection = Depends(get_publications_db),
    user: dict = Depends(get_current_user),
):
    """Get aggregate publication statistics.

    Returns:
        dict: Statistics including total count, citations, year distribution

    Example:
        ```bash
        curl http://localhost:8000/api/v1/publications/stats
        ```
    """
    try:
        # Total publications
        cursor = db.execute("SELECT COUNT(*) as count FROM publications")
        total_pubs = cursor.fetchone()["count"]

        # Total citations
        cursor = db.execute("SELECT SUM(citations) as total FROM publications")
        total_citations = cursor.fetchone()["total"] or 0

        # Publications by year
        cursor = db.execute(
            """SELECT year, COUNT(*) as count
               FROM publications
               WHERE year IS NOT NULL
               GROUP BY year
               ORDER BY year DESC
               LIMIT 10"""
        )
        by_year = [dict(row) for row in cursor.fetchall()]

        # Top cited publications
        cursor = db.execute(
            """SELECT title, citations, year
               FROM publications
               ORDER BY citations DESC
               LIMIT 10"""
        )
        top_cited = [dict(row) for row in cursor.fetchall()]

        return {
            "total_publications": total_pubs,
            "total_citations": total_citations,
            "publications_by_year": by_year,
            "top_cited": top_cited
        }

    except Exception as e:
        logger.error(f"Error retrieving publication stats: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve statistics: {str(e)}"
        )


@router.delete(
    "/{author_id}/{title}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a publication",
    description="Remove a specific publication from the cache.",
)
async def delete_publication(
    author_id: str,
    title: str,
    db: sqlite3.Connection = Depends(get_publications_db),
    user: dict = Depends(get_current_user),
):
    """Delete a specific publication from the cache.

    Args:
        author_id: Google Scholar ID of the author
        title: Exact title of the publication

    Raises:
        HTTPException: If publication is not found

    Example:
        ```bash
        curl -X DELETE "http://localhost:8000/api/v1/publications/abc123xyz/My%20Paper%20Title"
        ```
    """
    try:
        # Check if publication exists
        cursor = db.execute(
            "SELECT title FROM publications WHERE author_id = ? AND title = ?",
            (author_id, title)
        )
        pub = cursor.fetchone()

        if not pub:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Publication not found"
            )

        # Delete publication
        db.execute(
            "DELETE FROM publications WHERE author_id = ? AND title = ?",
            (author_id, title)
        )

        logger.info(f"Deleted publication: {title} by {author_id}")

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting publication: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete publication: {str(e)}"
        )
