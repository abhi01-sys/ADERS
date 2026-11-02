"""
dashboard/app.py
─────────────────
Streamlit dashboard for ADERS (Accident Detection & Emergency Response System).

Features:
  1. 🎥 Manual Video Test (Upload video from PC, run live YOLO detection)
  2. 📹 Live Webcam feed option
  3. 📍 Custom PC / College Campus GPS Location coordinates
  4. 📋 Live Incident history table with severity badges
  5. 🗺️ Interactive Folium map with exact GPS drop-pins & Google Maps links
  6. ✅ One-click Incident Acknowledgement
"""

import os
import sys
import time
import tempfile
from pathlib import Path
from datetime import datetime

import cv2
import httpx
import pandas as pd
import streamlit as st
import folium
from streamlit_folium import st_folium

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from detection.detector import AccidentDetector

API_BASE = "http://localhost:8000"

# ── Page Configuration ────────────────────────────────────────────────────────
st.set_page_config(
    page_title="ADERS Dashboard",
    page_icon="🚨",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.title("🚨 ADERS — AI Accident Detection & Emergency Response")
st.caption("College Demo & Operations Console")

# ── Sidebar Controls ──────────────────────────────────────────────────────────
with st.sidebar:
    st.header("⚙️ System Settings")

    st.subheader("📍 Demo Location (My College / City)")
    loc_preset = st.selectbox(
        "Location Preset",
        ["Custom Coordinates", "College Campus Main Gate", "Highway NH-44", "Downtown Intersection"],
    )

    preset_coords = {
        "Custom Coordinates": (28.6139, 77.2090),
        "College Campus Main Gate": (12.9716, 77.5946),
        "Highway NH-44": (28.4595, 77.0266),
        "Downtown Intersection": (19.0760, 72.8777),
    }

    default_lat, default_lon = preset_coords.get(loc_preset, (28.6139, 77.2090))
    cam_name = st.text_input("Camera Label", value=f"CAM_{loc_preset.replace(' ', '_')[:12]}")
    sim_lat = st.number_input("Latitude", value=default_lat, format="%.6f")
    sim_lon = st.number_input("Longitude", value=default_lon, format="%.6f")

    st.divider()

    st.subheader("🎯 Model Sensitivity")
    conf_thresh = st.slider("Confidence Threshold", 0.15, 0.90, 0.35, 0.05)
    confirm_frames = st.slider("Consecutive Confirm Frames", 2, 20, 5, 1)

    st.divider()
    st.caption(f"FastAPI Backend: `{API_BASE}`")


# ── Backend Helpers ───────────────────────────────────────────────────────────
def fetch_incidents() -> list[dict]:
    try:
        resp = httpx.get(f"{API_BASE}/incidents/", timeout=3.0, follow_redirects=True)
        if resp.status_code == 200:
            return resp.json()
    except Exception:
        pass
    return []


def ack_incident(incident_id: int, responder: str):
    try:
        resp = httpx.post(
            f"{API_BASE}/incidents/{incident_id}/ack",
            json={"responder": responder, "message": "Acknowledged from Dashboard"},
            timeout=3.0,
        )
        return resp.status_code == 200
    except Exception:
        return False


def severity_badge(sev: str) -> str:
    return "🔴 MAJOR" if sev == "major" else "🟡 MINOR"


def alert_status_badge(row: dict) -> str:
    if row.get("acknowledged"):
        return "✅ ACKNOWLEDGED"
    if row.get("alert_sent"):
        return "📤 ALERT DISPATCHED"
    return "⏳ PENDING"


# ── Fetch Data ────────────────────────────────────────────────────────────────
incidents = fetch_incidents()

# ── Summary Metrics Banner ────────────────────────────────────────────────────
total = len(incidents)
major = sum(1 for i in incidents if i.get("severity") == "major")
minor = total - major
unacked = sum(1 for i in incidents if not i.get("acknowledged"))

m1, m2, m3, m4 = st.columns(4)
m1.metric("Total Incidents", total)
m2.metric("🔴 Major Accidents", major)
m3.metric("🟡 Minor Incidents", minor)
m4.metric("⏳ Action Required", unacked)

st.divider()

# ── Main Tabs: Video Testing vs Incident Logs & Map ───────────────────────────
tab_demo, tab_logs, tab_map = st.tabs([
    "🎥 Manual Video Test & Live Stream",
    "📋 Incident Log & Acknowledgements",
    "🗺️ Interactive GPS Map",
])

# ═══════════════════════════════════════════════════════════════════════════════
# TAB 1: MANUAL VIDEO TEST & LIVE DETECTION
# ═══════════════════════════════════════════════════════════════════════════════
with tab_demo:
    col_input, col_display = st.columns([1, 2])

    with col_input:
        st.subheader("Select Video Source")
        source_type = st.radio(
            "Source Type:",
            ["📁 Upload Video from PC", "📹 Webcam (Camera 0)", "🌐 Test Sample Video"],
        )

        video_path = None

        if source_type == "📁 Upload Video from PC":
            uploaded_file = st.file_uploader(
                "Choose an accident / traffic video (.mp4, .avi, .mov)",
                type=["mp4", "avi", "mov", "mkv"],
            )
            if uploaded_file:
                # Save to temporary file for OpenCV to read
                tfile = tempfile.NamedTemporaryFile(delete=False, suffix=".mp4")
                tfile.write(uploaded_file.read())
                video_path = tfile.name
                st.success(f"Loaded: `{uploaded_file.name}`")

        elif source_type == "📹 Webcam (Camera 0)":
            video_path = 0
            st.info("Uses your PC's built-in webcam.")

        else:
            # Look for sample videos in data or media folders
            sample_candidates = list((ROOT / "media").glob("*.mp4")) + list((ROOT / "data").glob("*.mp4"))
            if sample_candidates:
                selected_sample = st.selectbox("Choose sample video:", [str(p) for p in sample_candidates])
                video_path = selected_sample
            else:
                st.info("No sample .mp4 found in project. Upload a video file above!")

        st.markdown("---")
        start_btn = st.button("▶️ Start Accident Detection", type="primary", use_container_width=True)
        stop_btn = st.button("⏹️ Stop Stream", use_container_width=True)

    with col_display:
        st.subheader("Live Detection Monitor")
        video_placeholder = st.empty()
        status_box = st.empty()

        if stop_btn:
            st.session_state["stop_detection"] = True

        if start_btn:
            if video_path is None:
                st.warning("Please upload a video file or choose a webcam source first!")
            else:
                st.session_state["stop_detection"] = False
                try:
                    detector = AccidentDetector(
                        conf_threshold=conf_thresh,
                        confirmation_frames=confirm_frames,
                    )
                except Exception as e:
                    st.error(f"Error loading model: {e}")
                    detector = None

                if detector:
                    cap = cv2.VideoCapture(video_path)
                    if not cap.isOpened():
                        st.error("Could not open video source.")
                    else:
                        status_box.info("Streaming and running YOLOv8 accident detection...")
                        frame_count = 0

                        while cap.isOpened() and not st.session_state.get("stop_detection", False):
                            ret, frame = cap.read()
                            if not ret:
                                break

                            frame_count += 1
                            # Process frame
                            annotated, incident_data = detector.process_frame(
                                frame=frame,
                                camera_id=cam_name,
                                location_lat=sim_lat,
                                location_lon=sim_lon,
                            )

                            # Display in Streamlit
                            rgb_frame = cv2.cvtColor(annotated, cv2.COLOR_BGR2RGB)
                            video_placeholder.image(rgb_frame, channels="RGB", use_container_width=True)

                            if incident_data:
                                st.toast(
                                    f"🚨 {incident_data['severity'].upper()} ACCIDENT DETECTED! Emergency alert sent.",
                                    icon="🚨",
                                )

                            # Brief yield for UI responsiveness
                            time.sleep(0.01)

                        cap.release()
                        status_box.success("Video playback completed / stopped.")

# ═══════════════════════════════════════════════════════════════════════════════
# TAB 2: INCIDENT LOG & ACKNOWLEDGEMENT
# ═══════════════════════════════════════════════════════════════════════════════
with tab_logs:
    st.subheader("📋 Recorded Incidents")

    if not incidents:
        st.info("No incidents in database yet. Run the video test or trigger one from Swagger UI!")
    else:
        rows = []
        for inc in incidents:
            lat = inc.get("location_lat")
            lon = inc.get("location_lon")
            coords_str = f"{lat:.5f}, {lon:.5f}" if lat and lon else "—"
            maps_link = f"https://www.google.com/maps?q={lat},{lon}" if lat and lon else None

            rows.append({
                "ID":          inc["id"],
                "Timestamp":   inc.get("created_at", "")[:19].replace("T", " "),
                "Camera":      inc.get("camera_id"),
                "Severity":    severity_badge(inc.get("severity", "")),
                "Confidence":  f"{inc.get('confidence', 0)*100:.1f}%",
                "GPS Coordinates": coords_str,
                "Status":      alert_status_badge(inc),
                "Snapshot":    f"[View Image]({API_BASE}/{inc.get('snapshot_path')})" if inc.get("snapshot_path") else "—",
                "_id":         inc["id"],
                "_acked":      inc.get("acknowledged", False),
            })

        df = pd.DataFrame(rows)
        st.dataframe(df.drop(columns=["_id", "_acked"]), use_container_width=True, hide_index=True)

        st.markdown("---")
        st.subheader("✅ Dispatch Responder Acknowledgement")
        unacked_rows = [r for r in rows if not r["_acked"]]

        if unacked_rows:
            col_a1, col_a2, col_a3 = st.columns([2, 2, 1])
            with col_a1:
                options = {f"Incident #{r['_id']} ({r['Camera']})": r["_id"] for r in unacked_rows}
                chosen_label = st.selectbox("Pending Incident", list(options.keys()))
            with col_a2:
                responder_name = st.text_input("Responder Name / Unit", value="College Campus Patrol Unit 1")
            with col_a3:
                st.write("")
                st.write("")
                if st.button("Confirm Ack", type="primary"):
                    cid = options[chosen_label]
                    if ack_incident(cid, responder_name):
                        st.success(f"Incident #{cid} confirmed!")
                        time.sleep(1)
                        st.rerun()
                    else:
                        st.error("Failed to connect to backend.")
        else:
            st.success("All recorded incidents have been acknowledged.")

# ═══════════════════════════════════════════════════════════════════════════════
# TAB 3: INTERACTIVE GPS MAP
# ═══════════════════════════════════════════════════════════════════════════════
with tab_map:
    st.subheader("🗺️ Emergency Incident Map")

    has_coords = [i for i in incidents if i.get("location_lat") and i.get("location_lon")]

    if not has_coords:
        st.info("No GPS coordinates recorded yet. Test an incident in Tab 1 with your chosen coordinates!")
    else:
        avg_lat = sum(i["location_lat"] for i in has_coords) / len(has_coords)
        avg_lon = sum(i["location_lon"] for i in has_coords) / len(has_coords)

        m = folium.Map(location=[avg_lat, avg_lon], zoom_start=14)

        for inc in has_coords:
            lat, lon = inc["location_lat"], inc["location_lon"]
            sev = inc.get("severity", "minor")
            color = "red" if sev == "major" else "orange"
            icon_name = "exclamation-sign" if sev == "major" else "info-sign"

            popup_html = f"""
            <div style="font-family: Arial; min-width: 200px;">
                <h4 style="margin:0 0 5px 0; color: {'#d9534f' if sev=='major' else '#f0ad4e'};">
                    {sev.upper()} ACCIDENT
                </h4>
                <b>Incident ID:</b> #{inc['id']}<br>
                <b>Camera:</b> {inc.get('camera_id')}<br>
                <b>Time:</b> {inc.get('created_at','')[:19]}<br>
                <b>Confidence:</b> {inc.get('confidence',0)*100:.1f}%<br>
                <b>GPS:</b> {lat:.5f}, {lon:.5f}<br>
                <hr style="margin: 6px 0;">
                <a href="https://www.google.com/maps?q={lat},{lon}" target="_blank" style="color: #0275d8; text-decoration: underline; font-weight: bold;">
                    📍 Open in Google Maps
                </a>
            </div>
            """
            popup = folium.Popup(popup_html, max_width=260)

            folium.Marker(
                location=[lat, lon],
                popup=popup,
                tooltip=f"Incident #{inc['id']} ({sev.upper()})",
                icon=folium.Icon(color=color, icon=icon_name, prefix="glyphicon"),
            ).add_to(m)

        st_folium(m, use_container_width=True, height=500)
