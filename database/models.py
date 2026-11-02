"""
database/models.py
──────────────────
SQLAlchemy ORM models → maps Python classes to SQLite tables.

Tables:
  incidents      — every confirmed accident detected
  alerts         — every SMS/call sent (one row per contact per incident)
  acknowledgements — responder replies ("ack")
"""

from datetime import datetime, timezone
from sqlalchemy import (
    Column, Integer, String, Float, Boolean,
    DateTime, ForeignKey, Text
)
from sqlalchemy.orm import relationship

from database.db import Base


class Incident(Base):
    __tablename__ = "incidents"

    id           = Column(Integer, primary_key=True, index=True)
    created_at   = Column(DateTime, default=lambda: datetime.now(timezone.utc), index=True)

    # Camera info
    camera_id    = Column(String(64), nullable=False, index=True)
    location_lat = Column(Float, nullable=True)   # from config.yaml cameras[].location_lat
    location_lon = Column(Float, nullable=True)

    # Detection metadata
    confidence   = Column(Float, nullable=False)
    severity     = Column(String(16), nullable=False)  # "minor" | "major"
    frame_index  = Column(Integer, nullable=True)

    # Evidence paths (relative to project root)
    snapshot_path = Column(String(256), nullable=True)
    clip_path     = Column(String(256), nullable=True)

    # Alert / ack status
    alert_sent   = Column(Boolean, default=False)
    acknowledged = Column(Boolean, default=False)
    ack_at       = Column(DateTime, nullable=True)

    # Relationships
    alerts          = relationship("Alert", back_populates="incident",
                                   cascade="all, delete-orphan")
    acknowledgements = relationship("Acknowledgement", back_populates="incident",
                                    cascade="all, delete-orphan")

    def to_dict(self) -> dict:
        return {
            "id":            self.id,
            "created_at":    self.created_at.isoformat() if self.created_at else None,
            # P2-16 fix: provide unix timestamp so SMS body shows correct incident time
            "created_at_ts": self.created_at.timestamp() if self.created_at else None,
            "camera_id":     self.camera_id,
            "location_lat":  self.location_lat,
            "location_lon":  self.location_lon,
            "confidence":    self.confidence,
            "severity":      self.severity,
            "snapshot_path": self.snapshot_path,
            "clip_path":     self.clip_path,
            "alert_sent":    self.alert_sent,
            "acknowledged":  self.acknowledged,
            "ack_at":        self.ack_at.isoformat() if self.ack_at else None,
        }


class Alert(Base):
    __tablename__ = "alerts"

    id          = Column(Integer, primary_key=True, index=True)
    incident_id = Column(Integer, ForeignKey("incidents.id"), nullable=False)
    sent_at     = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    contact_name  = Column(String(128))
    contact_phone = Column(String(32))
    alert_type    = Column(String(16))   # "sms" | "call" | "whatsapp"
    status        = Column(String(32))   # "sent" | "failed" | "retrying"
    twilio_sid    = Column(String(64), nullable=True)
    error_message = Column(Text, nullable=True)
    retry_count   = Column(Integer, default=0)

    incident = relationship("Incident", back_populates="alerts")

    def to_dict(self) -> dict:
        return {
            "id":            self.id,
            "incident_id":   self.incident_id,
            "sent_at":       self.sent_at.isoformat() if self.sent_at else None,
            "contact_name":  self.contact_name,
            "contact_phone": self.contact_phone,
            "alert_type":    self.alert_type,
            "status":        self.status,
            "retry_count":   self.retry_count,
        }


class Acknowledgement(Base):
    __tablename__ = "acknowledgements"

    id           = Column(Integer, primary_key=True, index=True)
    incident_id  = Column(Integer, ForeignKey("incidents.id"), nullable=False)
    received_at  = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    responder    = Column(String(128))   # phone number or name
    message      = Column(Text, nullable=True)

    incident = relationship("Incident", back_populates="acknowledgements")

    def to_dict(self) -> dict:
        return {
            "id":          self.id,
            "incident_id": self.incident_id,
            "received_at": self.received_at.isoformat() if self.received_at else None,
            "responder":   self.responder,
            "message":     self.message,
        }

