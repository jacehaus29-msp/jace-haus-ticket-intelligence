import os
import asyncio
import logging
from datetime import datetime, timezone
from typing import Optional, Dict, Any

from app.database import SessionLocal
from app.services.notification_service import check_and_generate_sla_notifications

logger = logging.getLogger("sla_worker")
if not logger.handlers:
    handler = logging.StreamHandler()
    formatter = logging.Formatter("[%(asctime)s] [%(name)s] %(levelname)s: %(message)s")
    handler.setFormatter(formatter)
    logger.addHandler(handler)
logger.setLevel(logging.INFO)


class SLAWorker:
    """
    Autonomous background worker that scans tickets periodically
    to calculate SLA timers, detect at-risk conditions, detect breaches,
    and trigger automated escalations.
    """

    def __init__(self, interval_seconds: Optional[int] = None):
        env_interval = os.environ.get("SLA_WORKER_INTERVAL_SECONDS")
        if interval_seconds is not None:
            self.interval_seconds = max(5, interval_seconds)
        elif env_interval and env_interval.strip().isdigit():
            self.interval_seconds = max(5, int(env_interval.strip()))
        else:
            self.interval_seconds = 30  # Default 30 seconds

        self._running: bool = False
        self._task: Optional[asyncio.Task] = None
        self._last_run_at: Optional[datetime] = None
        self._total_runs: int = 0
        self._total_alerts_generated: int = 0
        self._last_error: Optional[str] = None

    @property
    def is_running(self) -> bool:
        return self._running and self._task is not None and not self._task.done()

    def run_once(self) -> Dict[str, Any]:
        """
        Execute a single scan cycle using an isolated database session.
        Returns a summary dictionary of the execution.
        """
        db = SessionLocal()
        start_time = datetime.now(timezone.utc)
        try:
            alerts = check_and_generate_sla_notifications(db)
            alert_count = len(alerts)
            self._last_run_at = start_time
            self._total_runs += 1
            self._total_alerts_generated += alert_count
            self._last_error = None
            if alert_count > 0:
                logger.info(f"[SLA Worker] Scan completed: generated {alert_count} alert(s)")
            return {
                "success": True,
                "alerts_generated": alert_count,
                "ran_at": start_time.isoformat()
            }
        except Exception as e:
            err_msg = str(e)
            self._last_error = err_msg
            logger.error(f"[SLA Worker] Error during SLA scan cycle: {err_msg}", exc_info=True)
            return {
                "success": False,
                "error": err_msg,
                "ran_at": start_time.isoformat()
            }
        finally:
            db.close()

    async def _worker_loop(self):
        """Continuous background execution loop."""
        logger.info(f"[SLA Worker] Started background worker loop (interval={self.interval_seconds}s)")
        while self._running:
            try:
                # Run synchronous DB task in default threadpool executor to avoid blocking event loop
                await asyncio.to_thread(self.run_once)
            except asyncio.CancelledError:
                logger.info("[SLA Worker] Task cancelled, exiting worker loop.")
                break
            except Exception as e:
                logger.error(f"[SLA Worker] Unhandled exception in worker loop: {e}", exc_info=True)

            try:
                await asyncio.sleep(self.interval_seconds)
            except asyncio.CancelledError:
                logger.info("[SLA Worker] Sleep interrupted by cancellation, shutting down.")
                break

    def start(self):
        """Start the background worker task."""
        if self._running and self._task is not None and not self._task.done():
            logger.warning("[SLA Worker] Start requested but worker is already running.")
            return

        self._running = True
        loop = asyncio.get_event_loop()
        self._task = loop.create_task(self._worker_loop())
        logger.info("[SLA Worker] Background task registered with event loop.")

    async def stop(self):
        """Gracefully stop the background worker task."""
        if not self._running and (self._task is None or self._task.done()):
            return

        self._running = False
        if self._task and not self._task.done():
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        self._task = None
        logger.info("[SLA Worker] Background worker successfully stopped.")

    def get_status(self) -> Dict[str, Any]:
        """Return diagnostic status of the background worker."""
        return {
            "is_running": self.is_running,
            "interval_seconds": self.interval_seconds,
            "last_run_at": self._last_run_at.isoformat() if self._last_run_at else None,
            "total_runs": self._total_runs,
            "total_alerts_generated": self._total_alerts_generated,
            "last_error": self._last_error
        }


# Global singleton worker instance
sla_worker = SLAWorker()
