"""
scripts/split_dataset.py
────────────────────────
Splits raw YOLO-format data into train / val / test sets.

Expected raw layout:
    data/raw/
        images/   ← .jpg / .png files
        labels/   ← .txt files with same stem as image

Output:
    data/processed/
        train/images,  train/labels
        val/images,    val/labels
        test/images,   test/labels

IMPORTANT RULES
  • Run this script ONCE. Fix random_seed in config.yaml; never change it.
  • The test set is LOCKED after this split — do not use it during training.
  • Only images that have a matching label file are included.
"""

import shutil
import sys
from pathlib import Path

import yaml
from sklearn.model_selection import train_test_split

# ── Load config ──────────────────────────────────────────────────────────────
ROOT = Path(__file__).resolve().parent.parent
cfg_path = ROOT / "config.yaml"
with open(cfg_path) as f:
    cfg = yaml.safe_load(f)

ds_cfg = cfg["dataset"]
RAW_DIR = ROOT / ds_cfg["raw_dir"]
OUT_DIR = ROOT / ds_cfg["processed_dir"]
TRAIN_R = ds_cfg["train_ratio"]   # e.g. 0.70
VAL_R   = ds_cfg["val_ratio"]     # e.g. 0.15
TEST_R  = ds_cfg["test_ratio"]    # e.g. 0.15
SEED    = ds_cfg["random_seed"]   # e.g. 42

assert abs(TRAIN_R + VAL_R + TEST_R - 1.0) < 1e-6, "Ratios must sum to 1.0"

# ── Gather paired samples ─────────────────────────────────────────────────────
img_dir = RAW_DIR / "images"
lbl_dir = RAW_DIR / "labels"

if not img_dir.exists():
    sys.exit(f"[ERROR] Raw images dir not found: {img_dir}\n"
             "Download your dataset into data/raw/images/ first.")

image_exts = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}
images = sorted([p for p in img_dir.iterdir() if p.suffix.lower() in image_exts])

paired = []
skipped = 0
for img in images:
    lbl = lbl_dir / (img.stem + ".txt")
    if lbl.exists():
        paired.append((img, lbl))
    else:
        skipped += 1

print(f"Found {len(paired)} paired samples  |  Skipped {skipped} images (no label)")
if len(paired) == 0:
    sys.exit("[ERROR] No paired image+label files found. Check your data/raw/ layout.")

# ── Two-stage split ───────────────────────────────────────────────────────────
# Stage 1: split off test set
trainval, test = train_test_split(
    paired,
    test_size=TEST_R,
    random_state=SEED,
    shuffle=True,
)

# Stage 2: split remaining into train and val
# val_size relative to trainval portion
relative_val = VAL_R / (TRAIN_R + VAL_R)
train, val = train_test_split(
    trainval,
    test_size=relative_val,
    random_state=SEED,
    shuffle=True,
)

splits = {"train": train, "val": val, "test": test}
print(f"\nSplit sizes  →  train: {len(train)}  |  val: {len(val)}  |  test: {len(test)}")

# ── Copy files ────────────────────────────────────────────────────────────────
def copy_split(pairs, split_name: str):
    img_out = OUT_DIR / split_name / "images"
    lbl_out = OUT_DIR / split_name / "labels"
    img_out.mkdir(parents=True, exist_ok=True)
    lbl_out.mkdir(parents=True, exist_ok=True)

    for img_src, lbl_src in pairs:
        shutil.copy2(img_src, img_out / img_src.name)
        shutil.copy2(lbl_src, lbl_out / lbl_src.name)

    print(f"  [{split_name:>5}]  Copied {len(pairs)} pairs → {OUT_DIR / split_name}")

for name, pairs in splits.items():
    copy_split(pairs, name)

print("\n✅ Dataset split complete. Test set is now LOCKED.")
print("   Next: run  python model/train.py  to start fine-tuning.")

