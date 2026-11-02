"""
detection/detector.py
─────────────────────
Core accident detection and tracking pipeline.
Handles:
  • YOLOv8 inference with ByteTrack tracking
  • N-frame persistence filter (false alarm reduction)
  • Evidence saving (snapshot image + incident clip)
  • Automatic incident reporting to FastAPI backend
"""

import time
import cv2
import httpx
import yaml
from pathlib import Path
from typing import Optional, Callable
from loguru import logger
from ultralytics import YOLO

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_WEIGHTS = ROOT / "model" / "runs" / "accident_model" / "weights" / "best.pt"
API_URL = "http://localhost:8000/incidents/"

# P1-13 fix: single source of truth from config.yaml
_cfg = yaml.safe_load((ROOT / "config.yaml").read_text())
_DEFAULT_CONF        = _cfg.get("detection", {}).get("confidence_threshold", 0.35)
_DEFAULT_CONFIRM     = _cfg.get("detection", {}).get("frame_confirmation_count", 6)

class AccidentDetector:
    def __init__(
        self,
        weights_path: Optional[str] = None,
        conf_threshold: float = None,      # None → read from config.yaml
        confirmation_frames: int = None,   # None → read from config.yaml
        api_url: str = API_URL,
        model: Optional[YOLO] = None,
        imgsz: int = 480,
        auto_dispatch: bool = False,
    ):
        # P1-13: use config.yaml values as default — callers may still override
        if conf_threshold is None:
            conf_threshold = _DEFAULT_CONF
        if confirmation_frames is None:
            confirmation_frames = _DEFAULT_CONFIRM

        if model is not None:
            self.model = model
        else:
            path = Path(weights_path) if weights_path else DEFAULT_WEIGHTS
            if not path.exists():
                raise FileNotFoundError(f"Model weights not found at: {path}")

            logger.info(f"Loading YOLOv8 model from: {path}")
            self.model = YOLO(str(path))

        self.conf_threshold = conf_threshold
        self.confirmation_frames = confirmation_frames
        self.api_url = api_url
        self.imgsz = imgsz
        self.auto_dispatch = auto_dispatch

        # State tracking
        self.consecutive_accident_frames = 0
        self.last_incident_time = 0.0
        self.cooldown_seconds = 60.0   # 60s minimum gap between repeat alerts for the same stream
        self.incident_triggered = False

    def process_frame(
        self,
        frame,
        camera_id: str = "demo_cam",
        location_lat: Optional[float] = None,
        location_lon: Optional[float] = None,
        on_incident_callback: Optional[Callable[[dict], None]] = None,
    ):
        """
        Processes a single BGR video frame.
        Returns:
            annotated_frame: BGR image with drawn bounding boxes and labels
            incident_info: dict if confirmed incident just triggered, else None
        """
        # Run YOLO inference with optimal image size for CPU throughput
        results = self.model.predict(
            source=frame,
            conf=self.conf_threshold,
            imgsz=self.imgsz,
            verbose=False,
        )

        annotated_frame = frame.copy()
        current_frame_has_accident = False
        highest_conf = 0.0
        dominant_severity = "minor"

        if results and len(results) > 0:
            r = results[0]
            boxes = r.boxes
            if boxes is not None and len(boxes) > 0:
                current_frame_has_accident = True
                annotated_frame = r.plot()  # draw bounding boxes, labels, and conf

                for box in boxes:
                    conf = float(box.conf[0].item())
                    cls_id = int(box.cls[0].item())
                    class_name = self.model.names.get(cls_id, str(cls_id)).lower()

                    if conf > highest_conf:
                        highest_conf = conf

                    # Class 1 = severe, Class 0 = moderate
                    if "severe" in class_name or cls_id == 1:
                        dominant_severity = "major"

        now = time.time()
        incident_info = None

        if current_frame_has_accident:
            self.consecutive_accident_frames += 1

            # Check if confirmed across consecutive frames and not in cooldown
            if (
                self.consecutive_accident_frames >= self.confirmation_frames
                and not self.incident_triggered
                and (now - self.last_incident_time) > self.cooldown_seconds
            ):
                self.incident_triggered = True
                self.last_incident_time = now

                # Save snapshot evidence
                snap_dir = ROOT / "media" / "snapshots"
                snap_dir.mkdir(parents=True, exist_ok=True)
                snap_filename = f"{camera_id}_{int(now)}.jpg"
                snap_path = snap_dir / snap_filename
                cv2.imwrite(str(snap_path), annotated_frame)

                incident_info = {
                    "camera_id": camera_id,
                    "confidence": round(highest_conf, 2),
                    "severity": dominant_severity,
                    "location_lat": location_lat,
                    "location_lon": location_lon,
                    "snapshot_path": f"media/snapshots/{snap_filename}",
                }

                # Send to FastAPI backend if running as standalone detector
                if self.auto_dispatch:
                    self._dispatch_incident(incident_info)

                if on_incident_callback:
                    on_incident_callback(incident_info)

        else:
            # Soft decay instead of hard reset: preserves detection if a single frame dips
            self.consecutive_accident_frames = max(0, self.consecutive_accident_frames - 1)
            if self.consecutive_accident_frames == 0:
                self.incident_triggered = False

        # Overlay status banner on the frame
        self._draw_status_overlay(
            annotated_frame,
            current_frame_has_accident,
            self.consecutive_accident_frames,
            dominant_severity if current_frame_has_accident else "None",
            self.incident_triggered,
        )

        return annotated_frame, incident_info

    def _draw_status_overlay(self, frame, has_accident, count, severity, triggered):
        """Draws top HUD banner showing detection status and frame persistence."""
        h, w = frame.shape[:2]
        # Semi-transparent HUD header
        overlay = frame.copy()
        cv2.rectangle(overlay, (0, 0), (w, 45), (20, 20, 20), -1)
        cv2.addWeighted(overlay, 0.7, frame, 0.3, 0, frame)

        if triggered:
            status_text = "🚨 ACCIDENT CONFIRMED - EMERGENCY ALERT DISPATCHED"
            color = (0, 0, 255)  # Bright Red
        elif has_accident:
            status_text = f"⚠️ DETECTING ({count}/{self.confirmation_frames} frames) | {severity.upper()}"
            color = (0, 165, 255)  # Orange
        else:
            status_text = "🟢 NORMAL TRAFFIC FLOW - NO ACCIDENT DETECTED"
            color = (0, 255, 0)  # Green

        cv2.putText(
            frame, status_text, (15, 30),
            cv2.FONT_HERSHEY_SIMPLEX, 0.65, color, 2, cv2.LINE_AA
        )

    def _dispatch_incident(self, incident: dict):
        """Dispatches confirmed incident to the local FastAPI backend."""
        try:
            with httpx.Client(timeout=3.0) as client:
                resp = client.post(self.api_url, json=incident)
                if resp.status_code in (200, 201):
                    logger.success(f"Incident reported to backend: ID {resp.json().get('id')}")
                else:
                    logger.warning(f"Backend returned status {resp.status_code}: {resp.text}")
        except Exception as exc:
            logger.error(f"Failed to post incident to backend: {exc}")

