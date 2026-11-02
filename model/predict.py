"""
model/predict.py
────────────────
Runs test inference on an image or video file using best.pt.

Usage:
    python model/predict.py                                # picks a sample test image
    python model/predict.py --source "path/to/image.jpg"   # custom image or video
"""

import argparse
import random
from pathlib import Path
from ultralytics import YOLO

ROOT = Path(__file__).resolve().parent.parent
WEIGHTS_PATH = ROOT / "model" / "runs" / "accident_model" / "weights" / "best.pt"
TEST_IMG_DIR = ROOT / "data" / "processed" / "test" / "images"

def predict(source_path=None, conf=0.35):
    if not WEIGHTS_PATH.exists():
        print(f"[ERROR] Model weights not found at: {WEIGHTS_PATH}")
        return

    # If no source provided, pick a random image from held-out test split
    if source_path is None or not Path(source_path).exists():
        test_images = list(TEST_IMG_DIR.glob("*.jpg")) + list(TEST_IMG_DIR.glob("*.png"))
        if not test_images:
            print("[ERROR] No images found in test split.")
            return
        source_path = random.choice(test_images)
        print(f"Sample test image selected: {source_path.name}")
    else:
        source_path = Path(source_path)

    print(f"\nLoading weights: {WEIGHTS_PATH}")
    model = YOLO(str(WEIGHTS_PATH))

    print(f"Running inference on: {source_path} (confidence threshold = {conf})...")
    results = model.predict(
        source=str(source_path),
        conf=conf,
        save=True,
        project=str(ROOT / "model" / "runs"),
        name="predictions"
    )

    for r in results:
        boxes = r.boxes
        print(f"\nFound {len(boxes)} detection(s):")
        for box in boxes:
            cls_id = int(box.cls[0].item())
            class_name = model.names.get(cls_id, f"Class {cls_id}")
            confidence = float(box.conf[0].item())
            xyxy = box.xyxy[0].tolist()
            print(f"  • {class_name.upper()} with confidence {confidence:.2f} at bbox [{xyxy[0]:.0f}, {xyxy[1]:.0f}, {xyxy[2]:.0f}, {xyxy[3]:.0f}]")

    print(f"\nAnnotated result saved to: model/runs/predictions/")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=str, default=None, help="Path to image or video")
    parser.add_argument("--conf", type=float, default=0.35, help="Confidence threshold")
    args = parser.parse_args()
    predict(args.source, args.conf)

