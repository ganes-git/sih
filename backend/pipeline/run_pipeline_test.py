"""
Pipeline Multi-Camera Evaluation Test (Stage 3)
Runs Detect -> OCR -> Vote across all 8 virtual camera clips.
Prints summary evaluation table with camera_id, vehicle count, final plate text (or UNCONFIRMED),
confidence, and vote metrics.
"""

import os
import sys
import json
import time

BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from pipeline.detect import load_detector
from pipeline.ocr import load_ocr_reader, extract_clip_readings
from pipeline.vote import vote_on_readings

CLIPS_DIR = os.path.join(BACKEND_DIR, "data", "clips")
METADATA_PATH = os.path.join(BACKEND_DIR, "data", "camera_metadata.json")


def run_all_clips():
    print("=" * 90)
    print("          VEHICLE ANPR PIPELINE: STAGE 3 MULTI-CAMERA EVALUATION")
    print("=" * 90)

    with open(METADATA_PATH, "r", encoding="utf-8") as f:
        cam_metadata = json.load(f)

    print("Loading YOLOv8 detector (yolov8n.pt)...")
    detector = load_detector()
    print("Loading EasyOCR engine...")
    ocr_reader = load_ocr_reader(gpu=False)
    print("Pipelines loaded successfully.\n")

    results_table = []

    for cam_id, meta in sorted(cam_metadata.items()):
        clip_file = meta["clip_file"]
        clip_path = os.path.join(CLIPS_DIR, clip_file)

        if not os.path.exists(clip_path):
            print(f"[-] Warning: {clip_file} not found at {clip_path}")
            continue

        start_t = time.time()
        # 1. Detect vehicles & extract OCR readings (sampled every 5th frame)
        clip_data = extract_clip_readings(clip_path, detector, ocr_reader, frame_stride=5)

        # 2. Multi-frame confidence voting and syntax repair
        vote_result = vote_on_readings(clip_data["ocr_readings"])
        elapsed = time.time() - start_t

        plate_display = vote_result["plate_text"] if not vote_result["unconfirmed"] else "UNCONFIRMED"
        conf_display = f"{vote_result['confidence']:.4f}"
        votes_display = f"{vote_result.get('vote_count', 0)}/{vote_result.get('total_readings', 0)}"

        row = {
            "camera_id": cam_id,
            "label": meta["label"],
            "clip_file": clip_file,
            "is_adversarial": meta["is_adversarial"],
            "sampled_frames": clip_data["sampled_frames"],
            "vehicle_detections": clip_data["vehicle_detections_count"],
            "plate_text": plate_display,
            "confidence": conf_display,
            "raw_conf": vote_result["confidence"],
            "votes": votes_display,
            "unconfirmed": vote_result["unconfirmed"],
            "elapsed_sec": round(elapsed, 2),
        }
        results_table.append(row)

        status_tag = "[PASS - CLEAN]" if not row["unconfirmed"] else "[PASS - ADVERSARIAL UNCONFIRMED]"
        print(f"[{cam_id}] {clip_file:14s} | Detections: {row['vehicle_detections']:2d} | "
              f"Plate: {row['plate_text']:14s} | Conf: {row['confidence']} | "
              f"Votes: {row['votes']:5s} | {status_tag}")

    print("\n" + "=" * 90)
    print(f"{'Camera ID':<10} | {'Condition':<25} | {'Detections':<10} | {'Plate Text':<16} | {'Confidence':<10} | {'Status':<12}")
    print("-" * 90)
    for r in results_table:
        cond_label = "Adversarial Degraded" if r["is_adversarial"] else "Daylight Standard"
        status_str = "UNCONFIRMED" if r["unconfirmed"] else "CONFIRMED"
        print(f"{r['camera_id']:<10} | {cond_label:<25} | {r['vehicle_detections']:<10} | {r['plate_text']:<16} | {r['confidence']:<10} | {status_str:<12}")
    print("=" * 90)

    return results_table


if __name__ == "__main__":
    run_all_clips()
