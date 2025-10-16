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
from fetch_backend import fetch_from_json, fetch_publications_by_id, _settings as _fb_settings
from src.api.scheduler import (
    add_cron_job,
    list_jobs,
    remove_job,
    run_job,
    schedule_immediate,
    set_job_status,
    get_job_status,
)
from src.api.models import JobCreate, JobResponse, SendPublicationsRequest, SavePublicationsRequest
import os
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/fetch",
    tags=["fetch"],
    responses={
        401: {"description": "Unauthorized"},
        500: {"description": "Internal Server Error"},
    },
)


def do_refresh_cache_all(authors_db: sqlite3.Connection, job_id: str | None = None) -> dict:
    """Core function to refresh cache for all authors."""
    cursor = authors_db.execute("SELECT id, name FROM authors")
    authors = cursor.fetchall()
    if not authors:
        return {"success": True, "authors": 0, "refreshed": 0}

    total_refreshed = 0
    cfg = _fb_settings()
    backend = (cfg.get("backend") or "scholar").lower()
    if backend == "openalex" and cfg.get("fetch_full_history", False):
        from_year = None
    else:
        from_year = cfg.get("from_year") or datetime.now().year
    processed = 0
    for row in authors:
        author_id = row["id"]
        author_name = row["name"]
        pubs = fetch_publications_by_id(
            author_id,
            output_folder="./src",
            args=SimpleNamespace(update_cache=True, test_fetching=False),
            from_year=from_year,
        )
        total_refreshed += len(pubs or [])
        processed += 1
        if job_id:
            try:
                from src.api.scheduler import set_job_status  # local import to avoid cycles
                set_job_status(job_id, status="running", processed=processed, total=len(authors), current_author=author_name)
            except Exception:
                pass

    logger.info("Refreshed cache for %d author(s), %d pubs total", len(authors), total_refreshed)
    return {"success": True, "authors": len(authors), "refreshed": total_refreshed}


def do_fetch_and_send_all_progress(job_id: str | None = None) -> dict:
    # Load plugin config
    config = load_plugin_config("slack")
    if not config or "api_token" not in config:
        raise RuntimeError("Slack plugin not configured")

    # Gather authors list for progress
    db_gen = get_authors_db()
    conn = next(db_gen)
    try:
        rows = conn.execute("SELECT id, name FROM authors").fetchall()
    finally:
        try:
            next(db_gen)
        except StopIteration:
            pass

    total = len(rows)
    processed = 0
    all_works = []
    cfg = _fb_settings()
    backend = (cfg.get("backend") or "scholar").lower()
    if backend == "openalex" and cfg.get("fetch_full_history", False):
        from_year = None
    else:
        from_year = cfg.get("from_year") or datetime.now().year
    for r in rows:
        author_id = r["id"]
        author_name = r["name"]
        works = fetch_publications_by_id(
            author_id,
            output_folder="./src",
            args=SimpleNamespace(update_cache=False, test_fetching=False),
            from_year=from_year,
        ) or []
        all_works.extend(works)
        processed += 1
        if job_id:
            try:
                from src.api.scheduler import set_job_status
                set_job_status(job_id, status="running", processed=processed, total=total, current_author=author_name)
            except Exception:
                pass

    # Prepare plugin
    registry = get_global_registry()
    if "slack" not in registry.list_plugins():
        registry.register(SlackPlugin)
    plugin = registry.create_instance("slack", config, cache=True)

    # Convert to Publication dataclasses
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
        for p in all_works
    ]

    message = plugin.format_publications(publications)
    target = config.get("default_channel") or config.get("channel", "")
    ok = plugin.send_message(message, target)
    if not ok:
        raise RuntimeError("Failed to send notification")
    return {"success": True, "sent": True, "count": len(publications)}


@router.post("/preview", summary="Fetch & preview for all authors")
async def fetch_preview_all(
    authors_db: sqlite3.Connection = Depends(get_authors_db),
    user: dict = Depends(get_current_user),
):
    """Fetch latest publications across all authors and return a preview (no save, no send)."""
    try:
        cfg = _fb_settings()
        backend = (cfg.get("backend") or "scholar").lower()
        if backend == "openalex" and cfg.get("fetch_full_history", False):
            from_year = None
        else:
            from_year = cfg.get("from_year") or datetime.now().year

        rows = authors_db.execute("SELECT id FROM authors").fetchall()
        result = []
        for r in rows:
            author_id = r["id"]
            pubs = fetch_publications_by_id(
                author_id,
                output_folder="./src",
                args=SimpleNamespace(update_cache=False, test_fetching=False),
                from_year=from_year,
            ) or []
            for p in pubs:
                result.append({
                    "author_id": author_id,
                    "title": p.get("title") or "",
                    "authors": p.get("authors") or "",
                    "year": p.get("year"),
                    "abstract": p.get("abstract") or p.get("summary"),
                    "url": p.get("pub_url") or p.get("url"),
                    "citations": p.get("num_citations") if p.get("num_citations") is not None else p.get("citations", 0),
                    "journal": p.get("journal"),
                })
        return result
    except Exception as e:
        logger.error(f"Error in preview all: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/preview/save", summary="Save preview publications (bulk) to DB")
async def save_preview_publications_bulk(
    req: SavePublicationsRequest,
    user: dict = Depends(get_current_user),
):
    """Persist selected preview publications (across authors) into publications DB.

    Groups items by author_id and upserts in batches per author.
    """
    try:
        items = req.items or []
        if not items:
            return {"success": True, "saved": 0}
        from collections import defaultdict
        groups = defaultdict(list)
        for it in items:
            groups[it.author_id].append(it)
        total_saved = 0
        from src.openalex.client import upsert_publications as _upsert
        for author_id, lst in groups.items():
            works = []
            for it in lst:
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
            total_saved += _upsert(author_id, works)
        return {"success": True, "saved": total_saved}
    except Exception as e:
        logger.error(f"Error saving preview publications (bulk): {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/notify/send", summary="Send publications via plugin")
async def send_publications(req: SendPublicationsRequest):
    """Format and send a set of publications via the selected plugin.

    Defaults to Slack if no plugin is provided. Uses plugin config target if not provided.
    """
    try:
        plugin_name = (req.plugin_name or "slack").lower()
        config = load_plugin_config(plugin_name)
        if not config:
            raise HTTPException(status_code=400, detail=f"Plugin '{plugin_name}' not configured")

        registry = get_global_registry()
        if plugin_name not in registry.list_plugins():
            # Attempt to register Slack by default
            if plugin_name == "slack":
                registry.register(SlackPlugin)
            else:
                raise HTTPException(status_code=404, detail=f"Plugin '{plugin_name}' not available")

        plugin = registry.create_instance(plugin_name, config, cache=True)

        # Build dataclass objects
        publications: List[Publication] = []
        for it in req.items:
            publications.append(
                Publication(
                    title=it.title,
                    authors=it.authors or "",
                    year=str(it.year or ""),
                    abstract=it.abstract or "",
                    pub_url=it.url or "",
                    journal=it.journal or "",
                    citations=it.citations or 0,
                )
            )

        if not publications:
            return {"success": True, "sent": False, "count": 0}

        message = plugin.format_publications(publications)
        target = req.target or config.get("default_channel") or config.get("channel", "")
        ok = plugin.send_message(message, target)
        if not ok:
            raise HTTPException(status_code=500, detail="Failed to send notification")
        return {"success": True, "sent": True, "count": len(publications)}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error sending publications: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/hard-reset", summary="Hard reset publications database and refetch all authors")
async def hard_reset_publications_db(user: dict = Depends(get_current_user)):
    """Schedule a background hard reset and return a job id for progress polling."""
    job_id = f"hard_reset_{hash(datetime.now().isoformat()) & 0xFFFFFFFF}"
    set_job_status(job_id, status="running", started_at=datetime.now().isoformat(), message="Starting hard reset")

    def _runner():
        try:
            pub_db_env = os.getenv("PUBLICATIONS_DB_PATH", "./src/publications.db")
            pub_path = Path(pub_db_env)
            pub_path.parent.mkdir(parents=True, exist_ok=True)

            # Backup existing
            if pub_path.exists():
                ts = datetime.now().strftime("%Y%m%d_%H%M%S")
                backup = pub_path.with_name(f"{pub_path.name}.{ts}.bak")
                pub_path.rename(backup)
                logger.info("Backed up publications DB to %s", str(backup))

            # Fresh DB
            conn = sqlite3.connect(str(pub_path))
            try:
                conn.execute(
                    """CREATE TABLE IF NOT EXISTS publications (
                        author_id TEXT,
                        title TEXT,
                        source_id TEXT,
                        year INTEGER,
                        abstract TEXT,
                        url TEXT,
                        doi TEXT,
                        citations INTEGER,
                        journal TEXT,
                        authors TEXT,
                        PRIMARY KEY (author_id, title, source_id)
                    )"""
                )
                conn.commit()
            finally:
                conn.close()

            # Settings window
            cfg = _fb_settings()
            backend = (cfg.get("backend") or "scholar").lower()
            if backend == "openalex" and cfg.get("fetch_full_history", False):
                from_year = None
            else:
                from_year = cfg.get("from_year") or datetime.now().year

            # Iterate authors
            db_gen = get_authors_db()
            adb = next(db_gen)
            try:
                rows = adb.execute("SELECT id, name FROM authors").fetchall()
            finally:
                try:
                    next(db_gen)
                except StopIteration:
                    pass
            total = len(rows)
            processed = 0
            total_pubs = 0
            for r in rows:
                author_id = r["id"]
                author_name = r["name"]
                set_job_status(job_id, status="running", processed=processed, total=total, current_author=author_name)
                pubs = fetch_publications_by_id(
                    author_id,
                    output_folder=str(pub_path.parent),
                    args=SimpleNamespace(update_cache=True, test_fetching=False),
                    from_year=from_year,
                ) or []
                total_pubs += len(pubs)
                processed += 1
                set_job_status(job_id, status="running", processed=processed, total=total, current_author=author_name)

            set_job_status(job_id, status="completed", finished_at=datetime.now().isoformat(), result={
                "success": True,
                "authors": total,
                "publications": total_pubs,
                "from_year": from_year,
                "backend": backend,
            })
        except Exception as e:  # pragma: no cover
            logger.error("Hard reset runner failed: %s", e)
            set_job_status(job_id, status="failed", finished_at=datetime.now().isoformat(), error=str(e))

    schedule_immediate(job_id, _runner)
    return {"job_id": job_id, "status": "running", "status_url": f"/api/v1/fetch/jobs/{job_id}/status"}


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


@router.post("/run", summary="Run fetch action asynchronously")
async def run_async_action(payload: dict, user: dict = Depends(get_current_user)):
    action = payload.get("action")
    if action not in ("fetch", "fetch_and_notify"):
        raise HTTPException(status_code=400, detail="Invalid action")

    job_id = f"run_{hash((action, datetime.now().isoformat())) & 0xFFFFFFFF}"
    set_job_status(job_id, status="running", started_at=datetime.now().isoformat(), message=f"Starting {action}")

    def _runner():
        try:
            if action == "fetch":
                db_gen = get_authors_db()
                conn = next(db_gen)
                try:
                    res = do_refresh_cache_all(conn, job_id=job_id)
                finally:
                    try:
                        next(db_gen)
                    except StopIteration:
                        pass
                set_job_status(job_id, status="completed", finished_at=datetime.now().isoformat(), result=res)
            else:
                res = do_fetch_and_send_all_progress(job_id=job_id)
                set_job_status(job_id, status="completed", finished_at=datetime.now().isoformat(), result=res)
        except Exception as e:  # pragma: no cover
            set_job_status(job_id, status="failed", finished_at=datetime.now().isoformat(), error=str(e))

    schedule_immediate(job_id, _runner)
    return {"job_id": job_id, "status": "running", "status_url": f"/api/v1/fetch/jobs/{job_id}/status"}


@router.get("/jobs/{job_id}/status", summary="Get job status")
async def get_status(job_id: str):
    st = get_job_status(job_id)
    if not st:
        raise HTTPException(status_code=404, detail="Job not found")
    return st
