"""
scripts/benchmark.py
─────────────────────
Phase 2 Baseline Measurement — ADERS
Measures per-frame timing and false-alert count.
Run: python scripts/benchmark.py

NO real Twilio calls are made — alert dispatch is mocked.
"""

import sys
import time
import cv2
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

# ── Mock out Twilio so no real calls are ever made ────────────────────────────
import unittest.mock as mock
import alerts.twilio_client as _twilio_mod
_twilio_mod.AlertSender.send_alerts = lambda self, *a, **kw: []  # noqa: E731
print("[OK] Twilio send_alerts MOCKED - no real calls will be placed.\n")

import yaml
from ultralytics import YOLO
from detection.detector import DEFAULT_WEIGHTS, AccidentDetector

# Read benchmark settings from config.yaml (P1-13 fix: single source of truth)
_cfg = yaml.safe_load((ROOT / "config.yaml").read_text())
CONF_THRESHOLD      = _cfg.get("detection", {}).get("confidence_threshold", 0.35)
CONFIRMATION_FRAMES = _cfg.get("detection", {}).get("frame_confirmation_count", 6)
CLIPS = [
    {
        "path": ROOT / "sample_video's" / "Town03_head-on_clear_30.mp4",
        "label": "Town03_clear (accident expected)",
        "expect_accident": True,
    },
    {
        "path": ROOT / "sample_video's" / "Town03_head-on_wet_49.mp4",
        "label": "Town03_wet (accident expected)",
        "expect_accident": True,
    },
    {
        "path": ROOT / "sample_video's" / "clip_03.mp4",
        "label": "clip_03 (short clip)",
        "expect_accident": True,
    },
]

CONF_THRESHOLD     = 0.30
CONFIRMATION_FRAMES = 4   # current detector default
IMGSZ              = 416  # current stream-video default
SKIP_FRAMES        = 2    # current stream-video default


def benchmark_clip(model, clip_info: dict) -> dict:
    path  = clip_info["path"]
    label = clip_info["label"]

    if not path.exists():
        print(f"  ⚠️  SKIPPED (not found): {path.name}")
        return None

    detector = AccidentDetector(
        model=model,
        conf_threshold=CONF_THRESHOLD,
        confirmation_frames=CONFIRMATION_FRAMES,
        imgsz=IMGSZ,
        auto_dispatch=False,
    )

    cap = cv2.VideoCapture(str(path))
    total_frames   = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    source_fps     = cap.get(cv2.CAP_PROP_FPS) or 25.0

    frame_times    = []   # wall time per processed frame (inference + draw)
    capture_times  = []   # just cap.read()
    inference_times = []  # just model.predict()
    encode_times   = []   # just cv2.imencode
    incidents_fired = 0
    frame_idx      = 0
    processed      = 0

    print(f"\n▶  {label}")
    print(f"   Source: {path.name} | {total_frames} frames @ {source_fps:.1f} fps | testing conf={CONF_THRESHOLD}")

    while cap.isOpened():
        t_cap0 = time.perf_counter()
        ret, frame = cap.read()
        t_cap1 = time.perf_counter()
        if not ret:
            break
        frame_idx += 1
        capture_times.append(t_cap1 - t_cap0)

        # Subsample (mirror stream-video pipeline)
        if frame_idx % SKIP_FRAMES != 0:
            continue

        # Resize > 640 (mirror pipeline)
        h, w = frame.shape[:2]
        if w > 640:
            frame = cv2.resize(frame, (640, int(h * 640.0 / w)))

        # ----- Time inference separately -----
        t_inf0 = time.perf_counter()
        results = model.predict(
            source=frame, conf=CONF_THRESHOLD, imgsz=IMGSZ, verbose=False
        )
        t_inf1 = time.perf_counter()
        inference_times.append(t_inf1 - t_inf0)

        # ----- Full process_frame (includes draw) -----
        t_frame0 = time.perf_counter()
        annotated, inc_info = detector.process_frame(frame)
        t_frame1 = time.perf_counter()
        frame_times.append(t_frame1 - t_frame0)

        # ----- Encode -----
        t_enc0 = time.perf_counter()
        cv2.imencode(".jpg", annotated, [cv2.IMWRITE_JPEG_QUALITY, 72])
        t_enc1 = time.perf_counter()
        encode_times.append(t_enc1 - t_enc0)

        if inc_info:
            incidents_fired += 1
            print(f"   🚨  Incident at frame {frame_idx}: conf={inc_info['confidence']} sev={inc_info['severity']}")

        processed += 1

    cap.release()

    if not frame_times:
        print("   ⚠️  No frames processed.")
        return None

    avg_inf_ms   = 1000 * sum(inference_times) / len(inference_times)
    avg_frame_ms = 1000 * sum(frame_times)     / len(frame_times)
    avg_enc_ms   = 1000 * sum(encode_times)    / len(encode_times)
    avg_cap_ms   = 1000 * sum(capture_times)   / len(capture_times)

    # Effective FPS = 1 / (cap + inf + draw + enc) per processed frame
    per_frame_wall = avg_cap_ms + avg_inf_ms + avg_enc_ms  # draw is inside frame_ms
    eff_fps = 1000.0 / per_frame_wall if per_frame_wall > 0 else 0.0

    print(f"   Frames total={total_frames} | processed={processed} | incidents={incidents_fired}")
    print(f"   ┌─────────────────────────────────────┐")
    print(f"   │  Capture       : {avg_cap_ms:6.1f} ms/frame   │")
    print(f"   │  YOLO Inference: {avg_inf_ms:6.1f} ms/frame   │")
    print(f"   │  Draw+Process  : {avg_frame_ms:6.1f} ms/frame   │")
    print(f"   │  JPEG Encode   : {avg_enc_ms:6.1f} ms/frame   │")
    print(f"   │  ─────────────────────────────────  │")
    print(f"   │  Effective FPS : {eff_fps:6.1f} fps          │")
    print(f"   └─────────────────────────────────────┘")

    return {
        "clip": label,
        "total_frames": total_frames,
        "processed_frames": processed,
        "incidents_fired": incidents_fired,
        "avg_capture_ms": round(avg_cap_ms, 1),
        "avg_inference_ms": round(avg_inf_ms, 1),
        "avg_draw_ms": round(avg_frame_ms, 1),
        "avg_encode_ms": round(avg_enc_ms, 1),
        "effective_fps": round(eff_fps, 1),
    }


def main():
    print("=" * 60)
    print("ADERS — Phase 2 Baseline Benchmark")
    print("=" * 60)
    print(f"Model  : {DEFAULT_WEIGHTS}")
    print(f"imgsz  : {IMGSZ}  |  conf={CONF_THRESHOLD}  |  confirm={CONFIRMATION_FRAMES}  |  skip={SKIP_FRAMES}")

    print("\nLoading model weights...")
    t0 = time.perf_counter()
    model = YOLO(str(DEFAULT_WEIGHTS))
    load_ms = (time.perf_counter() - t0) * 1000
    print(f"✅ Model loaded in {load_ms:.0f} ms")

    results = []
    for clip in CLIPS:
        r = benchmark_clip(model, clip)
        if r:
            results.append(r)

    print("\n" + "=" * 60)
    print("SUMMARY TABLE")
    print("=" * 60)
    print(f"{'Clip':<35} {'FPS':>6} {'Inf ms':>7} {'Incidents':>10}")
    print("-" * 60)
    for r in results:
        name = r["clip"][:35]
        print(f"{name:<35} {r['effective_fps']:>6.1f} {r['avg_inference_ms']:>7.1f} {r['incidents_fired']:>10}")

    # Save results JSON for comparison after fixes
    out = ROOT / "scripts" / "benchmark_baseline.json"
    out.write_text(json.dumps({"config": {
        "imgsz": IMGSZ,
        "conf_threshold": CONF_THRESHOLD,
        "confirmation_frames": CONFIRMATION_FRAMES,
        "skip_frames": SKIP_FRAMES,
    }, "results": results}, indent=2))
    print(f"\n✅ Results saved to: {out}")


if __name__ == "__main__":
    main()
