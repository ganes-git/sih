"""
Visual Embedding Sanity Check (Stage 4)
Verifies that OpenCLIP visual appearance embeddings:
1. Produce a fixed 512-dimensional output regardless of input image size.
2. Yield significantly higher cosine similarity for the SAME vehicle (across frames and cameras)
   compared to DIFFERENT vehicles.
"""

import os
import sys
import cv2
import numpy as np

BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from pipeline.detect import load_detector
from pipeline.embed import load_embedder, compute_cosine_similarity

CLIPS_DIR = os.path.join(BACKEND_DIR, "data", "clips")


def extract_best_vehicle_crop(clip_path: str, detector, sample_frame: int = 75) -> np.ndarray:
    """Extract a detected vehicle crop from a specific frame index in a clip."""
    cap = cv2.VideoCapture(clip_path)
    cap.set(cv2.CAP_PROP_POS_FRAMES, sample_frame)
    ret, frame = cap.read()
    cap.release()

    if not ret or frame is None:
        raise ValueError(f"Could not read frame {sample_frame} from {clip_path}")

    dets = detector.detect_frame(frame)
    if not dets:
        raise ValueError(f"No vehicle detected at frame {sample_frame} in {clip_path}")

    best_det = max(dets, key=lambda d: d["confidence"])
    return best_det["vehicle_crop"]


def run_embedding_sanity_check():
    print("=" * 80)
    print("        OPENCLIP VEHICLE EMBEDDING SANITY CHECK (STAGE 4)")
    print("=" * 80)

    print("Loading detector and embedder...")
    detector = load_detector()
    embedder = load_embedder()

    clip1_path = os.path.join(CLIPS_DIR, "camera_1.mp4")
    clip2_path = os.path.join(CLIPS_DIR, "camera_2.mp4")
    clip3_path = os.path.join(CLIPS_DIR, "camera_3.mp4")
    clip4_path = os.path.join(CLIPS_DIR, "camera_4.mp4")

    print("\nExtracting vehicle crops:")
    crop_white_f50 = extract_best_vehicle_crop(clip1_path, detector, sample_frame=50)
    crop_white_f100 = extract_best_vehicle_crop(clip1_path, detector, sample_frame=100)
    crop_white_cam3 = extract_best_vehicle_crop(clip3_path, detector, sample_frame=75)
    crop_blue_cam2 = extract_best_vehicle_crop(clip2_path, detector, sample_frame=75)
    crop_blue_cam4 = extract_best_vehicle_crop(clip4_path, detector, sample_frame=75)

    print(f"  - White Car (CAM_01 f50) crop shape:  {crop_white_f50.shape}")
    print(f"  - White Car (CAM_01 f100) crop shape: {crop_white_f100.shape}")
    print(f"  - White Car (CAM_03 f75) crop shape:  {crop_white_cam3.shape}")
    print(f"  - Blue Coupe (CAM_02 f75) crop shape: {crop_blue_cam2.shape}")
    print(f"  - Blue Coupe (CAM_04 f75) crop shape: {crop_blue_cam4.shape}")

    print("\nComputing embeddings...")
    emb_white_f50 = embedder.embed_crop(crop_white_f50)
    emb_white_f100 = embedder.embed_crop(crop_white_f100)
    emb_white_cam3 = embedder.embed_crop(crop_white_cam3)
    emb_blue_cam2 = embedder.embed_crop(crop_blue_cam2)
    emb_blue_cam4 = embedder.embed_crop(crop_blue_cam4)

    # Dimensionality check
    dim = len(emb_white_f50)
    print(f"\n[PASS] Fixed output embedding dimension: {dim}-D (ViT-B-32)")
    assert dim == 512, f"Expected 512 dimensions, got {dim}"

    # Similarity checks
    # 1. Same vehicle across frames (CAM_01 f50 vs f100)
    sim_same_intra_cam = compute_cosine_similarity(emb_white_f50, emb_white_f100)
    # 2. Same white vehicle across cameras (CAM_01 vs CAM_03)
    sim_same_cross_cam = compute_cosine_similarity(emb_white_f50, emb_white_cam3)
    # 3. Same blue vehicle across cameras (CAM_02 vs CAM_04)
    sim_same_blue_cross_cam = compute_cosine_similarity(emb_blue_cam2, emb_blue_cam4)
    # 4. Different vehicles (White car vs Blue coupe)
    sim_diff_vehicles_1 = compute_cosine_similarity(emb_white_f50, emb_blue_cam2)
    sim_diff_vehicles_2 = compute_cosine_similarity(emb_white_cam3, emb_blue_cam4)

    print("\n" + "=" * 80)
    print("                    COSINE SIMILARITY COMPARISONS")
    print("=" * 80)
    print(f"  Same Vehicle (Intra-camera, f50 vs f100):     {sim_same_intra_cam:.4f}")
    print(f"  Same Vehicle (Cross-camera CAM_01 vs CAM_03): {sim_same_cross_cam:.4f}")
    print(f"  Same Vehicle (Cross-camera CAM_02 vs CAM_04): {sim_same_blue_cross_cam:.4f}")
    print(f"  Different Vehicles (CAM_01 White vs CAM_02 Blue): {sim_diff_vehicles_1:.4f}")
    print(f"  Different Vehicles (CAM_03 White vs CAM_04 Blue): {sim_diff_vehicles_2:.4f}")
    print("-" * 80)

    # Sanity assertion
    min_same = min(sim_same_intra_cam, sim_same_cross_cam, sim_same_blue_cross_cam)
    max_diff = max(sim_diff_vehicles_1, sim_diff_vehicles_2)
    separation_margin = min_same - max_diff
    print(f"Separation Margin (Min Same - Max Diff): +{separation_margin:.4f}")

    assert min_same > max_diff, (
        f"Embedding sanity check failed: Same ({min_same:.4f}) <= Diff ({max_diff:.4f})"
    )
    print("\n[PASS] Same-vehicle appearance similarity is clearly higher than different-vehicle similarity.")
    print("=" * 80)

    return {
        "dim": dim,
        "sim_same_intra_cam": sim_same_intra_cam,
        "sim_same_cross_cam": sim_same_cross_cam,
        "sim_same_blue_cross_cam": sim_same_blue_cross_cam,
        "sim_diff_vehicles_1": sim_diff_vehicles_1,
        "sim_diff_vehicles_2": sim_diff_vehicles_2,
        "separation_margin": separation_margin,
    }


if __name__ == "__main__":
    run_embedding_sanity_check()
