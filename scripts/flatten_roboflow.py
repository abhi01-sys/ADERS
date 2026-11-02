"""
scripts/flatten_roboflow.py
────────────────────────────
Roboflow downloads data already split into train/valid/test.
We IGNORE that split (to avoid their leakage or imbalance choices)
and flatten everything into data/raw/images/ + data/raw/labels/
so our own split_dataset.py can re-split cleanly.

Usage:
    python scripts/flatten_roboflow.py --src "C:/path/to/extracted/roboflow/folder"

The source folder should contain subfolders like:
    train/images/, train/labels/
    valid/images/, valid/labels/
    test/images/,  test/labels/    (if present)
"""

import argparse
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RAW_IMG_DIR = ROOT / "data" / "raw" / "images"
RAW_LBL_DIR = ROOT / "data" / "raw" / "labels"

def flatten(src: Path):
    RAW_IMG_DIR.mkdir(parents=True, exist_ok=True)
    RAW_LBL_DIR.mkdir(parents=True, exist_ok=True)

    total = 0
    for split in ["train", "valid", "val", "test"]:
        img_dir = src / split / "images"
        lbl_dir = src / split / "labels"
        if not img_dir.exists():
            continue
        image_exts = {".jpg", ".jpeg", ".png", ".bmp"}
        for img in img_dir.iterdir():
            if img.suffix.lower() not in image_exts:
                continue
            lbl = lbl_dir / (img.stem + ".txt")
            if not lbl.exists():
                continue
            # Avoid name collision across splits
            dest_img = RAW_IMG_DIR / img.name
            dest_lbl = RAW_LBL_DIR / lbl.name
            if dest_img.exists():
                dest_img = RAW_IMG_DIR / f"{split}_{img.name}"
                dest_lbl = RAW_LBL_DIR / f"{split}_{lbl.name}"
            shutil.copy2(img, dest_img)
            shutil.copy2(lbl, dest_lbl)
            total += 1

    print(f"✅ Flattened {total} image+label pairs into data/raw/")
    print("   Now run: python scripts/split_dataset.py")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--src", required=True,
                        help="Path to extracted Roboflow dataset folder")
    args = parser.parse_args()
    src = Path(args.src)
    if not src.exists():
        raise FileNotFoundError(f"Source not found: {src}")
    flatten(src)

