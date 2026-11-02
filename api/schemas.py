"""
api/schemas.py
──────────────
Pydantic models for FastAPI request/response validation.
These are separate from the SQLAlchemy ORM models in database/models.py.
"""

from datetime import datetime
from typing import Optional
from pydantic import BaseModel, ConfigDict, Field


# ── Incidents ──────────────────────────────────────────────────────────────────

class IncidentCreate(BaseModel):
    """Payload the detector POSTs when a new accident is confirmed."""
    camera_id:    str
    confidence:   float = Field(..., ge=0.0, le=1.0)
    severity:     str   = Field(..., pattern="^(minor|major)$")
    location_lat: Optional[float] = None
    location_lon: Optional[float] = None
    snapshot_path: Optional[str]  = None
    clip_path:     Optional[str]  = None
    frame_index:   Optional[int]  = None


class IncidentResponse(BaseModel):
    id:            int
    created_at:    datetime
    camera_id:     str
    confidence:    float
    severity:      str
    location_lat:  Optional[float]
    location_lon:  Optional[float]
    snapshot_path: Optional[str]
    clip_path:     Optional[str]
    alert_sent:    bool
    acknowledged:  bool
    ack_at:        Optional[datetime]

    model_config = ConfigDict(from_attributes=True)


# ── Acknowledgements ───────────────────────────────────────────────────────────

class AckCreate(BaseModel):
    responder: str = Field(..., min_length=1)
    message:   Optional[str] = ""


class AckResponse(BaseModel):
    incident_id: int
    acknowledged: bool
    ack_at:      Optional[datetime]

    model_config = ConfigDict(from_attributes=True)


# ── Alerts ─────────────────────────────────────────────────────────────────────

class AlertResponse(BaseModel):
    id:            int
    incident_id:   int
    sent_at:       datetime
    contact_name:  str
    contact_phone: str
    alert_type:    str
    status:        str
    retry_count:   int

    model_config = ConfigDict(from_attributes=True)


# ── WebSocket broadcast payload ────────────────────────────────────────────────

class WSEvent(BaseModel):
    event:    str           # "new_incident" | "ack_received" | "alert_sent"
    payload:  dict

