"""
alerts/escalation.py
─────────────────────
Handles the escalation lifecycle:
  1. After an incident is created, wait `ack_timeout_seconds`.
  2. If still unacknowledged, escalate (SMS → voice call).
  3. Respects cooldown to avoid duplicate alerts for the same camera.
  4. Runs as a background thread — FastAPI starts it on startup.
"""

import time
import threading
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

from loguru import logger

from alerts.contact_manager import get_ack_timeout, get_cooldown_minutes
from alerts.twilio_client import AlertSender


class EscalationManager:
    """
    Background thread that monitors unacknowledged incidents
    and escalates if no ack is received within the timeout window.
    """

    def __init__(self):
        self.sender      = AlertSender()
        self.ack_timeout = get_ack_timeout()           # seconds (default 30)
        self.cooldown    = get_cooldown_minutes() * 60  # convert to seconds
        self._stop_evt   = threading.Event()
        self._thread     = threading.Thread(
            target=self._run_loop, daemon=True, name="EscalationThread"
        )

    def start(self):
        logger.info("EscalationManager started.")
        self._thread.start()

    def stop(self):
        self._stop_evt.set()
        self._thread.join(timeout=5)
        logger.info("EscalationManager stopped.")

    def _run_loop(self):
        """Poll every 5 s for unacknowledged incidents past their timeout."""
        while not self._stop_evt.is_set():
            try:
                self._check_and_escalate()
            except Exception as exc:
                logger.error(f"EscalationManager error: {exc}")
            time.sleep(5)

    def _check_and_escalate(self):
        from database.db import SessionLocal
        from database import crud

        db = SessionLocal()
        try:
            cutoff = datetime.now(timezone.utc) - timedelta(seconds=self.ack_timeout)
            from database.models import Incident
            # P1-11 fix: only escalate incidents where alert_sent is STILL False
            # (i.e. the initial dispatch failed entirely). If alert_sent=True, the
            # emergency services were already notified — do NOT send a second round of calls.
            pending = (
                db.query(Incident)
                .filter(
                    Incident.alert_sent == False,   # initial dispatch failed
                    Incident.acknowledged == False,
                    Incident.created_at <= cutoff,
                )
                .all()
            )

            for inc in pending:
                logger.warning(
                    f"Incident #{inc.id} — initial alert failed and unacknowledged after "
                    f"{self.ack_timeout}s — escalating now."
                )
                if inc.severity == "major":
                    self.sender.send_alerts(inc.to_dict(), db=db)

                # Mark as system-escalated to prevent further escalation loops
                crud.acknowledge_incident(db, inc.id, responder="SYSTEM_ESCALATION")

        finally:
            db.close()


# ── Cooldown helper (used by detection pipeline) ───────────────────────────────

_last_alert_times: dict[str, float] = {}    # {camera_id: last_alert_unix_ts}
_lock = threading.Lock()


def is_in_cooldown(camera_id: str) -> bool:
    """Return True if camera is still within the cooldown window."""
    cooldown = get_cooldown_minutes() * 60
    with _lock:
        last = _last_alert_times.get(camera_id, 0)
        return (time.time() - last) < cooldown


def record_alert(camera_id: str):
    """Mark that an alert was just sent for this camera."""
    with _lock:
        _last_alert_times[camera_id] = time.time()
        logger.debug(f"Cooldown started for camera: {camera_id}")

