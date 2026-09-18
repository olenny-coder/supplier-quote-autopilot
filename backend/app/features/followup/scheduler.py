"""In-process follow-up scheduler.

Runs :func:`app.features.followup.service.run_scheduler` on an interval from inside
the web process, which is the only option on Render's free tier (no always-on
worker, and a paid Background Worker would break the free tier).

Two things make this reliable despite the service spinning down after 15 idle
minutes:

* The loop is created in the FastAPI lifespan and cancelled on shutdown, so it
  never outlives the process.
* The same work is exposed at ``POST /internal/scheduler/tick`` for an external
  free cron, which is what actually guarantees a schedule. See the README.

The loop is a plain ``asyncio`` task rather than APScheduler: one dependency fewer,
and the scheduling requirement here is a single fixed interval.
"""

import asyncio
import logging

from app.core.config import settings
from app.core.database import SessionLocal
from app.features.followup.service import run_scheduler

logger = logging.getLogger(__name__)


async def _loop(stop_event: asyncio.Event) -> None:
    interval = max(1, settings.SCHEDULER_INTERVAL_MINUTES) * 60

    logger.info("Follow-up scheduler started (every %s min)", interval // 60)

    while not stop_event.is_set():
        try:
            # wait_for returns immediately when the event is set, so shutdown does
            # not have to wait out a full interval.
            await asyncio.wait_for(stop_event.wait(), timeout=interval)
            continue
        except asyncio.TimeoutError:
            pass

        try:
            await asyncio.to_thread(_tick)
        except Exception:  # noqa: BLE001 - a scheduler crash must not kill the app
            logger.exception("Scheduled follow-up sweep failed")

    logger.info("Follow-up scheduler stopped")


def _tick() -> None:
    """One sweep, on its own session.

    The scheduler runs on a thread separate from request handling, so it opens and
    closes its own ``Session`` rather than borrowing a request-scoped one.
    """

    db = SessionLocal()

    try:
        run_scheduler(db)
    finally:
        db.close()


class SchedulerRunner:
    """Owns the background task's lifecycle."""

    def __init__(self) -> None:
        self._task: asyncio.Task | None = None
        self._stop_event: asyncio.Event | None = None

    @property
    def running(self) -> bool:
        return self._task is not None and not self._task.done()

    def start(self) -> None:
        if not settings.SCHEDULER_ENABLED:
            logger.info(
                "Follow-up scheduler disabled (SCHEDULER_ENABLED=false); "
                "drive it with POST /internal/scheduler/tick instead."
            )
            return

        if self.running:
            return

        self._stop_event = asyncio.Event()
        self._task = asyncio.create_task(_loop(self._stop_event))

    async def stop(self) -> None:
        if self._stop_event is not None:
            self._stop_event.set()

        if self._task is not None:
            try:
                await asyncio.wait_for(self._task, timeout=5)
            except (asyncio.TimeoutError, asyncio.CancelledError):
                self._task.cancel()

        self._task = None
        self._stop_event = None


runner = SchedulerRunner()
