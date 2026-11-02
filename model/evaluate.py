"""
model/evaluate.py
─────────────────
Evaluates the fine-tuned model strictly on the held-out TEST set.

Calculates:
  • Precision, Recall, F1-Score
  • mAP@0.5
  • mAP@0.5:0.95
  • Class-wise breakdown (moderate vs severe)
  • Overfitting / Data Leakage sanity check (> 0.99 warning)
"""

import sys
from pathlib import Path
from ultralytics import YOLO

ROOT = Path(__file__).resolve().parent.parent
DATASET_YAML = ROOT / "data" / "dataset.yaml"
WEIGHTS_PATH = ROOT / "model" / "runs" / "accident_model" / "weights" / "best.pt"

def evaluate():
    if not WEIGHTS_PATH.exists():
        sys.exit(
            f"[ERROR] Weights not found at: {WEIGHTS_PATH}\n"
            "Train the model first using: python model/train.py"
        )

    print("=" * 65)
    print("ADERS — Test Set Model Evaluation")
    print(f"Loading weights: {WEIGHTS_PATH}")
    print(f"Evaluating strictly on: {DATASET_YAML} (split='test')")
    print("=" * 65)

    model = YOLO(str(WEIGHTS_PATH))

    # Evaluate on the HELD-OUT test split
    metrics = model.val(
        data=str(DATASET_YAML),
        split="test",
        project=str(ROOT / "model" / "runs"),
        name="test_evaluation",
        save_json=True,
        plots=True
    )

    # Extract metrics
    # box.mp: mean precision, box.mr: mean recall, box.map50: mAP@0.5, box.map: mAP@0.5:0.95
    p = metrics.box.mp
    r = metrics.box.mr
    map50 = metrics.box.map50
    map50_95 = metrics.box.map

    f1 = 2 * (p * r) / (p + r + 1e-16)

    print("\n" + "=" * 65)
    print("🎯 OFFICIAL TEST SET RESULTS (2,421 Unseen Test Images)")
    print("=" * 65)
    print(f"  • Precision     : {p:.4f}  ({p*100:.2f}%)")
    print(f"  • Recall        : {r:.4f}  ({r*100:.2f}%)")
    print(f"  • F1-Score      : {f1:.4f}  ({f1*100:.2f}%)")
    print(f"  • mAP@0.5       : {map50:.4f}  ({map50*100:.2f}%)  [Target: ≥ 0.9000]")
    print(f"  • mAP@0.5:0.95  : {map50_95:.4f}  ({map50_95*100:.2f}%)")
    print("-" * 65)

    # Class-wise metrics
    class_names = metrics.names
    for i, name in class_names.items():
        try:
            if hasattr(metrics.box, 'ap50') and len(metrics.box.ap50) > i:
                print(f"  Class [{name}]: mAP@0.5 = {metrics.box.ap50[i]:.4f}")
        except Exception:
            pass

    print("=" * 65)

    # Diagnostic checks
    if map50 > 0.99:
        print("\n⚠️ WARNING: mAP@0.5 is suspiciously high (>0.99)!")
        print("Possible causes: Duplicate/near-identical frames between train & test,")
        print("or synthetic benchmark data. Inspect sample predictions in runs/test_evaluation/.")
    elif map50 >= 0.90:
        print("\n✅ Target Met: mAP@0.5 is ≥ 0.90! Ready for inference & tracking pipeline.")
    else:
        gap = 0.90 - map50
        print(f"\n⚠️ Target not met: mAP@0.5 is {map50:.4f} ({gap:.4f} below 0.90 target).")
        print("Suggestions:")
        print("  1. Train for more epochs (e.g. 50 instead of 30).")
        print("  2. Upgrade base model from yolov8n.pt to yolov8s.pt.")
        print("  3. Check data augmentation settings in training.")

    print(f"\nConfusion matrix and PR curve saved at: model/runs/test_evaluation/")

if __name__ == "__main__":
    evaluate()

