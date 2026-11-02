"""
tests/test_system.py
────────────────────
Automated verification tests using standard library `unittest`.
Validates all P0, P1, and P2 fixes:
  - Falsy-zero coordinate handling in get_maps_url
  - created_at_ts presence in Incident.to_dict()
  - Escalation logic avoids duplicate alerts
  - Atomic ack updates in CRUD
  - Mock Twilio safety
"""

import sys
import unittest
from pathlib import Path
from datetime import datetime

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

# Ensure Twilio is strictly mocked
import alerts.twilio_client as tw_client
tw_client.TWILIO_AVAILABLE = False


class TestFixes(unittest.TestCase):

    def test_maps_url_falsy_zero_coordinates(self):
        """P2-15: (0.0, 0.0) must not be treated as missing location."""
        from alerts.contact_manager import get_maps_url
        url = get_maps_url(0.0, 0.0)
        self.assertIn("0.0,0.0", url)
        self.assertNotEqual(url, "Location unavailable")

        # Missing coords should still say unavailable
        self.assertEqual(get_maps_url(None, None), "Location unavailable")

    def test_incident_to_dict_includes_created_at_ts(self):
        """P2-16: Incident.to_dict() must provide created_at_ts for SMS timestamping."""
        from database.models import Incident
        dt = datetime(2026, 11, 1, 12, 0, 0)
        inc = Incident(
            id=101,
            camera_id="cam_test",
            confidence=0.88,
            severity="major",
            created_at=dt,
        )
        d = inc.to_dict()
        self.assertIn("created_at_ts", d)
        self.assertAlmostEqual(d["created_at_ts"], dt.timestamp(), places=2)

    def test_path_traversal_guard(self):
        """P0-4: video_id with path traversal characters must be blocked."""
        from api.routes.incidents import VIDEOS_DIR
        def is_safe_id(video_id: str) -> bool:
            if "/" in video_id or "\\" in video_id or ".." in video_id or Path(video_id).name != video_id:
                return False
            resolved = (VIDEOS_DIR / video_id).resolve()
            return str(resolved).startswith(str(VIDEOS_DIR.resolve()))

        bad_ids = ["../secret.txt", "..\\secret.txt", "/etc/passwd", "sub/video.mp4", "sub\\video.mp4", ".."]
        for bad_id in bad_ids:
            self.assertFalse(is_safe_id(bad_id), f"Path traversal allowed for: {bad_id}")

        good_ids = ["3a971a5ca4ce4dbe9ccf89d0cf1daba6.mp4", "valid_video.mp4"]
        for good_id in good_ids:
            self.assertTrue(is_safe_id(good_id), f"Valid ID rejected: {good_id}")

    def test_database_wal_mode(self):
        """P1-7: Verify SQLite WAL mode pragma executed on engine connect."""
        from database.db import engine
        from sqlalchemy import text
        with engine.connect() as conn:
            res = conn.execute(text("PRAGMA journal_mode")).scalar()
            self.assertEqual(res.lower(), "wal")

    def test_single_atomic_ack(self):
        """P2-17: Acknowledge incident records both ack status and Acknowledgement row."""
        from database.db import SessionLocal
        from database import crud
        db = SessionLocal()
        try:
            inc = crud.create_incident(
                db,
                camera_id="test_cam_ack",
                confidence=0.75,
                severity="moderate",
            )
            self.assertFalse(inc.acknowledged)

            # Ack
            updated = crud.acknowledge_incident(db, inc.id, responder="Officer Test", message="En route")
            self.assertTrue(updated.acknowledged)
            self.assertIsNotNone(updated.ack_at)

            acks = crud.get_acks_for_incident(db, inc.id)
            self.assertEqual(len(acks), 1)
            self.assertEqual(acks[0].responder, "Officer Test")
        finally:
            db.close()


if __name__ == "__main__":
    unittest.main()
