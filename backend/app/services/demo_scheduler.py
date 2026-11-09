"""Nightly reset of the public demo, done by the app itself.

The uptime pinger runs from the early morning to the evening only (the free host has a limit of 750 instance
hours a month for the whole workspace), so the app wakes up around 06:30. A small background thread then resets
the demo once per day between 06:00 and 08:00 Vienna time, before the first visitors. No external cron job and no secret is needed.
The check is cheap: it only reads the time of the first audit entry (the moment the demo data was loaded).
"""

import logging
import threading
import time
from datetime import datetime
from zoneinfo import ZoneInfo

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.db import SessionLocal
from app.models import AuditEntry

log = logging.getLogger("valitrack.demo")

VIENNA = ZoneInfo("Europe/Vienna")
RESET_HOURS = (6, 7)
CHECK_EVERY_SECONDS = 600

_lock = threading.Lock()


def needs_reset(db: Session, now: datetime | None = None) -> bool:
    """True when it is early morning in Vienna and the demo data was loaded on an earlier day."""
    now = (now or datetime.now(VIENNA)).astimezone(VIENNA)
    if now.hour not in RESET_HOURS:
        return False
    loaded_at = db.scalar(select(func.min(AuditEntry.occurred_at)))
    if loaded_at is None:
        return False  # empty database: the start script loads the data
    return loaded_at.astimezone(VIENNA).date() < now.date()


def reset_now() -> bool:
    """Reset the demo unless a reset is already running. Returns False when it was skipped."""
    from app.seed.demo import reset_and_seed

    if not _lock.acquire(blocking=False):
        return False
    try:
        with SessionLocal() as session:
            reset_and_seed(session)
        log.info("Demo data was reset.")
        return True
    finally:
        _lock.release()


def start_reset_in_background() -> None:
    threading.Thread(target=reset_now, name="demo-reset", daemon=True).start()


def _loop() -> None:
    time.sleep(60)  # let the server finish starting
    while True:
        try:
            with SessionLocal() as session:
                due = needs_reset(session)
            if due:
                reset_now()
        except Exception:
            log.exception("The nightly demo reset check failed.")
        time.sleep(CHECK_EVERY_SECONDS)


def start_scheduler() -> None:
    settings = get_settings()
    if settings.demo_mode and settings.demo_auto_reset:
        threading.Thread(target=_loop, name="demo-scheduler", daemon=True).start()
