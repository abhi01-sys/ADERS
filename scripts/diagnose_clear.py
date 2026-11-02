"""
scripts/diagnose_clear.py
──────────────────────────
One-shot diagnostic: scan Town03_clear at very low confidence
to see what the model ACTUALLY detects (and at what conf scores).
No alerts, no side effects.
"""

import sys
import time
import cv2
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from ultralytics import YOLO

WEIGHTS = ROOT / "model" / "runs" / "accident_model" / "weights" / "best.pt"
CLIP    = ROOT / "sample_video's" / "Town03_head-on_clear_30.mp4"

model = YOLO(str(WEIGHTS))
cap   = cv2.VideoCapture(str(CLIP))

print(f"Model classes: {model.names}")
print(f"Scanning {CLIP.name} at conf=0.05 (floor)...\n")

frame_idx = 0
high_scores = []

while cap.isOpened():
    ret, frame = cap.read()
    if not ret:
        break
    frame_idx += 1
    if frame_idx % 2 != 0:
        continue

    results = model.predict(source=frame, conf=0.05, imgsz=416, verbose=False)
    r = results[0]
    if r.boxes is not None and len(r.boxes) > 0:
        for box in r.boxes:
            conf  = float(box.conf[0])
            cls   = int(box.cls[0])
            name  = model.names.get(cls, str(cls))
            high_scores.append((frame_idx, conf, name))

cap.release()

if not high_scores:
    print("RESULT: Model detected NOTHING even at conf=0.05 on this clip.")
    print("=> This clip likely falls outside the training distribution.")
else:
    high_scores.sort(key=lambda x: -x[1])
    print(f"{'Frame':>6}  {'Conf':>6}  Class")
    print("-" * 30)
    for frame, conf, cls in high_scores[:30]:
        marker = " <-- above 0.30" if conf >= 0.30 else ""
        print(f"{frame:>6}  {conf:>6.3f}  {cls}{marker}")
    max_conf = high_scores[0][1]
    print(f"\nMax confidence found: {max_conf:.3f}")
    if max_conf < 0.30:
        print(f"=> No frame exceeds conf=0.30 threshold. Model not confident on this clip.")
        print(f"=> Try lowering threshold to ~{max_conf - 0.05:.2f} to detect it.")

