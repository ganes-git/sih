"""
OCR Quantitative Evaluation Module (Stage 3)
Compares pipeline predictions against ground_truth.json across all 8 clips.
Computes:
  (a) Exact-match accuracy across all 8 clips
  (b) Exact-match accuracy across the 6 non-adversarial clips
  (c) Average character-level similarity (Levenshtein ratio) across all 8 clips
"""

import os
import sys
import json
import re
import Levenshtein

BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from pipeline.detect import load_detector
from pipeline.ocr import load_ocr_reader, extract_clip_readings
from pipeline.vote import vote_on_readings, clean_raw_ocr_text

CLIPS_DIR = os.path.join(BACKEND_DIR, "data", "clips")
METADATA_PATH = os.path.join(BACKEND_DIR, "data", "camera_metadata.json")
GROUND_TRUTH_PATH = os.path.join(BACKEND_DIR, "data", "ground_truth.json")


def run_evaluation():
    with open(METADATA_PATH, "r", encoding="utf-8") as f:
        cam_metadata = json.load(f)

    with open(GROUND_TRUTH_PATH, "r", encoding="utf-8") as f:
        ground_truth = json.load(f)

    detector = load_detector()
    ocr_reader = load_ocr_reader(gpu=False)

    total_clips = len(cam_metadata)
    exact_matches_all = 0
    exact_matches_clean = 0
    clean_clips_count = 0
    levenshtein_scores = []
    eval_rows = []

    print("=" * 100)
    print("                 STAGE 3 OCR PIPELINE EVALUATION AGAINST GROUND TRUTH")
    print("=" * 100)

    for cam_id, meta in sorted(cam_metadata.items()):
        clip_file = meta["clip_file"]
        clip_path = os.path.join(CLIPS_DIR, clip_file)
        true_plate = ground_truth.get(cam_id) or ground_truth.get(meta["clip_file"].split(".")[0])

        clip_data = extract_clip_readings(clip_path, detector, ocr_reader, frame_stride=5)
        vote_result = vote_on_readings(clip_data["ocr_readings"])

        pred_plate = vote_result["plate_text"] if not vote_result["unconfirmed"] else None
        
        # Clean both for exact string comparison
        clean_pred = clean_raw_ocr_text(pred_plate) if pred_plate else ""
        clean_true = clean_raw_ocr_text(true_plate)

        is_exact_match = (clean_pred == clean_true) and (len(clean_true) > 0)
        lev_ratio = Levenshtein.ratio(clean_pred, clean_true)
        levenshtein_scores.append(lev_ratio)

        if is_exact_match:
            exact_matches_all += 1

        is_adversarial = meta["is_adversarial"]
        if not is_adversarial:
            clean_clips_count += 1
            if is_exact_match:
                exact_matches_clean += 1

        eval_rows.append({
            "camera_id": cam_id,
            "clip_file": clip_file,
            "is_adversarial": is_adversarial,
            "true_plate": true_plate,
            "pred_plate": pred_plate if pred_plate else "UNCONFIRMED",
            "confidence": vote_result["confidence"],
            "exact_match": is_exact_match,
            "lev_ratio": lev_ratio,
        })

    # Metrics computation
    acc_all = (exact_matches_all / total_clips) * 100.0 if total_clips > 0 else 0.0
    acc_clean = (exact_matches_clean / clean_clips_count) * 100.0 if clean_clips_count > 0 else 0.0
    avg_lev = (sum(levenshtein_scores) / total_clips) * 100.0 if total_clips > 0 else 0.0

    print(f"{'Camera ID':<10} | {'Type':<12} | {'True Plate':<15} | {'Predicted Plate':<15} | {'Conf':<8} | {'Exact':<7} | {'Lev Ratio':<10}")
    print("-" * 100)
    for r in eval_rows:
        type_str = "Adversarial" if r["is_adversarial"] else "Standard"
        exact_str = "YES" if r["exact_match"] else "NO"
        print(f"{r['camera_id']:<10} | {type_str:<12} | {r['true_plate']:<15} | {r['pred_plate']:<15} | {r['confidence']:<8.4f} | {exact_str:<7} | {r['lev_ratio'] * 100.0:<8.2f}%")

    print("=" * 100)
    print("SUMMARY METRICS:")
    print(f"  (a) Exact-Match Accuracy (All 8 clips):          {exact_matches_all}/{total_clips} ({acc_all:.2f}%)")
    print(f"  (b) Exact-Match Accuracy (6 Clean clips):       {exact_matches_clean}/{clean_clips_count} ({acc_clean:.2f}%)")
    print(f"  (c) Average Levenshtein Similarity (All 8):     {avg_lev:.2f}%")
    print("=" * 100)

    return {
        "acc_all": acc_all,
        "acc_clean": acc_clean,
        "avg_lev": avg_lev,
        "eval_rows": eval_rows,
    }


if __name__ == "__main__":
    run_evaluation()
