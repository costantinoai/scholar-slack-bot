"""Publication query API endpoints."""

import logging
import sqlite3
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query

from src.api.models import PublicationResponse, ErrorResponse
from src.api.deps import get_publications_db, get_current_user, get_authors_db

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
        query_parts = ["SELECT author_id, title, year, abstract, url, citations, journal, authors, doi FROM publications WHERE 1=1"]
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
                journal=pub_dict.get("journal"),
                doi=pub_dict.get("doi")
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
    min_year: Optional[int] = Query(None, description="Minimum publication year to include"),
    max_year: Optional[int] = Query(None, description="Maximum publication year to include"),
    top_limit: int = Query(10, ge=1, le=100, description="Top authors/publications limit"),
    db: sqlite3.Connection = Depends(get_publications_db),
    authors_db: sqlite3.Connection = Depends(get_authors_db),
    user: dict = Depends(get_current_user),
):
    """Get aggregate publication statistics.

    Args:
        min_year: Filter stats to publications from this year (inclusive)
        max_year: Filter stats to publications up to this year (inclusive)
        top_limit: How many entries to return for top lists

    Returns:
        dict with counts, per-year distribution, top-cited publications, and
        top authors by citations within the provided year window.
    """
    try:
        # Common WHERE clause parts
        where_parts = ["1=1"]
        params: list = []
        if min_year is not None:
            where_parts.append("year >= ?")
            params.append(min_year)
        if max_year is not None:
            where_parts.append("year <= ?")
            params.append(max_year)
        where = " AND ".join(where_parts)

        # Total publications (respecting year filter if provided)
        cursor = db.execute(f"SELECT COUNT(*) as count FROM publications WHERE {where}", params)
        total_pubs = cursor.fetchone()["count"]

        # Total citations (respecting year filter)
        cursor = db.execute(f"SELECT COALESCE(SUM(citations), 0) as total FROM publications WHERE {where}", params)
        total_citations = cursor.fetchone()["total"] or 0

        # Publications by year (no limit by default; return ascending years for chart readability)
        cursor = db.execute(
            f"""
               SELECT year, COUNT(*) as count
               FROM publications
               WHERE year IS NOT NULL AND {where}
               GROUP BY year
               ORDER BY year ASC
            """,
            params,
        )
        by_year = [dict(row) for row in cursor.fetchall()]

        # Top cited publications (within window)
        cursor = db.execute(
            f"""
               SELECT title, COALESCE(citations,0) AS citations, year
               FROM publications
               WHERE {where}
               ORDER BY citations DESC
               LIMIT ?
            """,
            [*params, top_limit],
        )
        top_cited = [dict(row) for row in cursor.fetchall()]

        # Top authors by citations (within window) — aggregate in publications DB and resolve names from authors DB
        cursor = db.execute(
            f"""
               SELECT author_id, COALESCE(SUM(citations),0) AS citations
               FROM publications
               WHERE {where}
               GROUP BY author_id
               ORDER BY citations DESC
               LIMIT ?
            """,
            [*params, top_limit],
        )
        rows = cursor.fetchall()
        top_authors = []
        for r in rows:
            aid = r["author_id"]
            cits = r["citations"] or 0
            name_row = authors_db.execute("SELECT name FROM authors WHERE id = ?", (aid,)).fetchone()
            name = name_row["name"] if name_row else aid
            top_authors.append({"author_id": aid, "name": name, "citations": cits})

        # Top journals by publication count (and citations) within window
        # We ignore empty or NULL journal entries for this aggregation.
        cursor = db.execute(
            f"""
               SELECT journal, COUNT(*) AS publications, COALESCE(SUM(citations),0) AS citations
               FROM publications
               WHERE {where} AND journal IS NOT NULL AND TRIM(journal) <> ''
               GROUP BY journal
               ORDER BY publications DESC, citations DESC
               LIMIT ?
            """,
            [*params, top_limit],
        )
        top_journals = [
            {"journal": row["journal"], "publications": row["publications"], "citations": row["citations"]}
            for row in cursor.fetchall()
        ]

        # Institutions by country (geo stats)
        countries = []
        try:
            # Only if institutions table exists
            chk = db.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='publication_institutions'").fetchone()
            if chk:
                cursor = db.execute(
                    f"""
                       SELECT TRIM(UPPER(pi.country_code)) AS country_code, COUNT(*) AS publications
                       FROM publication_institutions pi
                       JOIN publications p
                         ON p.author_id = pi.author_id AND p.source_id = pi.source_id
                       WHERE {where} AND pi.country_code IS NOT NULL AND TRIM(pi.country_code) <> ''
                       GROUP BY TRIM(UPPER(pi.country_code))
                       ORDER BY publications DESC
                       LIMIT ?
                    """,
                    [*params, top_limit],
                )
                countries = [ {"country_code": r["country_code"], "publications": r["publications"]} for r in cursor.fetchall() ]
        except Exception:
            countries = []

        # Compute basic author-level fine-grained stats and h-index leaderboard
        # We iterate authors and compute h-index using per-author citations list.
        authors_rows = authors_db.execute("SELECT id, name FROM authors").fetchall()
        total_authors = len(authors_rows)
        pubs_per_author: list[int] = []
        citations_per_author: list[int] = []
        h_index_entries: list[dict] = []

        for row in authors_rows:
            aid = row["id"]
            aname = row["name"]
            # Publications count respecting year window
            pcount_row = db.execute(
                f"SELECT COUNT(*) AS c FROM publications WHERE author_id = ? AND {where}",
                [aid, *params],
            ).fetchone()
            pcount = int(pcount_row["c"]) if pcount_row else 0
            pubs_per_author.append(pcount)

            # Total citations respecting year window
            csum_row = db.execute(
                f"SELECT COALESCE(SUM(citations),0) AS s FROM publications WHERE author_id = ? AND {where}",
                [aid, *params],
            ).fetchone()
            csum = int(csum_row["s"]) if csum_row else 0
            citations_per_author.append(csum)

            # h-index (computed from all publications for the author within the window)
            cits_rows = db.execute(
                f"SELECT COALESCE(citations,0) AS c FROM publications WHERE author_id = ? AND {where} ORDER BY citations DESC",
                [aid, *params],
            ).fetchall()
            cits_sorted = [int(r["c"]) for r in cits_rows]
            h = 0
            for i, c in enumerate(cits_sorted, start=1):
                if c >= i:
                    h = i
                else:
                    break
            h_index_entries.append({"author_id": aid, "name": aname, "h_index": h})

        # Sort and pick top N h-index authors
        top_authors_by_h = sorted(h_index_entries, key=lambda x: x["h_index"], reverse=True)[:top_limit]

        # Basic aggregates with safe guards against division by zero
        avg_pubs_per_author = (sum(pubs_per_author) / total_authors) if total_authors else 0.0
        avg_citations_per_author = (sum(citations_per_author) / total_authors) if total_authors else 0.0
        avg_citations_per_publication = (total_citations / total_pubs) if total_pubs else 0.0

        # Lightweight keyword extraction from titles+abstracts as a proxy for topics
        # This avoids requiring OpenAlex concept ingestion while still giving a topical view.
        # Very simple tokenization with a built-in stopword list.
        # Prefer canonical topics if available in publication_topics; fallback to keyword extraction
        top_keywords = []
        try:
            tbl = db.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='publication_topics'").fetchone()
            if tbl:
                # Join with publications to respect year filters
                cursor = db.execute(
                    f"""
                       SELECT pt.term AS term, COUNT(*) AS count
                       FROM publication_topics pt
                       JOIN publications p
                         ON p.author_id = pt.author_id AND p.source_id = pt.source_id
                       WHERE {where}
                       GROUP BY pt.term
                       ORDER BY count DESC
                       LIMIT ?
                    """,
                    [*params, min(top_limit * 2, 30)],
                )
                rows = cursor.fetchall()
                top_keywords = [ {"term": r["term"], "count": r["count"]} for r in rows ]
        except Exception:
            top_keywords = []

        if not top_keywords:
            try:
                stopwords = {
                    # Common English stopwords (short list)
                    'the','and','for','with','that','this','from','into','over','under','between','within','without','using','use','used','based','via','of','in','on','to','by','as','a','an','is','are','be','we','it','our','their','its','at','or','not','no','yes','more','less','new','novel','study','paper','method','results','analysis','approach','effect','effects','case','data','model','models','evidence','insight','insights','evaluation','towards','about','across','across','can','may','might','will','would','should'
                }
                # Pull a limited number of records to stay efficient on large DBs
                kw_rows = db.execute(
                    f"""
                       SELECT title, abstract FROM publications
                       WHERE {where}
                    """,
                    params,
                ).fetchall()
                from collections import Counter
                import re
                counter: Counter[str] = Counter()
                for r in kw_rows:
                    text = f"{r['title'] or ''} {r['abstract'] or ''}"
                    # Tokenize on non-letters, lowercase, minimum length 4
                    for tok in re.split(r"[^a-zA-Z]+", text.lower()):
                        if len(tok) < 4:
                            continue
                        if tok in stopwords:
                            continue
                        counter[tok] += 1
                top_keywords = [
                    {"term": term, "count": count}
                    for term, count in counter.most_common(min(top_limit * 2, 30))
                ]
            except Exception:
                top_keywords = []

        return {
            "total_publications": total_pubs,
            "total_citations": total_citations,
            "publications_by_year": by_year,
            "top_cited": top_cited,
            "top_authors_by_citations": top_authors,
            "top_journals": top_journals,
            "institutions_by_country": countries,
            "authors_summary": {
                "total_authors": total_authors,
                "avg_pubs_per_author": avg_pubs_per_author,
                "avg_citations_per_author": avg_citations_per_author,
                "avg_citations_per_publication": avg_citations_per_publication,
                "top_authors_by_h_index": top_authors_by_h,
            },
            "top_keywords": top_keywords,
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
