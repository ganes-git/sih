"""
Identity Fusion & Trajectory Matching Test Suite (Stage 4)
Runs full pipeline on all 8 clips to build Sighting objects and evaluates:
  (a) Trajectory survival across an adversarial degraded camera:
      Composite score stays high between normal sighting and adversarial sighting (CAM_07),
      carried by the visual embedding signal even though plate reading failed (plate_score = 0.0).
  (b) Cloned plate detection:
      Synthetic clone case where a sighting carries an authentic plate string but a disparate
      vehicle embedding, confirming that clone_flag returns True.
  (c) Spatio-temporal transit gating:
      Implausible teleportation across distant junctions is rejected by the transit score.
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
from pipeline.embed import load_embedder
from pipeline.sighting import Sighting
from pipeline.match import (
    plate_score,
    visual_score,
    transit_score,
    composite_score,
    clone_flag,
)

CLIPS_DIR = os.path.join(BACKEND_DIR, "data", "clips")
METADATA_PATH = os.path.join(BACKEND_DIR, "data", "camera_metadata.json")


def build_all_sightings(detector, ocr_reader, embedder):
    with open(METADATA_PATH, "r", encoding="utf-8") as f:
        cam_metadata = json.load(f)

    sightings = {}
    base_epoch = 1756837200.0  # Baseline simulated epoch

    print("Extracting multi-camera sightings across all 8 clips:")
    for cam_id, meta in sorted(cam_metadata.items()):
        clip_path = os.path.join(CLIPS_DIR, meta["clip_file"])
        if not os.path.exists(clip_path):
            continue

        # 1. Detect & extract OCR readings (every 5th frame)
        clip_data = extract_clip_readings(clip_path, detector, ocr_reader, frame_stride=5)

        # 2. Multi-frame voting
        vote_res = vote_on_readings(clip_data["ocr_readings"])

        # 3. Visual embedding from sample vehicle crop
        vehicle_crop = clip_data["sample_vehicle_crop"]
        if vehicle_crop is not None:
            embedding = embedder.embed_crop(vehicle_crop)
        else:
            embedding = [0.0] * 512

        # Plausible city travel timeline: 3 minutes (180s) between successive corridor junctions
        cam_num = int(cam_id.split("_")[1])
        timestamp = base_epoch + (cam_num * 180.0)

        sighting = Sighting(
            sighting_id=f"SGT_{cam_id}",
            camera_id=cam_id,
            lat=meta["lat"],
            lon=meta["lon"],
            timestamp=timestamp,
            plate_text=vote_res["plate_text"],
            plate_confidence=vote_res["confidence"] if not vote_res["unconfirmed"] else None,
            embedding=embedding,
            unconfirmed_plate=vote_res["unconfirmed"],
        )
        sightings[cam_id] = sighting
        plate_str = sighting.plate_text if sighting.plate_text else "UNCONFIRMED"
        print(f"  [{cam_id}] {meta['label'][:38]:<38} | Plate: {plate_str:<14} | Emb: {len(embedding)}D")

    return sightings


def run_match_test():
    print("=" * 90)
    print("          MULTI-MODAL IDENTITY FUSION TEST SUITE (STAGE 4)")
    print("=" * 90)

    print("Loading pipeline models...")
    detector = load_detector()
    ocr_reader = load_ocr_reader(gpu=False)
    embedder = load_embedder()
    print("Models loaded successfully.\n")

    sightings = build_all_sightings(detector, ocr_reader, embedder)

    print("\n" + "=" * 90)
    print("TEST A: TRAJECTORY CONTINUITY ACROSS ADVERSARIAL DEGRADED CAMERA (CAM_07)")
    print("=" * 90)
    # Compare CAM_04 (Blue coupe, clean plate) and CAM_07 (Same Blue coupe, plate blurred/occluded)
    sgt_clean = sightings["CAM_04"]
    sgt_adversarial = sightings["CAM_07"]

    res_adv = composite_score(sgt_clean, sgt_adversarial)
    print(f"Sighting A: {sgt_clean.camera_id} (Plate: {sgt_clean.plate_text}, Conf: {sgt_clean.plate_confidence})")
    print(f"Sighting B: {sgt_adversarial.camera_id} (Plate: {sgt_adversarial.plate_text}, Unconfirmed: {sgt_adversarial.unconfirmed_plate})")
    print("-" * 90)
    print(f"  Plate Score (fuzzy text):           {res_adv['plate_score']:.4f}  (Plate unconfirmed on CAM_07)")
    print(f"  Visual Score (OpenCLIP cosine):     {res_adv['visual_score']:.4f}  (Appearance carries identity)")
    print(f"  Transit Score (distance/speed):     {res_adv['transit_score']:.4f}  ({res_adv['transit_details']['distance_km']} km in {res_adv['transit_details']['time_delta_sec']}s)")
    print(f"  Matching Regime:                    {res_adv['regime']}")
    print(f"  Composite Identity Score:           {res_adv['composite_score']:.4f}")
    print(f"  Trajectory Match Decision:          {'CONFIRMED MATCH' if res_adv['is_match'] else 'REJECTED'}")
    assert res_adv["is_match"], "Expected trajectory to be confirmed via visual Re-ID fallback!"
    print("[PASS] Trajectory survived unreadable plate via OpenCLIP visual appearance fallback.")

    print("\n" + "=" * 90)
    print("TEST B: CLONED PLATE DETECTION (IDENTICAL PLATE TEXT, DIFFERENT VEHICLE)")
    print("=" * 90)
    # Synthetic clone: Clone CAM_01's white car plate onto CAM_02's blue car embedding
    sgt_original = sightings["CAM_01"]
    sgt_clone = Sighting(
        sighting_id="SGT_CLONE_TEST",
        camera_id="CAM_CLONE",
        lat=13.0750,
        lon=80.2650,
        timestamp=sgt_original.timestamp + 300.0,
        plate_text=sgt_original.plate_text,  # Identical plate: "TN 07 AB 1234"
        plate_confidence=0.95,
        embedding=sightings["CAM_02"].embedding,  # Disparate vehicle: Blue coupe embedding
        unconfirmed_plate=False,
    )

    res_clone = composite_score(sgt_original, sgt_clone)
    p_score = plate_score(sgt_original, sgt_clone)
    v_score = visual_score(sgt_original, sgt_clone)
    is_clone = clone_flag(sgt_original, sgt_clone)

    print(f"Vehicle A (Original): {sgt_original.camera_id} White Sedan (Plate: {sgt_original.plate_text})")
    print(f"Vehicle B (Clone):    CAM_CLONE Blue Coupe (Plate: {sgt_clone.plate_text})")
    print("-" * 90)
    print(f"  Plate Score:                        {p_score:.4f} (Near-exact match)")
    print(f"  Visual Score:                       {v_score:.4f} (Visually disparate vehicles)")
    print(f"  Clone Detection Flag:               {is_clone}")
    print(f"  Composite Decision:                 {'BLOCKED AS CLONE' if not res_clone['is_match'] and is_clone else 'MATCH'}")
    assert is_clone, "Expected clone_flag to trigger for plate spoofing!"
    print("[PASS] Cloned plate successfully detected and blocked from erroneous trajectory merging.")

    print("\n" + "=" * 90)
    print("TEST C: SPATIO-TEMPORAL TRANSIT PLAUSIBILITY GATING")
    print("=" * 90)
    # Implausible transit: 25 km distance traversed in 30 seconds (~3000 km/h)
    sgt_teleport = Sighting(
        sighting_id="SGT_TELEPORT",
        camera_id="CAM_FAR",
        lat=12.8500,
        lon=80.1500,  # ~28 km away
        timestamp=sgt_original.timestamp + 30.0,  # Only 30 seconds later
        plate_text=sgt_original.plate_text,
        plate_confidence=0.95,
        embedding=sgt_original.embedding,
        unconfirmed_plate=False,
    )
    res_teleport = composite_score(sgt_original, sgt_teleport)
    print(f"Trip: {sgt_original.camera_id} -> CAM_FAR ({res_teleport['transit_details']['distance_km']} km in {res_teleport['transit_details']['time_delta_sec']}s)")
    print(f"  Implied Speed:                      {res_teleport['transit_details']['implied_speed_kmh']} km/h")
    print(f"  Transit Plausibility Score:         {res_teleport['transit_score']:.4f}")
    print(f"  Composite Score:                    {res_teleport['composite_score']:.4f} (Pulled down by transit gate)")
    print(f"  Match Decision:                     {'REJECTED (IMPLAUSIBLE)' if not res_teleport['is_match'] else 'MATCH'}")
    assert not res_teleport["is_match"], "Expected transit gate to reject impossible speed!"
    print("[PASS] Spatio-temporal transit gate rejected physically implausible trajectory hop.")
    print("=" * 90)


if __name__ == "__main__":
    run_match_test()
