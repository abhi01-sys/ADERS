"""
api/routes/incidents.py
────────────────────────
REST endpoints for incident management.

GET  /incidents              → list all incidents (paginated)
GET  /incidents/{id}         → single incident detail
POST /incidents              → create new incident (called by detector)
POST /incidents/{id}/ack     → acknowledge an incident
GET  /incidents/{id}/alerts  → list alerts sent for an incident
"""

from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, UploadFile, File, Form
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
import tempfile
import time
import uuid
import cv2
import numpy as np
import base64
from pathlib import Path

from database.db import get_db, SessionLocal
from database import crud
from loguru import logger
from api.schemas import (
    IncidentCreate, IncidentResponse,
    AckCreate, AckResponse,
    AlertResponse,
)
from alerts.twilio_client import AlertSender
from alerts.escalation import is_in_cooldown, record_alert
from api.routes.stream import manager

router = APIRouter(prefix="/incidents", tags=["incidents"])
_sender = AlertSender()


_event_loop = None  # Set at startup by lifespan; used for thread-safe WS broadcasts


def _broadcast(event: str, payload: dict):
    """Fire-and-forget WS broadcast from any sync context (P1-9 fix)."""
    import asyncio
    try:
        loop = _event_loop or asyncio.get_event_loop()
        if loop.is_running():
            asyncio.run_coroutine_threadsafe(
                manager.broadcast({"event": event, "payload": payload}), loop
            )
    except Exception:
        pass


def dispatch_incident_alerts(incident_dict: dict, camera_id: str, incident_id: int):
    """Sends Twilio alerts and logs to database with dedicated session."""
    if is_in_cooldown(camera_id):
        logger.info(f"Alert suppressed: Camera '{camera_id}' is in active cooldown window.")
        return

    record_alert(camera_id)  # Lock cooldown immediately to suppress repeated calls

    with SessionLocal() as bg_db:
        try:
            _sender.send_alerts(incident_dict, db=bg_db)
            crud.mark_incident_alert_sent(bg_db, incident_id)
        except Exception as exc:
            logger.error(f"Alert dispatch failed: {exc}")


# ── List incidents ─────────────────────────────────────────────────────────────
@router.get("", response_model=list[IncidentResponse])
@router.get("/", response_model=list[IncidentResponse])
def list_incidents(skip: int = 0, limit: int = 50, db: Session = Depends(get_db)):
    return crud.get_all_incidents(db, skip=skip, limit=limit)


# ── Get single incident ────────────────────────────────────────────────────────
@router.get("/{incident_id}", response_model=IncidentResponse)
def get_incident(incident_id: int, db: Session = Depends(get_db)):
    inc = crud.get_incident(db, incident_id)
    if not inc:
        raise HTTPException(status_code=404, detail="Incident not found")
    return inc


from pathlib import Path
import yaml

ROOT = Path(__file__).resolve().parent.parent.parent
_cfg = yaml.safe_load((ROOT / "config.yaml").read_text())
_CAMERA_COORDS = {
    c["id"]: (c.get("location_lat"), c.get("location_lon"))
    for c in _cfg.get("cameras", [])
}

# ── Create incident (called by the detector) ───────────────────────────────────
@router.post("", response_model=IncidentResponse, status_code=201)
@router.post("/", response_model=IncidentResponse, status_code=201)
def create_incident(
    body: IncidentCreate,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    # ── Cooldown check ────────────────────────────────────────────────────────
    if is_in_cooldown(body.camera_id):
        raise HTTPException(
            status_code=429,
            detail=f"Cooldown active for camera {body.camera_id}. Duplicate alert suppressed.",
        )

    # ── Auto-fill coordinates from config.yaml if not provided in payload ─────
    data = body.model_dump()
    if (data.get("location_lat") is None or data.get("location_lon") is None) and body.camera_id in _CAMERA_COORDS:
        lat, lon = _CAMERA_COORDS[body.camera_id]
        data["location_lat"] = lat
        data["location_lon"] = lon

    # ── Persist to DB ─────────────────────────────────────────────────────────
    inc = crud.create_incident(db, **data)

    # ── Broadcast real-time event to dashboards ──────────────────────────────
    inc_data = inc.to_dict()
    background_tasks.add_task(manager.broadcast, {"event": "new_incident", "payload": inc_data})

    # ── Send Twilio alerts in background (with dedicated DB session) ─────────
    background_tasks.add_task(dispatch_incident_alerts, inc_data, body.camera_id, inc.id)

    return inc


# ── Acknowledge incident ───────────────────────────────────────────────────────
@router.post("/{incident_id}/ack", response_model=AckResponse)
def ack_incident(
    incident_id: int,
    body: AckCreate,
    db: Session = Depends(get_db),
):
    inc = crud.acknowledge_incident(db, incident_id, body.responder, body.message)
    if not inc:
        raise HTTPException(status_code=404, detail="Incident not found")
    _broadcast("ack_received", inc.to_dict())
    # P2-14 fix: return explicit dict so AckResponse fields map correctly
    return {"incident_id": inc.id, "acknowledged": inc.acknowledged, "ack_at": inc.ack_at}


# ── List alerts for an incident ────────────────────────────────────────────────
@router.get("/{incident_id}/alerts", response_model=list[AlertResponse])
def get_alerts(incident_id: int, db: Session = Depends(get_db)):
    return crud.get_alerts_for_incident(db, incident_id)


# ── Run Video Detection on Uploaded File ───────────────────────────────────────

@router.post("/detect-video")
async def detect_video(
    file: UploadFile = File(...),
    camera_id: str = Form("CAM_DEMO_01"),
    location_lat: float = Form(12.9716),
    location_lon: float = Form(77.5946),
    conf_threshold: float = Form(0.50),
    confirmation_frames: int = Form(10),
    db: Session = Depends(get_db),
):
    """
    Accepts an uploaded video file, executes YOLOv8 fine-tuned detection
    with frame persistence confirmation, saves snapshot on accident,
    and returns detected incidents.
    """
    from detection.detector import AccidentDetector
    detector = AccidentDetector(
        conf_threshold=conf_threshold,
        confirmation_frames=confirmation_frames,
    )

    # Save uploaded bytes to temporary file for OpenCV
    # P0-5: enforce upload size limit (50 MB max)
    MAX_BYTES = 50 * 1024 * 1024
    content = await file.read(MAX_BYTES + 1)
    if len(content) > MAX_BYTES:
        raise HTTPException(status_code=413, detail="File too large. Maximum upload size is 50 MB.")
    suffix = Path(file.filename).suffix or ".mp4"
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        tmp.write(content)
        tmp_path = tmp.name

    detected_incidents = []
    cap = cv2.VideoCapture(tmp_path)

    try:
        frame_idx = 0
        while cap.isOpened():
            ret, frame = cap.read()
            if not ret:
                break
            frame_idx += 1

            # Process every 2nd frame for faster inference
            if frame_idx % 2 != 0:
                continue

            _, inc_info = detector.process_frame(
                frame=frame,
                camera_id=camera_id,
                location_lat=location_lat,
                location_lon=location_lon,
            )

            if inc_info:
                # Add to DB
                inc_row = crud.create_incident(db, **inc_info)
                inc_dict = inc_row.to_dict()
                detected_incidents.append(inc_dict)
                await manager.broadcast({"event": "new_incident", "payload": inc_dict})
                import threading
                threading.Thread(
                    target=dispatch_incident_alerts,
                    args=(inc_dict, camera_id, inc_row.id),
                    daemon=True,
                ).start()
    finally:
        cap.release()
        try:
            Path(tmp_path).unlink(missing_ok=True)
        except Exception:
            pass

    return {
        "status": "completed",
        "processed_frames": frame_idx,
        "accidents_detected": len(detected_incidents),
        "incidents": detected_incidents,
    }


# ── Live Detection Streaming Pipelines ─────────────────────────────────────────

VIDEOS_DIR = ROOT / "media" / "videos"
VIDEOS_DIR.mkdir(parents=True, exist_ok=True)
_PRELOADED_MODEL = None
_shared_webcam_detector = None


def _get_preloaded_model():
    """Caches YOLO in memory to avoid reloading weights repeatedly."""
    global _PRELOADED_MODEL
    if _PRELOADED_MODEL is None:
        from ultralytics import YOLO
        from detection.detector import DEFAULT_WEIGHTS
        _PRELOADED_MODEL = YOLO(str(DEFAULT_WEIGHTS))
    return _PRELOADED_MODEL


@router.post("/upload-video-stream")
async def upload_video_stream(file: UploadFile = File(...)):
    """Saves uploaded video file for real-time MJPEG live detection streaming."""
    # P0-5: enforce upload size limit (50 MB max)
    MAX_BYTES = 50 * 1024 * 1024
    content = await file.read(MAX_BYTES + 1)
    if len(content) > MAX_BYTES:
        raise HTTPException(status_code=413, detail="File too large. Maximum upload size is 50 MB.")
    ext = Path(file.filename).suffix or ".mp4"
    video_id = f"{uuid.uuid4().hex}{ext}"
    save_path = VIDEOS_DIR / video_id
    save_path.write_bytes(content)
    return {"video_id": video_id, "filename": file.filename}


@router.get("/stream-video/{video_id}")
def stream_video(
    video_id: str,
    camera_id: str = "CAM_LIVE_01",
    location_lat: float = 12.9716,
    location_lon: float = 77.5946,
    conf_threshold: float = 0.50,
    confirmation_frames: int = 10,
    skip_frames: int = 2,
):
    """
    Streams an annotated video with live YOLO bounding boxes, classes,
    and HUD banners as a real-time MJPEG multipart stream.
    P1-8 fix: No DB session injected here — session opened short-lived only on incident.
    """
    # P0-4: path traversal guard — video_id must be a plain filename with no directory components
    if "/" in video_id or "\\" in video_id or ".." in video_id or Path(video_id).name != video_id:
        raise HTTPException(status_code=400, detail="Invalid video_id.")
    video_path = (VIDEOS_DIR / video_id).resolve()
    if not str(video_path).startswith(str(VIDEOS_DIR.resolve())):
        raise HTTPException(status_code=400, detail="Invalid video_id.")
    if not video_path.exists():
        raise HTTPException(status_code=404, detail="Video file not found")

    def iter_frames():
        from detection.detector import AccidentDetector
        model = _get_preloaded_model()
        detector = AccidentDetector(
            conf_threshold=conf_threshold,
            confirmation_frames=confirmation_frames,
            model=model,
            imgsz=416,           # 416x416 for 2x faster CPU inference
            auto_dispatch=False,  # Prevent blocking HTTP loopback call
        )
        cap = cv2.VideoCapture(str(video_path))
        fps = cap.get(cv2.CAP_PROP_FPS) or 25.0
        frame_delay = max(0.015, 1.0 / fps)
        last_annotated = None
        frame_idx = 0

        try:
            while cap.isOpened():
                loop_start = time.time()
                ret, frame = cap.read()
                if not ret:
                    break
                frame_idx += 1

                # Resize frame to standard 640 width if larger (saves 70% CPU encoding & bandwidth)
                h, w = frame.shape[:2]
                if w > 640:
                    scale = 640.0 / w
                    frame = cv2.resize(frame, (640, int(h * scale)))

                # Subsample: Run full YOLO inference every Nth frame, reuse bounding boxes on skipped frame
                if frame_idx % skip_frames == 0 or last_annotated is None:
                    annotated, inc_info = detector.process_frame(
                        frame=frame,
                        camera_id=camera_id,
                        location_lat=location_lat,
                        location_lon=location_lon,
                    )
                    last_annotated = annotated

                    if inc_info:
                        # P1-8: short-lived session — don't hold session for entire stream
                        with SessionLocal() as short_db:
                            inc_row = crud.create_incident(short_db, **inc_info)
                            inc_dict = inc_row.to_dict()
                        _broadcast("new_incident", inc_dict)
                        import threading
                        threading.Thread(
                            target=dispatch_incident_alerts,
                            args=(inc_dict, camera_id, inc_dict["id"]),
                            daemon=True,
                        ).start()
                else:
                    annotated = last_annotated if last_annotated is not None else frame

                _, jpeg = cv2.imencode(".jpg", annotated, [cv2.IMWRITE_JPEG_QUALITY, 72])
                yield (
                    b"--frame\r\n"
                    b"Content-Type: image/jpeg\r\n\r\n"
                    + jpeg.tobytes()
                    + b"\r\n"
                )

                elapsed = time.time() - loop_start
                if elapsed < frame_delay:
                    time.sleep(frame_delay - elapsed)
        finally:
            cap.release()

    return StreamingResponse(
        iter_frames(),
        media_type="multipart/x-mixed-replace; boundary=frame",
    )


@router.post("/detect-frame")
async def detect_frame(
    file: UploadFile = File(...),
    camera_id: str = Form("CAM_WEBCAM_01"),
    location_lat: float = Form(12.9716),
    location_lon: float = Form(77.5946),
    conf_threshold: float = Form(0.50),
    confirmation_frames: int = Form(8),
    db: Session = Depends(get_db),
):
    """
    Processes a single frame (e.g. from live browser webcam) and returns
    annotated base64 JPEG with bounding boxes and any confirmed incident.
    """
    global _shared_webcam_detector
    from detection.detector import AccidentDetector
    if _shared_webcam_detector is None:
        model = _get_preloaded_model()
        _shared_webcam_detector = AccidentDetector(
            conf_threshold=conf_threshold,
            confirmation_frames=confirmation_frames,
            model=model,
            imgsz=384,          # Highly responsive webcam inference size
            auto_dispatch=False, # Prevent blocking HTTP call
        )
    else:
        _shared_webcam_detector.conf_threshold = conf_threshold
        _shared_webcam_detector.confirmation_frames = confirmation_frames

    content = await file.read()
    nparr = np.frombuffer(content, np.uint8)
    frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
    if frame is None:
        raise HTTPException(status_code=400, detail="Invalid image frame")

    # Resize if frame width > 480 for fast webcam inference
    h, w = frame.shape[:2]
    if w > 480:
        scale = 480.0 / w
        frame = cv2.resize(frame, (480, int(h * scale)))

    annotated, inc_info = _shared_webcam_detector.process_frame(
        frame=frame,
        camera_id=camera_id,
        location_lat=location_lat,
        location_lon=location_lon,
    )

    inc_dict = None
    if inc_info:
        inc_row = crud.create_incident(db, **inc_info)
        inc_dict = inc_row.to_dict()
        _broadcast("new_incident", inc_dict)
        import threading
        threading.Thread(
            target=dispatch_incident_alerts,
            args=(inc_dict, camera_id, inc_row.id),
            daemon=True,
        ).start()

    _, jpeg = cv2.imencode(".jpg", annotated, [cv2.IMWRITE_JPEG_QUALITY, 70])
    b64_img = base64.b64encode(jpeg.tobytes()).decode("utf-8")

    return {
        "status": "ok",
        "image": f"data:image/jpeg;base64,{b64_img}",
        "accident_detected": bool(inc_info),
        "incident": inc_dict,
    }

