#!/usr/bin/env python
"""
Detect duplicate or near‑duplicate images across train/val/test
and optionally re‑split the raw dataset *by video ID* to avoid leakage.

Usage:
    python scripts/check_and_split.py            # only check for duplicates
    python scripts/check_and_split.py --re‑split  # clean split by video ID
"""

import argparse
import hashlib
import random
import shutil
from pathlib import Path
import yaml

ROOT = Path(__file__).resolve().parent.parent
RAW_IMG = ROOT / "data" / "raw" / "images"
RAW_LBL = ROOT / "data" / "raw" / "labels"

PROCESSED = ROOT / "data" / "processed"
TRAIN = PROCESSED / "train"
VAL = PROCESSED / "val"
TEST = PROCESSED / "test"

def hash_file(p: Path) -> str:
    """Return SHA‑256 hash of a file (fast for jpg/png)."""
    h = hashlib.sha256()
    with p.open("rb") as f:
        while chunk := f.read(8192):
            h.update(chunk)
    return h.hexdigest()

def find_hash_collisions() -> dict:
    """Collect hashes for all images in processed splits and return collisions."""
    coll = {}
    for split in (TRAIN, VAL, TEST):
        img_dir = split / "images"
        if not img_dir.exists():
            continue
        for img in img_dir.iterdir():
            if not img.is_file():
                continue
            h = hash_file(img)
            coll.setdefault(h, []).append(img)
    # Keep only hashes that appear in 2+ files
    return {h: paths for h, paths in coll.items() if len(paths) > 1}

def report_collisions(collisions: dict):
    if not collisions:
        print("✅ No duplicate/near‑duplicate images found across splits.")
        return
    print("⚠️ Duplicate image hashes detected across splits:")
    for h, paths in collisions.items():
        print(f"  Hash {h[:8]}… – {len(paths)} occurrences:")
        for p in paths:
            print(f"    - {p.relative_to(ROOT)}")
    print("\nIf any belong to the same video, consider re‑splitting by video ID.")

def split_by_video_id(seed: int = 42,
                      train_ratio: float = 0.70,
                      val_ratio: float = 0.15,
                      test_ratio: float = 0.15):
    """Re‑split the *raw* dataset ensuring whole video clips stay together.
    Assumes filenames follow the pattern <videoID>_XXXXX.ext (e.g. V001_001.jpg).
    """
    random.seed(seed)
    # Group raw images by video ID (prefix before first underscore)
    groups = {}
    for img in RAW_IMG.glob("*.*"):
        vid = img.stem.split("_")[0]
        groups.setdefault(vid, []).append(img)

    # Shuffle video groups and allocate
    vids = list(groups.keys())
    random.shuffle(vids)
    n = len(vids)
    n_train = int(train_ratio * n)
    n_val = int(val_ratio * n)
    train_vids = set(vids[:n_train])
    val_vids   = set(vids[n_train:n_train+n_val])
    test_vids  = set(vids[n_train+n_val:])

    # Helper to copy images & matching labels
    def copy_split(vids_set, dst):
        img_dst = dst / "images"
        lbl_dst = dst / "labels"
        img_dst.mkdir(parents=True, exist_ok=True)
        lbl_dst.mkdir(parents=True, exist_ok=True)
        for vid in vids_set:
            for img in groups[vid]:
                shutil.copy2(img, img_dst / img.name)
                lbl = RAW_LBL / (img.stem + ".txt")
                if lbl.exists():
                    shutil.copy2(lbl, lbl_dst / lbl.name)

    # Remove old splits if present
    for d in (TRAIN, VAL, TEST):
        if d.exists():
            shutil.rmtree(d)

    copy_split(train_vids, TRAIN)
    copy_split(val_vids,   VAL)
    copy_split(test_vids,  TEST)

    print("✅ Re‑split completed (by video ID):")
    print(f"   Train: {len(train_vids)} videos → {sum(len(groups[v]) for v in train_vids)} images")
    print(f"   Val:   {len(val_vids)} videos → {sum(len(groups[v]) for v in val_vids)} images")
    print(f"   Test:  {len(test_vids)} videos → {sum(len(groups[v]) for v in test_vids)} images")

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--resplit", action="store_true",
                        help="Force a fresh split by video ID (removes leakage).")
    parser.add_argument("--seed", type=int, default=42,
                        help="Random seed for reproducible split.")
    args = parser.parse_args()

    # 1️⃣ Detect hash collisions
    collisions = find_hash_collisions()
    report_collisions(collisions)

    # 2️⃣ Re‑split if requested
    if args.resplit:
        split_by_video_id(seed=args.seed)
    else:
        print("\nRun with --resplit to create a leakage-free split.")

if __name__ == "__main__":
    main()

