"""Background scheduler setup and utilities."""

import logging
from typing import Callable, Dict

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

logger = logging.getLogger(__name__)

_scheduler: BackgroundScheduler | None = None


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


def add_cron_job(job_id: str, cron_expr: str, func: Callable, args: tuple = ()):  # noqa: ANN001
    sched = get_scheduler()
    trigger = CronTrigger.from_crontab(cron_expr)
    sched.add_job(func, trigger=trigger, id=job_id, replace_existing=True, args=args)
    logger.info("Scheduled job %s with cron '%s'", job_id, cron_expr)
    return job_id

