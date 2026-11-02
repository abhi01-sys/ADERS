"""
api/routes/stream.py
─────────────────────
WebSocket endpoint — streams live events to the Streamlit dashboard.

Connects at: ws://localhost:8000/ws
Events pushed:
  {"event": "new_incident",  "payload": {...}}
  {"event": "ack_received",  "payload": {...}}
  {"event": "alert_sent",    "payload": {...}}
"""

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from loguru import logger

router = APIRouter(tags=["stream"])


class ConnectionManager:
    """Keeps track of all active WebSocket connections."""

    def __init__(self):
        self.active_connections: list[WebSocket] = []

    async def connect(self, ws: WebSocket):
        await ws.accept()
        self.active_connections.append(ws)
        logger.info(f"WS client connected. Total: {len(self.active_connections)}")

    def disconnect(self, ws: WebSocket):
        if ws in self.active_connections:
            self.active_connections.remove(ws)
        logger.info(f"WS client disconnected. Total: {len(self.active_connections)}")

    async def broadcast(self, message: dict):
        """Send a JSON message to every connected client."""
        dead = []
        for ws in self.active_connections:
            try:
                await ws.send_json(message)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.disconnect(ws)


# Singleton — shared by the router and the incident endpoints
manager = ConnectionManager()


@router.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    await manager.connect(ws)
    try:
        while True:
            # Keep the connection alive; we don't process client messages
            await ws.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(ws)

