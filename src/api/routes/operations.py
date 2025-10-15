"""Operational API endpoints for bulk fetch/update actions."""

import logging
import sqlite3
from datetime import datetime
from types import SimpleNamespace
from typing import List

from fastapi import APIRouter, Depends, HTTPException, status

from src.api.deps import get_authors_db, get_publications_db, get_current_user
from plugins.registry import get_global_registry
from plugins.slack import SlackPlugin
from plugins.config import load_plugin_config
from plugins.base import Publication
from fetch_scholar import fetch_from_json, fetch_publications_by_id

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/fetch",
    tags=["fetch"],
    responses={
        401: {"description": "Unauthorized"},
        500: {"description": "Internal Server Error"},
    },
)


@router.post("/refresh-cache", summary="Refresh cache for all authors (no send)")
async def refresh_cache_all(
    authors_db: sqlite3.Connection = Depends(get_authors_db),
    user: dict = Depends(get_current_user),
):
    """Refresh cached publications for all authors without sending notifications."""
    try:
        cursor = authors_db.execute("SELECT id, name FROM authors")
        authors = cursor.fetchall()
        if not authors:
            return {"success": True, "authors": 0, "refreshed": 0}

        total_refreshed = 0
        year = datetime.now().year
        for row in authors:
            author_id = row["id"]
            pubs = fetch_publications_by_id(
                author_id,
                output_folder="./src",
                args=SimpleNamespace(update_cache=True, test_fetching=False),
                from_year=year,
            )
            total_refreshed += len(pubs or [])

        logger.info("Refreshed cache for %d author(s), %d pubs total", len(authors), total_refreshed)
        return {"success": True, "authors": len(authors), "refreshed": total_refreshed}
    except Exception as e:
        logger.error(f"Error refreshing cache for all authors: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/fetch-and-send", summary="Fetch and send for all authors")
async def fetch_and_send_all(
    user: dict = Depends(get_current_user),
):
    """Fetch latest publications across all authors and send a Slack summary."""
    try:
        # Load plugin config
        config = load_plugin_config("slack")
        if not config or "api_token" not in config:
            raise HTTPException(status_code=400, detail="Slack plugin not configured")

        # Fetch publications for all authors (uses DB under ./src)
        args = SimpleNamespace(authors_path="./src/authors.db", update_cache=False, test_fetching=False)
        result = fetch_from_json(args)
        if not result:
            return {"success": True, "sent": False, "message": "No authors"}
        authors, pubs_list = result

        # Prepare plugin
        registry = get_global_registry()
        if "slack" not in registry.list_plugins():
            registry.register(SlackPlugin)
        plugin = registry.create_instance("slack", config, cache=True)

        # Convert fetched pubs to Publication dataclasses
        publications: List[Publication] = [
            Publication(
                title=p.get("title", ""),
                authors=p.get("authors", ""),
                year=str(p.get("year", "")),
                abstract=p.get("abstract", ""),
                pub_url=p.get("pub_url", ""),
                journal=p.get("journal", ""),
                citations=p.get("num_citations"),
            )
            for p in pubs_list or []
        ]

        message = plugin.format_publications(publications)
        target = config.get("default_channel") or config.get("channel", "")
        ok = plugin.send_message(message, target)
        logger.info("Fetch & send all completed: pubs=%d, send_ok=%s", len(publications), ok)
        if not ok:
            raise HTTPException(status_code=500, detail="Failed to send notification")
        return {"success": True, "sent": True, "count": len(publications)}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in fetch & send all: {e}")
        raise HTTPException(status_code=500, detail=str(e))

