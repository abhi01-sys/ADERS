# ADERS — AI-Powered Accident Detection & Emergency Response System

ADERS is an end-to-end intelligent traffic surveillance and emergency dispatch system designed to detect road vehicle collisions in real time from video feeds, calibrate against false alarms, and automatically alert emergency responders via SMS and automated voice calls.

---

## 🚀 Key Features

- **Real-Time Collision Detection**: Powered by a fine-tuned YOLOv8n model trained to detect vehicular collisions.
- **False-Alert Calibration**: Temporal multi-frame confirmation prevents pre-impact false alerts.
- **Single Emergency Voice Call per Accident**: Guaranteed automated phone call to the primary responder without redundant repeated calling.
- **Glassmorphic Mission Control Dashboard**:
  - Live CCTV surveillance feed with HUD corner brackets.
  - Interactive Geospatial Leaflet Map with radar pins (Dark Tactical, OpenStreetMap, Satellite).
  - Live incident timeline and telemetry metrics.
  - One-click incident acknowledgement and Google Maps navigation dispatch.
- **Robust Architecture**:
  - SQLite database in WAL (Write-Ahead Logging) mode for high-concurrency safety.
  - Fast, modern REST & streaming endpoints via FastAPI.

---

## 🛠️ Tech Stack

- **Computer Vision & AI**: YOLOv8 (Ultralytics), OpenCV, PyTorch
- **Backend API**: FastAPI, Uvicorn, SQLAlchemy, SQLite WAL
- **Alert Dispatch**: Twilio REST API (SMS & Voice Calls)
- **Frontend Dashboard**: React 18, Vite, Tailwind CSS, Lucide Icons, Leaflet / React-Leaflet

---

## 📦 Project Structure

```text
ADERS/
├── alerts/               # Twilio client, emergency contact manager & escalation thread
├── api/                  # FastAPI app, routes (incidents, video streaming), schemas
├── config.yaml           # Centralized configuration (thresholds, contacts, cameras)
├── dashboard_react/      # Modern Mission Control React + Vite frontend
├── data/                 # Dataset configurations (dataset.yaml)
├── database/             # SQLAlchemy models, CRUD operations, SQLite engine
├── detection/            # OpenCV video pipeline & YOLO collision detector
├── model/                # YOLOv8 fine-tuned weights & evaluation scripts
├── sample_video's/       # Sample CCTV traffic test videos
├── scripts/              # Performance benchmarks & diagnostics
└── tests/                # System test suite
```

---

## ⚙️ Setup & Installation

### 1. Prerequisites
- Python 3.10+
- Node.js 18+ and npm
- (Optional) Twilio account credentials for live SMS/voice alerts

### 2. Backend Setup
```bash
# Clone the repository
git clone https://github.com/<YOUR_USERNAME>/<YOUR_REPO_NAME>.git
cd ADERS

# Install Python dependencies
pip install -r requirements.txt

# Configure environment variables
cp .env.example .env
# Open .env and add your Twilio credentials if desired (alerts work in mock console mode without them)

# Start FastAPI Backend Server
python -m uvicorn api.main:app --reload --port 8000
```
Backend API docs available at: `http://localhost:8000/docs`

### 3. Frontend Setup
In a second terminal:
```bash
cd dashboard_react
npm install
npm run dev
```
Open your browser at `http://localhost:5173`.

---

## 🧪 Testing

Run the automated test suite:
```bash
python tests/test_system.py
```

Run latency and FPS benchmarks:
```bash
python scripts/benchmark.py
```

---

## 🛡️ Security Note
The `.env` file contains sensitive credentials and is strictly excluded via `.gitignore`. Never commit API keys or private tokens.

