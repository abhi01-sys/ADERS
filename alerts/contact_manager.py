"""
alerts/contact_manager.py
──────────────────────────
Loads emergency contacts from config.yaml and optionally overrides phone
numbers from environment variables (so phones never have to be in source code).
"""

import os
from pathlib import Path
from typing import Optional
import yaml
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")

_cfg = yaml.safe_load((ROOT / "config.yaml").read_text())


def get_contacts(severity: str = "major") -> list[dict]:
    """
    Return the list of contacts to notify based on severity.
    - major  → all contacts that have receive_sms or receive_call = True
    - minor  → only SMS contacts (no voice calls)
    """
    load_dotenv(ROOT / ".env", override=True)
    env_overrides = {
        "ambulance": os.getenv("CONTACT_AMBULANCE_PHONE"),
        "police":    os.getenv("CONTACT_POLICE_PHONE"),
        "hospital":  os.getenv("CONTACT_HOSPITAL_PHONE"),
        "admin":     os.getenv("CONTACT_ADMIN_PHONE"),
    }

    contacts = []
    for c in _cfg.get("contacts", []):
        phone = env_overrides.get(c["role"]) or c.get("phone", "")
        if not phone or phone.startswith("+91XXXX"):
            # Skip placeholder phones
            continue

        entry = {
            "name":         c["name"],
            "role":         c["role"],
            "phone":        phone.strip(),
            "receive_sms":  c.get("receive_sms", True),
            # Only allow voice calls for major incidents
            "receive_call": c.get("receive_call", False) and severity == "major",
        }
        contacts.append(entry)
    return contacts


def get_cooldown_minutes() -> int:
    return _cfg.get("alerts", {}).get("cooldown_minutes", 5)


def get_ack_timeout() -> int:
    return _cfg.get("alerts", {}).get("ack_timeout_seconds", 30)


def get_max_retries() -> int:
    return _cfg.get("alerts", {}).get("max_retries", 3)


def get_maps_url(lat: Optional[float], lon: Optional[float]) -> str:
    base = _cfg.get("alerts", {}).get("maps_base_url", "https://www.google.com/maps?q=")
    # P2-15 fix: use 'is not None' so coordinate 0.0 is treated as valid
    if lat is not None and lon is not None:
        return f"{base}{lat},{lon}"
    return "Location unavailable"

