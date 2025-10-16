"""Author management API endpoints."""

import logging
import sqlite3
from typing import List
from datetime import datetime
from types import SimpleNamespace
from fastapi import APIRouter, Depends, HTTPException, status

from src.api.models import AuthorCreate, AuthorResponse, ErrorResponse, SavePublicationsRequest
from src.api.deps import get_authors_db, get_publications_db, get_current_user
from fetch_backend import fetch_publications_by_id, _settings as _fb_settings
from src.api.models import PublicationResponse
from plugins.config import load_plugin_config
from plugins.registry import get_global_registry
from plugins.slack import SlackPlugin
from plugins.base import Publication
from helper_funcs import add_new_author_to_json, get_authors_json
from src.openalex.client import upsert_publications as _upsert_pubs

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
        import os
        from src.openalex.client import get_author_name_by_id, _get_mailto, find_author_by_orcid

        # Determine input type
        scholar_id = (author.scholar_id or '').strip() or None
        openalex_id = (author.openalex_id or '').strip() or None
        orcid = (getattr(author, 'orcid', None) or '').strip() or None
        if not scholar_id and not openalex_id and not orcid:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Provide one of: scholar_id, openalex_id, or orcid")

        # Choose the ID to store as primary ID in our authors table
        if orcid and not openalex_id:
            mailto = _get_mailto()
            resolved = find_author_by_orcid(orcid, mailto)
            if not resolved:
                raise HTTPException(status_code=404, detail="No OpenAlex author found for given ORCID")
            openalex_id = resolved.get('id')
            resolved_name = resolved.get('display_name')
        primary_id = scholar_id if scholar_id else openalex_id

        # Check if exists
        existing = db.execute("SELECT name FROM authors WHERE id = ?", (primary_id,)).fetchone()
        if existing:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=f"Author with ID {primary_id} already exists")

        # Resolve author name
        if scholar_id:
            # Use legacy helper to fetch name via scholarly
            authors_db_path = os.getenv("AUTHORS_DB_PATH", "./src/authors.db")
            result = add_new_author_to_json(authors_db_path, scholar_id)
            name = result["name"]
            # If OpenAlex is configured in settings, optionally store matching OpenAlex ID later when fetching
            db.execute("UPDATE authors SET openalex_id = COALESCE(openalex_id, openalex_id) WHERE id = ?", (primary_id,))
            if orcid:
                try:
                    db.execute("ALTER TABLE authors ADD COLUMN orcid TEXT")
                except Exception:
                    pass
                db.execute("UPDATE authors SET orcid = ? WHERE id = ?", (orcid, primary_id))
        else:
            # OpenAlex-only path: fetch display name and insert directly
            mailto = _get_mailto()
            name = resolved_name or get_author_name_by_id(openalex_id, mailto) or openalex_id
            # Ensure optional column exists (handled by deps/_init_authors_db but be safe)
            try:
                db.execute("ALTER TABLE authors ADD COLUMN openalex_id TEXT")
            except Exception:
                pass
            # Optional ORCID column
            try:
                db.execute("ALTER TABLE authors ADD COLUMN orcid TEXT")
            except Exception:
                pass
            db.execute("INSERT INTO authors (name, id, openalex_id, orcid) VALUES (?, ?, ?, ?)", (name, primary_id, openalex_id, orcid))

        db.commit()
        logger.info(f"Added author: {name} ({primary_id})")

        return AuthorResponse(id=primary_id, name=name, added_at=None, publication_count=0)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error adding author: {e}")
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


@router.post(
    "/{author_id}/refresh-cache",
    summary="Refresh author cache (no send)",
    description="Fetch latest publications for an author and update the cache. Does NOT send messages.",
)
async def refresh_author_cache(
    author_id: str,
    db: sqlite3.Connection = Depends(get_authors_db),
    pub_db: sqlite3.Connection = Depends(get_publications_db),
    user: dict = Depends(get_current_user),
):
    """Refresh cached publications for a specific author without sending notifications."""
    try:
        # Verify author exists
        cursor = db.execute("SELECT name FROM authors WHERE id=?", (author_id,))
        row = cursor.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Author not found")

        author_name = row["name"]
        # Determine fetch window from settings (supports OpenAlex full-history)
        cfg = _fb_settings()
        backend = (cfg.get("backend") or "scholar").lower()
        if backend == "openalex" and cfg.get("fetch_full_history", False):
            from_year = None
        else:
            from_year = cfg.get("from_year") or datetime.now().year
        logger.info("Refreshing cache only for author %s (%s), from_year=%s", author_name, author_id, from_year)

        # Update cache via fetch pipeline (writes into ./src/publications.db)
        pubs = fetch_publications_by_id(
            author_id,
            output_folder="./src",
            args=SimpleNamespace(update_cache=True, test_fetching=False),
            from_year=from_year,
        )
        count = len(pubs or [])
        logger.info("Cache refresh complete for %s: %d publication(s)", author_id, count)
        return {"success": True, "author_id": author_id, "count": count}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error refreshing cache for author {author_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Refresh failed: {e}")


@router.post(
    "/{author_id}/fetch-preview",
    summary="Fetch preview for author",
    description="Fetch latest publications for an author and return a preview (no save, no send).",
    response_model=List[PublicationResponse],
)
async def fetch_preview_author(
    author_id: str,
    db: sqlite3.Connection = Depends(get_authors_db),
    user: dict = Depends(get_current_user),
):
    """Fetch latest publications for an author and return them for preview without sending.

    Uses backend settings to determine from_year or full history (OpenAlex).
    Does not perform any notification.
    """
    try:
        # Verify author exists
        row = db.execute("SELECT name FROM authors WHERE id=?", (author_id,)).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Author not found")

        cfg = _fb_settings()
        backend = (cfg.get("backend") or "scholar").lower()
        if backend == "openalex" and cfg.get("fetch_full_history", False):
            from_year = None
        else:
            from_year = cfg.get("from_year") or datetime.now().year

        pubs = fetch_publications_by_id(
            author_id,
            output_folder="./src",
            args=SimpleNamespace(update_cache=False, test_fetching=False),
            from_year=from_year,
        ) or []

        # Normalize to PublicationResponse shape
        result: List[PublicationResponse] = []
        for p in pubs:
            title = p.get("title") or ""
            authors = p.get("authors") or ""
            year_raw = p.get("year")
            try:
                year_int = int(year_raw) if year_raw is not None else None
            except Exception:
                year_int = None
            abstract = p.get("abstract") or p.get("summary")
            url = p.get("pub_url") or p.get("url")
            citations = p.get("num_citations") if p.get("num_citations") is not None else p.get("citations", 0)
            journal = p.get("journal")
            result.append(PublicationResponse(
                author_id=author_id,
                title=title,
                authors=authors,
                year=year_int,
                abstract=abstract,
                url=url,
                citations=int(citations or 0),
                journal=journal,
            ))

        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching preview for author {author_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Preview failed: {e}")


@router.post(
    "/{author_id}/preview/save",
    summary="Save preview publications to DB",
    description="Persist selected preview items to the publications database.",
)
async def save_preview_publications(
    author_id: str,
    req: SavePublicationsRequest,
    user: dict = Depends(get_current_user),
):
    """Upsert selected preview publications for an author into publications DB."""
    try:
        items = req.items or []
        works = []
        for it in items:
            if it.author_id != author_id:
                continue
            works.append({
                "title": it.title,
                "authors": it.authors or "",
                "abstract": it.abstract or "",
                "year": it.year,
                "pub_url": it.url or "",
                "doi": getattr(it, 'doi', None) or "",
                "num_citations": it.citations or 0,
                "journal": it.journal or "",
            })
        count = _upsert_pubs(author_id, works)
        return {"success": True, "author_id": author_id, "saved": count}
    except Exception as e:
        logger.error(f"Error saving preview publications for {author_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post(
    "/{author_id}/fetch-and-send",
    summary="Fetch and send for author",
    description="Fetch latest publications for an author and send a Slack notification using configured plugin.",
)
async def fetch_and_send_author(
    author_id: str,
    db: sqlite3.Connection = Depends(get_authors_db),
    user: dict = Depends(get_current_user),
):
    """Fetch latest publications for an author and send via Slack plugin."""
    try:
        # Verify author exists
        cursor = db.execute("SELECT name FROM authors WHERE id=?", (author_id,))
        row = cursor.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Author not found")
        author_name = row["name"]

        cfg = _fb_settings()
        backend = (cfg.get("backend") or "scholar").lower()
        if backend == "openalex" and cfg.get("fetch_full_history", False):
            from_year = None
        else:
            from_year = cfg.get("from_year") or datetime.now().year
        logger.info("Fetch & send for author %s (%s), from_year=%s", author_name, author_id, from_year)

        # Fetch publications (returns the new/filtered list)
        pubs = fetch_publications_by_id(
            author_id,
            output_folder="./src",
            args=SimpleNamespace(update_cache=False, test_fetching=False),
            from_year=from_year,
        ) or []

        # Prepare plugin
        config = load_plugin_config("slack")
        if not config or "api_token" not in config:
            raise HTTPException(status_code=400, detail="Slack plugin not configured")
        registry = get_global_registry()
        if "slack" not in registry.list_plugins():
            registry.register(SlackPlugin)
        plugin = registry.create_instance("slack", config, cache=True)

        # Convert to dataclasses for formatting
        publications = [
            Publication(
                title=p.get("title", ""),
                authors=p.get("authors", ""),
                year=str(p.get("year", "")),
                abstract=p.get("abstract", ""),
                pub_url=p.get("pub_url", ""),
                journal=p.get("journal", ""),
                citations=p.get("num_citations"),
            )
            for p in pubs
        ]

        message = plugin.format_publications(publications)
        target = config.get("default_channel") or config.get("channel", "")
        ok = plugin.send_message(message, target)
        logger.info("Fetch & send completed for %s: %d pubs, send_ok=%s", author_id, len(publications), ok)
        if not ok:
            raise HTTPException(status_code=500, detail="Failed to send notification")

        return {"success": True, "author_id": author_id, "sent_count": len(publications)}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in fetch & send for author {author_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Fetch & send failed: {e}")
