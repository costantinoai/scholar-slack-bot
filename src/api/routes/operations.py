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
from fetch_backend import fetch_from_json, fetch_publications_by_id
from src.api.scheduler import add_cron_job, list_jobs, remove_job, run_job
from src.api.models import JobCreate, JobResponse

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/fetch",
    tags=["fetch"],
    responses={
        401: {"description": "Unauthorized"},
        500: {"description": "Internal Server Error"},
    },
)


def do_refresh_cache_all(authors_db: sqlite3.Connection) -> dict:
    """Core function to refresh cache for all authors."""
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


@router.post("/refresh-cache", summary="Refresh cache for all authors (no send)")
async def refresh_cache_all(
    authors_db: sqlite3.Connection = Depends(get_authors_db),
    user: dict = Depends(get_current_user),
):
    """Refresh cached publications for all authors without sending notifications."""
    try:
        return do_refresh_cache_all(authors_db)
    except Exception as e:
        logger.error(f"Error refreshing cache for all authors: {e}")
        raise HTTPException(status_code=500, detail=str(e))


def do_fetch_and_send_all() -> dict:
    """Core function to fetch from all authors and send Slack summary."""
    # Load plugin config
    config = load_plugin_config("slack")
    if not config or "api_token" not in config:
        raise RuntimeError("Slack plugin not configured")

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
        raise RuntimeError("Failed to send notification")
    return {"success": True, "sent": True, "count": len(publications)}


@router.post("/fetch-and-send", summary="Fetch and send for all authors")
async def fetch_and_send_all(user: dict = Depends(get_current_user)):
    try:
        return do_fetch_and_send_all()
    except RuntimeError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error in fetch & send all: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/jobs", response_model=JobResponse, summary="Schedule a fetch job")
async def schedule_job(payload: JobCreate):
    """Schedule a cron job for fetch operations."""
    try:
        if payload.action == "fetch_and_notify":
            job_func = do_fetch_and_send_all
            name = payload.name or "Fetch & Send"
        elif payload.action == "fetch":
            job_func = lambda: do_refresh_cache_all(next(get_authors_db()))  # noqa: E731
            name = payload.name or "Refresh Cache"
        else:
            raise HTTPException(status_code=400, detail="Invalid action")

        job_id = f"job_{hash((payload.cron_expression, payload.action)) & 0xFFFFFFFF}"
        add_cron_job(job_id, payload.cron_expression, job_func, meta={
            "action": payload.action,
            "name": name,
            "description": payload.description,
        })
        logger.info("Scheduled %s (%s) with cron %s", name, job_id, payload.cron_expression)
        return JobResponse(
            id=job_id.__hash__() & 0x7FFFFFFF,
            name=name,
            description=payload.description,
            cron_expression=payload.cron_expression,
            action=payload.action,
            plugin_name=payload.plugin_name,
            author_ids=payload.author_ids,
            enabled=True,
            next_run=None,
            last_run=None,
            created_at=datetime.now().isoformat(),
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to schedule job: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/jobs", summary="List scheduled jobs")
async def list_scheduled_jobs():
    return list_jobs()


@router.delete("/jobs/{job_id}", summary="Delete a scheduled job")
async def delete_job(job_id: str):
    if not remove_job(job_id):
        raise HTTPException(status_code=404, detail="Job not found")
    return {"success": True, "job_id": job_id}


@router.post("/jobs/{job_id}/run", summary="Run job immediately")
async def run_job_now(job_id: str):
    if not run_job(job_id):
        raise HTTPException(status_code=404, detail="Job not found or execution failed")
    return {"success": True, "job_id": job_id}
