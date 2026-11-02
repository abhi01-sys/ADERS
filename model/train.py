"""
model/train.py
──────────────
Fine-tunes YOLOv8 on the accident dataset.

Workflow:
1. Loads pre-trained YOLOv8 (yolov8n.pt or yolov8s.pt).
2. Uses dataset specified in data/dataset.yaml.
3. Automatically uses GPU (CUDA) if available, otherwise CPU.
4. Saves checkpoints to model/runs/train/weights/best.pt.
"""

import sys
from pathlib import Path
import torch
import yaml
from ultralytics import YOLO

# ── Paths ─────────────────────────────────────────────────────────────────────
ROOT = Path(__file__).resolve().parent.parent
DATASET_YAML = ROOT / "data" / "dataset.yaml"
RUNS_DIR = ROOT / "model" / "runs"

def check_environment():
    """Verify hardware & environment before starting training."""
    print("=" * 60)
    print("ADERS — YOLOv8 Training Setup")
    print("=" * 60)
    print(f"PyTorch Version : {torch.__version__}")
    
    if torch.cuda.is_available():
        gpu_name = torch.cuda.get_device_name(0)
        gpu_mem = torch.cuda.get_device_properties(0).total_memory / 1e9
        print(f"Device          : GPU ({gpu_name}, {gpu_mem:.1f} GB VRAM)")
        device = 0
        batch_size = 16  # standard batch size for GPU
    else:
        print("Device          : CPU (No CUDA detected)")
        print("  [Tip] CPU training will be slower. Setting batch=8, epochs=15.")
        device = "cpu"
        batch_size = 8

    if not DATASET_YAML.exists():
        sys.exit(f"[ERROR] Dataset configuration not found: {DATASET_YAML}")

    # Ensure dataset.yaml points to absolute path on this machine
    with open(DATASET_YAML, "r") as f:
        data_cfg = yaml.safe_load(f)
    abs_processed = str((ROOT / "data" / "processed").resolve()).replace("\\", "/")
    if data_cfg.get("path") != abs_processed:
        data_cfg["path"] = abs_processed
        with open(DATASET_YAML, "w") as f:
            yaml.safe_dump(data_cfg, f, sort_keys=False)
        print(f"Updated dataset.yaml path -> {abs_processed}")

    return device, batch_size

def train():
    device, batch_size = check_environment()

    # 1. Load pre-trained model (nano is fastest for initial experiments)
    model_name = "yolov8n.pt"
    print(f"\nLoading base model: {model_name}...")
    model = YOLO(model_name)

    # 2. Configure training parameters
    epochs = 30 if device == 0 else 10  # adjust based on hardware availability
    imgsz = 640

    print(f"\nStarting fine-tuning:")
    print(f"  • Data Config : {DATASET_YAML}")
    print(f"  • Epochs      : {epochs}")
    print(f"  • Image Size  : {imgsz}x{imgsz}")
    print(f"  • Batch Size  : {batch_size}")
    print(f"  • Output Dir  : {RUNS_DIR}\n")

    # 3. Launch training
    # Note: absolute path to dataset.yaml avoids any working-dir ambiguity
    results = model.train(
        data=str(DATASET_YAML),
        epochs=epochs,
        imgsz=imgsz,
        batch=batch_size,
        device=device,
        project=str(RUNS_DIR),
        name="accident_model",
        save=True,
        patience=8,          # Early stopping if no val improvement for 8 epochs
        workers=2,           # Keep worker count moderate on Windows
        verbose=True,
        plots=True           # Generates PR curves, confusion matrix, loss charts
    )

    best_weights = RUNS_DIR / "accident_model" / "weights" / "best.pt"
    print("\n" + "=" * 60)
    print(f"✅ Training completed!")
    print(f"Best model weights saved at: {best_weights}")
    print("=" * 60)
    print("\nNext step: Run test-set evaluation (model/evaluate.py)")

if __name__ == "__main__":
    train()

