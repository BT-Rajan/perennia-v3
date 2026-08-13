"""
A single in-process background job: periodically check the connected
Google Calendar for events that changed outside this app (edited or
deleted directly in Google) and flag any linked appointment that no
longer matches — see calendar_sync_service.detect_drift.

Deliberately minimal: one job, driven by a single admin-configurable
interval setting (calendar_sync.drift_poll_minutes), started once at
app startup and stopped at shutdown. This is the only background/
recurring task in the app, so a general job-scheduling framework isn't
worth the extra moving part yet — plain APScheduler in the same
process is enough. If a second recurring job is ever needed, that's
the point to reconsider (e.g. moving to a dedicated worker process).
"""
from __future__ import annotations

import logging

from apscheduler.schedulers.background import BackgroundScheduler

logger = logging.getLogger("perennia.calendar_sync")

_scheduler: BackgroundScheduler | None = None
_JOB_ID = "calendar_drift_poll"


def _run_drift_check() -> None:
    from app.db import session_scope
    from app import calendar_sync_service
    from app.settings_service import get_setting

    with session_scope() as db:
        if not get_setting(db, "features.calendar_sync_enabled"):
            return
        if calendar_sync_service.get_active_credential(db) is None:
            return
        result = calendar_sync_service.detect_drift(db)
        if not result.get("ok"):
            logger.warning("Scheduled calendar drift check failed: %s", result.get("error"))
        elif result.get("flagged"):
            logger.info("Scheduled calendar drift check flagged %d appointment(s)", result["flagged"])


def start() -> None:
    """Called once from main.py's startup hook. Reads the poll interval
    fresh from settings each time the job fires (not just at startup),
    so an admin changing it takes effect on the job's next tick without
    a restart — reschedule() below handles an interval change made
    mid-run."""
    global _scheduler
    if _scheduler is not None:
        return
    from app.db import session_scope
    from app.settings_service import get_setting

    try:
        with session_scope() as db:
            minutes = get_setting(db, "calendar_sync.drift_poll_minutes")
    except Exception:
        # Settings table may not exist yet (fresh install before
        # init_db.py has run) - skip scheduling rather than crash startup.
        logger.exception("Could not read calendar_sync.drift_poll_minutes at startup; drift polling disabled")
        return

    _scheduler = BackgroundScheduler(daemon=True)
    if minutes and minutes > 0:
        _scheduler.add_job(_run_drift_check, "interval", minutes=minutes, id=_JOB_ID,
                            max_instances=1, coalesce=True)
    _scheduler.start()


def reschedule(minutes: int) -> None:
    """Call after an admin updates calendar_sync.drift_poll_minutes so
    the running scheduler picks up the new interval immediately."""
    if _scheduler is None:
        return
    if _scheduler.get_job(_JOB_ID) is not None:
        _scheduler.remove_job(_JOB_ID)
    if minutes and minutes > 0:
        _scheduler.add_job(_run_drift_check, "interval", minutes=minutes, id=_JOB_ID,
                            max_instances=1, coalesce=True)


def stop() -> None:
    global _scheduler
    if _scheduler is not None:
        _scheduler.shutdown(wait=False)
        _scheduler = None
