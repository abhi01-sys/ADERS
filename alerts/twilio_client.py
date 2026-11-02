"""
alerts/twilio_client.py
────────────────────────
Sends SMS and voice-call alerts via Twilio.

Features:
  • SMS with incident details + Google Maps link
  • Voice call (reads alert aloud via TwiML)
  • Retry up to MAX_RETRIES on failure
  • Logs every attempt to the database

All credentials come from .env — never hardcoded here.
"""

import os
import time
from pathlib import Path
from datetime import datetime
from typing import Optional

from dotenv import load_dotenv
from loguru import logger

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")

try:
    from twilio.rest import Client as TwilioClient
    from twilio.base.exceptions import TwilioRestException
    TWILIO_AVAILABLE = True
except ImportError:
    TWILIO_AVAILABLE = False
    logger.warning("twilio package not installed. Alerts will be logged only.")

from alerts.contact_manager import get_contacts, get_max_retries, get_maps_url


def _build_sms_body(incident: dict) -> str:
    """Build the SMS message string from an incident dict."""
    maps_url = get_maps_url(
        incident.get("location_lat"),
        incident.get("location_lon"),
    )
    ts = datetime.utcfromtimestamp(incident.get("created_at_ts", time.time()))
    time_str = ts.strftime("%Y-%m-%d %H:%M UTC")
    severity = incident.get("severity", "unknown").upper()

    return (
        f"[ADERS ALERT] {severity} ACCIDENT DETECTED\n"
        f"Time    : {time_str}\n"
        f"Camera  : {incident.get('camera_id', 'N/A')}\n"
        f"Confidence: {incident.get('confidence', 0)*100:.1f}%\n"
        f"Location: {maps_url}\n"
        f"Snapshot: {incident.get('snapshot_url', 'N/A')}\n"
        f"Incident ID: {incident.get('id', 'N/A')}\n"
        f"Reply ACK{incident.get('id','0')} to confirm response."
    )


def _build_twiml_say(incident: dict) -> str:
    """Build a simple TwiML response that reads the alert aloud."""
    severity = incident.get("severity", "unknown")
    cam = incident.get("camera_id", "unknown")
    return (
        f"<Response>"
        f"<Say voice='alice'>"
        f"Alert from ADERS. A {severity} road accident has been detected "
        f"at camera {cam}. Please respond immediately. "
        f"Send a text message with A C K {incident.get('id', '0')} to confirm."
        f"</Say>"
        f"<Pause length='1'/>"
        f"</Response>"
    )


class AlertSender:
    def __init__(self):
        load_dotenv(ROOT / ".env", override=True)
        self.sid   = os.getenv("TWILIO_ACCOUNT_SID", "").strip()
        self.token = os.getenv("TWILIO_AUTH_TOKEN", "").strip()
        self.from_ = os.getenv("TWILIO_FROM_NUMBER", "").strip()
        self.max_retries = get_max_retries()

        if TWILIO_AVAILABLE and self.sid and self.token and self.from_:
            try:
                self.client = TwilioClient(self.sid, self.token)
                self.enabled = True
                logger.info(f"Twilio configured for alerts (From: {self.from_})")
            except Exception as e:
                self.client = None
                self.enabled = False
                logger.error(f"Failed to initialize Twilio client: {e}")
        else:
            self.client = None
            self.enabled = False
            logger.warning("Twilio credentials missing or incomplete in .env — alerts will print to console only.")

    def _send_sms(self, to: str, body: str) -> tuple[str, str]:
        """Returns (twilio_sid, status)."""
        if not self.enabled:
            logger.info(f"[MOCK SMS → {to}]\n{body}")
            return "MOCK_SID", "sent"

        for attempt in range(1, self.max_retries + 1):
            try:
                msg = self.client.messages.create(body=body, from_=self.from_, to=to)
                logger.success(f"SMS alert successfully sent to {to} (SID: {msg.sid})")
                return msg.sid, "sent"
            except TwilioRestException as e:
                if e.code == 21608:
                    logger.error(
                        f"Twilio Trial Account Error (21608): The recipient number '{to}' is not verified. "
                        "Trial accounts can only send to verified numbers. "
                        "Verify it at: https://console.twilio.com/us1/develop/phone-numbers/manage/verified"
                    )
                    break
                elif e.code == 21211:
                    logger.error(f"Twilio Error (21211): Invalid phone number '{to}'. Must include country code, e.g. +91XXXXXXXXXX")
                    break
                elif e.code == 21606:
                    logger.error(f"Twilio Error (21606): The 'From' number '{self.from_}' is not a valid Twilio number for this account.")
                    break
                else:
                    logger.warning(f"SMS attempt {attempt}/{self.max_retries} failed for {to}: [{e.code}] {e.msg}")

                if attempt < self.max_retries:
                    time.sleep(2)
            except Exception as e:
                logger.error(f"Unexpected error sending SMS to {to}: {e}")
                break
        return "", "failed"

    def _place_call(self, to: str, twiml_xml: str) -> tuple[str, str]:
        """Returns (twilio_sid, status)."""
        if not self.enabled:
            logger.info(f"[MOCK CALL → {to}]")
            return "MOCK_CALL_SID", "sent"

        # Trial accounts require a public URL parameter; paid accounts can also use inline twiml
        twiml_url = os.getenv("TWILIO_TWIML_BIN_URL", "").strip() or "https://demo.twilio.com/welcome/voice/"

        for attempt in range(1, self.max_retries + 1):
            try:
                try:
                    call = self.client.calls.create(
                        url=twiml_url,
                        from_=self.from_,
                        to=to,
                    )
                except TwilioRestException:
                    # Fallback to inline twiml
                    call = self.client.calls.create(
                        twiml=twiml_xml,
                        from_=self.from_,
                        to=to,
                    )

                logger.success(f"Emergency call placed to {to} (SID: {call.sid})")
                return call.sid, "sent"
            except TwilioRestException as e:
                logger.warning(f"Call attempt {attempt}/{self.max_retries} failed: {e}")
                if attempt < self.max_retries:
                    time.sleep(2)
        return "", "failed"

    def send_alerts(self, incident: dict, db=None) -> list[dict]:
        """
        Main entry point — send SMS and voice calls.
        Strictly limits to at most ONE voice call per accident incident.
        Deduplicates identical phone numbers across emergency contacts.
        """
        severity = incident.get("severity", "minor")
        contacts = get_contacts(severity)

        sms_body  = _build_sms_body(incident)
        twiml_xml = _build_twiml_say(incident)

        results = []
        call_placed = False         # Enforce strictly 1 call per accident!
        messaged_numbers = set()    # Prevent duplicate SMS to the same phone
        called_numbers = set()      # Prevent duplicate calls to the same phone

        for contact in contacts:
            phone = contact["phone"]
            sms_status = "skipped"

            # 1. Send SMS (at most once per unique phone number)
            if contact["receive_sms"] and phone not in messaged_numbers:
                sid, sms_status = self._send_sms(phone, sms_body)
                messaged_numbers.add(phone)
                result = {
                    "contact_name":  contact["name"],
                    "contact_phone": phone,
                    "alert_type":    "sms",
                    "status":        sms_status,
                    "twilio_sid":    sid,
                }
                if db:
                    from database import crud
                    crud.create_alert(db, incident_id=incident["id"], **result)
                results.append(result)

            # 2. Voice Call: STRICTLY ONE call per accident incident!
            # Placed to the first available emergency responder who hasn't been called yet.
            should_place_call = (
                not call_placed
                and phone not in called_numbers
                and (contact.get("receive_call", False) or sms_status == "failed")
            )

            if should_place_call:
                logger.info(f"Initiating single emergency call for incident #{incident.get('id', 'N/A')} to {phone}...")
                sid, status_call = self._place_call(phone, twiml_xml)
                call_placed = True          # Lock: no further calls for this accident
                called_numbers.add(phone)
                result = {
                    "contact_name":  contact["name"],
                    "contact_phone": phone,
                    "alert_type":    "call",
                    "status":        status_call,
                    "twilio_sid":    sid,
                }
                if db:
                    from database import crud
                    crud.create_alert(db, incident_id=incident["id"], **result)
                results.append(result)

        return results

