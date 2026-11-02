"""
scripts/download_dataset.py
────────────────────────────
Downloads accident dataset from Roboflow and stages it for splitting.
"""

import os
import sys
from pathlib import Path
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
sys.path.append(str(ROOT / "scripts"))

load_dotenv(ROOT / ".env")

API_KEY = os.getenv("ROBOFLOW_API_KEY", "tz1cg7nLfL9HB4sx18iY").strip()

try:
    from roboflow import Roboflow
except ImportError:
    raise ImportError("Run: pip install roboflow")

# ── Roboflow Coordinates from your snippet ────────────────────────────────────
WORKSPACE  = "accident-detection-ffdrf"
PROJECT    = "accident-detection-8dvh5"
VERSION    = 2
FORMAT     = "yolov8"

print(f"Connecting to Roboflow workspace '{WORKSPACE}', project '{PROJECT}' (v{VERSION})...")
rf = Roboflow(api_key=API_KEY)
project = rf.workspace(WORKSPACE).project(PROJECT)
version = project.version(VERSION)

download_dir = ROOT / "data" / "raw_roboflow"
dataset = version.download(FORMAT, location=str(download_dir))

print(f"\n✅ Roboflow dataset downloaded to: {dataset.location}")
print("Flattening into data/raw/ ...")

# Auto-flatten into data/raw/images and data/raw/labels
from flatten_roboflow import flatten
flatten(Path(dataset.location))
