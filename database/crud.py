"""
database/crud.py
────────────────
All database read/write operations (Create, Read, Update, Delete).
FastAPI routes and the detection pipeline call only these functions —
they never touch the DB session directly.
"""

from datetime import datetime, timezone
from typing import Optional
from sqlalchemy.orm import Session

from database.models import Incident, Alert, Acknowledgement


# ── Incidents ──────────────────────────────────────────────────────────────────

def create_incident(db: Session, **kwargs) -> Incident:
    """Insert a new incident row and return it."""
    inc = Incident(**kwargs)
    db.add(inc)
    db.commit()
    db.refresh(inc)
    return inc


def get_incident(db: Session, incident_id: int) -> Optional[Incident]:
    return db.query(Incident).filter(Incident.id == incident_id).first()


def get_all_incidents(db: Session, skip: int = 0, limit: int = 100) -> list[Incident]:
    return (
        db.query(Incident)
        .order_by(Incident.created_at.desc())
        .offset(skip)
        .limit(limit)
        .all()
    )


def get_recent_incidents_for_camera(
    db: Session, camera_id: str, since_timestamp: float
) -> list[Incident]:
    """Used by the cooldown checker — fetch incidents within the cooldown window."""
    since_dt = datetime.utcfromtimestamp(since_timestamp)
    return (
        db.query(Incident)
        .filter(
            Incident.camera_id == camera_id,
            Incident.created_at >= since_dt,
        )
        .all()
    )


def mark_incident_alert_sent(db: Session, incident_id: int) -> Optional[Incident]:
    inc = get_incident(db, incident_id)
    if inc:
        inc.alert_sent = True
        db.commit()
        db.refresh(inc)
    return inc


def acknowledge_incident(
    db: Session, incident_id: int, responder: str, message: str = ""
) -> Optional[Incident]:
    inc = get_incident(db, incident_id)
    if inc:
        inc.acknowledged = True
        inc.ack_at = datetime.now(timezone.utc)
        # Log the acknowledgement in the same transaction (P2-17 fix: single atomic commit)
        ack = Acknowledgement(
            incident_id=incident_id,
            responder=responder,
            message=message,
        )
        db.add(ack)
        db.commit()   # single commit — both writes succeed or both fail
        db.refresh(inc)
    return inc


# ── Alerts ─────────────────────────────────────────────────────────────────────

def create_alert(db: Session, **kwargs) -> Alert:
    alert = Alert(**kwargs)
    db.add(alert)
    db.commit()
    db.refresh(alert)
    return alert


def update_alert_status(
    db: Session,
    alert_id: int,
    status: str,
    twilio_sid: str = None,
    error_message: str = None,
    retry_count: int = None,
) -> Optional[Alert]:
    alert = db.query(Alert).filter(Alert.id == alert_id).first()
    if alert:
        alert.status = status
        if twilio_sid is not None:
            alert.twilio_sid = twilio_sid
        if error_message is not None:
            alert.error_message = error_message
        if retry_count is not None:
            alert.retry_count = retry_count
        db.commit()
        db.refresh(alert)
    return alert


def get_alerts_for_incident(db: Session, incident_id: int) -> list[Alert]:
    return db.query(Alert).filter(Alert.incident_id == incident_id).all()


# ── Acknowledgements ───────────────────────────────────────────────────────────

def get_acks_for_incident(db: Session, incident_id: int) -> list[Acknowledgement]:
    return (
        db.query(Acknowledgement)
        .filter(Acknowledgement.incident_id == incident_id)
        .all()
    )

