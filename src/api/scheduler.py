"""Background scheduler setup and utilities."""

import logging
from typing import Callable, Dict

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.date import DateTrigger
from datetime import datetime

logger = logging.getLogger(__name__)

_scheduler: BackgroundScheduler | None = None
_job_meta: dict[str, dict] = {}
_job_status: dict[str, dict] = {}


def get_scheduler() -> BackgroundScheduler:
    global _scheduler
    if _scheduler is None:
        _scheduler = BackgroundScheduler()
        _scheduler.start()
        logger.info("Background scheduler started")
    return _scheduler


def shutdown_scheduler():
    global _scheduler
    if _scheduler is not None:
        _scheduler.shutdown(wait=False)
        logger.info("Background scheduler stopped")
        _scheduler = None


def add_cron_job(job_id: str, cron_expr: str, func: Callable, args: tuple = (), meta: dict | None = None):  # noqa: ANN001
    sched = get_scheduler()
    trigger = CronTrigger.from_crontab(cron_expr)
    sched.add_job(func, trigger=trigger, id=job_id, replace_existing=True, args=args)
    logger.info("Scheduled job %s with cron '%s'", job_id, cron_expr)
    if meta is None:
        meta = {}
    _job_meta[job_id] = {"cron": cron_expr, **meta}
    return job_id


def list_jobs() -> list[dict]:
    sched = get_scheduler()
    jobs = []
    for j in sched.get_jobs():
        meta = _job_meta.get(j.id, {})
        jobs.append({
            "id": j.id,
            "cron": meta.get("cron"),
            "action": meta.get("action"),
            "name": meta.get("name"),
            "description": meta.get("description"),
            "next_run": j.next_run_time.isoformat() if j.next_run_time else None,
        })
    return jobs


def remove_job(job_id: str) -> bool:
    sched = get_scheduler()
    try:
        sched.remove_job(job_id)
        _job_meta.pop(job_id, None)
        logger.info("Removed job %s", job_id)
        return True
    except Exception as e:
        logger.warning("Failed to remove job %s: %s", job_id, e)
        return False


def run_job(job_id: str) -> bool:
    sched = get_scheduler()
    job = sched.get_job(job_id)
    if not job:
        return False


def get_job_status(job_id: str) -> dict | None:
    return _job_status.get(job_id)


def set_job_status(job_id: str, **kwargs) -> None:  # noqa: ANN001
    status = _job_status.get(job_id, {})
    status.update(kwargs)
    _job_status[job_id] = status


def schedule_immediate(job_id: str, func, *args, **kwargs):  # noqa: ANN001
    sched = get_scheduler()
    sched.add_job(func, trigger=DateTrigger(run_date=datetime.now()), id=job_id, replace_existing=True, args=args, kwargs=kwargs)
    logger.info("Scheduled immediate job %s", job_id)
    try:
        # Directly call the stored function
        func = job.func
        args = job.args or ()
        func(*args)
        logger.info("Executed job %s immediately", job_id)
        return True
    except Exception as e:
        logger.error("Immediate run for job %s failed: %s", job_id, e)
        return False
