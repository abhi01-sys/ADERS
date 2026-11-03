"""
api/main.py
────────────
FastAPI application entry point.

Endpoints:
  GET  /ping                    → health check
  GET  /incidents               → list all incidents
  GET  /incidents/{id}          → get one incident
  POST /incidents               → detector posts a new incident here
  POST /incidents/{id}/ack      → responder acknowledges
  GET  /incidents/{id}/alerts   → list alerts for incident
  WS   /ws                      → live dashboard stream

Run locally:
    uvicorn api.main:app --reload --port 8000
"""

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from loguru import logger

from database.db import engine
from database.models import Base
from api.routes.incidents import router as incidents_router
from api.routes.stream import router as stream_router
from alerts.escalation import EscalationManager

ROOT = Path(__file__).resolve().parent.parent
escalation_mgr = EscalationManager()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # ── Startup ──────────────────────────────────────────────────────────────
    import asyncio
    import api.routes.incidents as _incidents_mod
    # P1-9 fix: store the running event loop so sync _broadcast() can schedule coroutines
    _incidents_mod._event_loop = asyncio.get_running_loop()

    logger.info("Creating database tables if not exist...")
    Base.metadata.create_all(bind=engine)

    logger.info("Starting escalation monitor thread...")
    escalation_mgr.start()

    yield  # ← app runs here

    # ── Shutdown ─────────────────────────────────────────────────────────────
    logger.info("Stopping escalation monitor...")
    escalation_mgr.stop()


app = FastAPI(
    title="ADERS API",
    description="AI-Powered Accident Detection & Emergency Response System",
    version="0.1.0",
    lifespan=lifespan,
)

import os
# Allow React (localhost:5173 / 3000) and Streamlit (localhost:8501), plus cloud domains
cors_origins = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "http://localhost:8501",
    "http://127.0.0.1:8501",
    "http://localhost:3000",
]
if os.getenv("RENDER") or os.getenv("ALLOW_ALL_ORIGINS", "true").lower() == "true":
    cors_origins = ["*"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Serve media files (snapshots, clips) statically
snapshots_dir = ROOT / "media" / "snapshots"
clips_dir     = ROOT / "media" / "clips"
snapshots_dir.mkdir(parents=True, exist_ok=True)
clips_dir.mkdir(parents=True, exist_ok=True)

app.mount("/snapshots", StaticFiles(directory=str(snapshots_dir)), name="snapshots")
app.mount("/clips",     StaticFiles(directory=str(clips_dir)),     name="clips")

# Register routers (both with and without /api prefix for dev + prod unified support)
app.include_router(incidents_router)
app.include_router(incidents_router, prefix="/api")
app.include_router(stream_router)


@app.get("/ping", tags=["health"])
@app.get("/api/ping", tags=["health"])
def ping():
    return {"status": "ok", "service": "ADERS API"}


# Serve React Frontend Build if available (for unified Render deployment)
frontend_dist = ROOT / "dashboard_react" / "dist"
if frontend_dist.exists() and (frontend_dist / "index.html").exists():
    app.mount("/", StaticFiles(directory=str(frontend_dist), html=True), name="frontend")


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run("api.main:app", host="0.0.0.0", port=port, reload=True)

