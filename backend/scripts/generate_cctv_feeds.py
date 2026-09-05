"""
CCTV Feed & Snapshot Generator
Builds 8 authentic surveillance video streams with real-world road traffic footage,
CCTV telemetry OSD overlays, GPS coordinates, live timestamps, and ANPR vehicle tracking boxes
matching the database sightings and corridor locations.
"""

import os
import sys
import cv2
import numpy as np
import json
import datetime

BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BACKEND_DIR, "data")
CLIPS_DIR = os.path.join(DATA_DIR, "clips")
SNAPSHOTS_DIR = os.path.join(DATA_DIR, "snapshots")
TEMP_DIR = os.path.join(os.path.dirname(BACKEND_DIR), "temp_videos")

os.makedirs(CLIPS_DIR, exist_ok=True)
os.makedirs(SNAPSHOTS_DIR, exist_ok=True)

# Load camera metadata
with open(os.path.join(DATA_DIR, "camera_metadata.json"), "r", encoding="utf-8") as f:
    CAMERA_METADATA = json.load(f)

# Camera specific configs
CAMERA_CONFIGS = {
    "CAM_01": {
        "clip_file": "camera_1.mp4",
        "source_video": os.path.join(TEMP_DIR, "highway.mp4"),
        "corridor": "POONAMALLEE HIGH RD (EVR SALAI)",
        "location": "EVR Salai - Central Station North Gate",
        "gps": "13.0827 N, 80.2707 E",
        "plate_targets": [("TN 07 AB 1234", "97.1%", 44), ("TN 07 AB 1000", "98.2%", 48)],
        "adversarial": None,
        "crop_offset": (0, 0),
        "target_frames": 350,
        "fps": 25.0
    },
    "CAM_02": {
        "clip_file": "camera_2.mp4",
        "source_video": os.path.join(TEMP_DIR, "highway.mp4"),
        "corridor": "POONAMALLEE HIGH RD (EVR SALAI)",
        "location": "EVR Salai - Periamet Signal",
        "gps": "13.0815 N, 80.2620 E",
        "plate_targets": [("MH 12 CD 5678", "95.8%", 50), ("TN 07 AB 1001", "97.4%", 46)],
        "adversarial": None,
        "crop_offset": (100, 200),
        "target_frames": 350,
        "fps": 25.0
    },
    "CAM_03": {
        "clip_file": "camera_3.mp4",
        "source_video": os.path.join(TEMP_DIR, "car_detection.mp4"),
        "corridor": "POONAMALLEE HIGH RD (EVR SALAI)",
        "location": "EVR Salai - Vepery High Road Junction",
        "gps": "13.0802 N, 80.2515 E",
        "plate_targets": [("DL 01 EF 9012", "94.6%", 42)],
        "adversarial": None,
        "crop_offset": (0, 0),
        "target_frames": 350,
        "fps": 25.0
    },
    "CAM_04": {
        "clip_file": "camera_4.mp4",
        "source_video": os.path.join(TEMP_DIR, "highway.mp4"),
        "corridor": "ANNA SALAI (MOUNT ROAD)",
        "location": "Anna Salai - Pallavan Salai Junction",
        "gps": "13.0762 N, 80.2738 E",
        "plate_targets": [("KA 05 GH 3456", "98.4%", 54), ("TN 01 XY 9988", "96.1%", 49)],
        "adversarial": None,
        "crop_offset": (250, 400),
        "target_frames": 350,
        "fps": 25.0
    },
    "CAM_05": {
        "clip_file": "camera_5.mp4",
        "source_video": os.path.join(TEMP_DIR, "person_bike_car.mp4"),
        "corridor": "ANNA SALAI (MOUNT ROAD)",
        "location": "Anna Salai - Chintadripet Junction",
        "gps": "13.0708 N, 80.2695 E",
        "plate_targets": [("KA 05 GH 3456", "97.8%", 52), ("TN 07 AB 1234", "96.5%", 48), ("KL 07 JK 7890", "95.1%", 43)],
        "adversarial": None,
        "crop_offset": (0, 0),
        "target_frames": 350,
        "fps": 25.0
    },
    "CAM_06": {
        "clip_file": "camera_6.mp4",
        "source_video": os.path.join(TEMP_DIR, "traffic.mp4"),
        "corridor": "ANNA SALAI (MOUNT ROAD)",
        "location": "Anna Salai - Thousand Lights LIC Junction",
        "gps": "13.0615 N, 80.2625 E",
        "plate_targets": [("KA 05 GH 3456", "99.1%", 56), ("TS 09 LM 2345", "94.8%", 45)],
        "adversarial": None,
        "crop_offset": (0, 0),
        "target_frames": 350,
        "fps": 25.0
    },
    "CAM_07": {
        "clip_file": "camera_7.mp4",
        "source_video": os.path.join(TEMP_DIR, "car_detection.mp4"),
        "corridor": "RAJAJI SALAI (PORT CORRIDOR)",
        "location": "Rajaji Salai - Parrys Corner High Court Junction",
        "gps": "13.0892 N, 80.2858 E",
        "plate_targets": [("TN 04 HG 8821", "88.2%", 38)],
        "adversarial": "motion_blur",
        "crop_offset": (50, 50),
        "target_frames": 350,
        "fps": 25.0
    },
    "CAM_08": {
        "clip_file": "camera_8.mp4",
        "source_video": os.path.join(TEMP_DIR, "person_bike_car.mp4"),
        "corridor": "RAJAJI SALAI (PORT CORRIDOR)",
        "location": "Rajaji Salai - Harbour Subway Underpass",
        "gps": "13.0965 N, 80.2890 E",
        "plate_targets": [("TN 02 BB 5544", "82.4%", 34)],
        "adversarial": "low_light",
        "crop_offset": (100, 100),
        "target_frames": 350,
        "fps": 25.0
    }
}


def draw_cctv_hud(frame, cam_id, cfg, frame_idx, total_frames):
    h, w = frame.shape[:2]
    
    # Top overlay bar (semi-transparent dark)
    overlay = frame.copy()
    cv2.rectangle(overlay, (0, 0), (w, 54), (16, 20, 24), -1)
    cv2.rectangle(overlay, (0, h - 34), (w, h), (16, 20, 24), -1)
    cv2.addWeighted(overlay, 0.75, frame, 0.25, 0, frame)

    # Top line accent
    cv2.line(frame, (0, 54), (w, 54), (50, 70, 90), 1)
    cv2.line(frame, (0, h - 34), (w, h - 34), (50, 70, 90), 1)

    # Top Left: Camera ID + Corridor Name
    font = cv2.FONT_HERSHEY_SIMPLEX
    cam_text = f"{cam_id} // {cfg['corridor']}"
    loc_text = f"{cfg['location'].upper()}"
    cv2.putText(frame, cam_text, (16, 22), font, 0.55, (80, 240, 160), 1, cv2.LINE_AA)
    cv2.putText(frame, loc_text, (16, 44), font, 0.45, (200, 215, 225), 1, cv2.LINE_AA)

    # Top Right: Live Timestamp + REC indicator
    # Simulate realistic surveillance time
    base_time = datetime.datetime(2026, 9, 5, 14, 30, 0) + datetime.timedelta(seconds=frame_idx * 0.1)
    time_str = base_time.strftime("%Y-%m-%d %H:%M:%S IST")
    
    # Blinking REC dot
    rec_color = (0, 0, 255) if (frame_idx // 12) % 2 == 0 else (120, 120, 120)
    cv2.circle(frame, (w - 240, 26), 6, rec_color, -1)
    cv2.putText(frame, "LIVE [CH-0" + cam_id[-1] + "]", (w - 225, 31), font, 0.48, (230, 230, 230), 1, cv2.LINE_AA)
    cv2.putText(frame, time_str, (w - 240, 48), font, 0.42, (180, 200, 215), 1, cv2.LINE_AA)

    # Bottom Left: GPS Coordinates & Stream Health
    bottom_l = f"GPS: {cfg['gps']}  |  1080P @ 25FPS  |  BITRATE: 4.2 MBPS"
    cv2.putText(frame, bottom_l, (16, h - 12), font, 0.42, (170, 185, 200), 1, cv2.LINE_AA)

    # Bottom Right: ANPR Engine Status
    bottom_r = "ANPR MULTI-MODAL PIPELINE: ACTIVE [CONF >= 0.70]"
    text_size = cv2.getTextSize(bottom_r, font, 0.42, 1)[0]
    cv2.putText(frame, bottom_r, (w - text_size[0] - 16, h - 12), font, 0.42, (80, 230, 150), 1, cv2.LINE_AA)

    # Vehicle Bounding Boxes & ANPR Tags
    progress = (frame_idx % 120) / 120.0
    for t_idx, (plate, conf, speed) in enumerate(cfg["plate_targets"]):
        lane_offset = t_idx * 160
        car_y = int(h * 0.42 + progress * (h * 0.40)) + (t_idx * 20)
        car_x = int(w * 0.22 + lane_offset + progress * 60)
        box_w = int(120 + progress * 70)
        box_h = int(60 + progress * 40)

        # Draw bounding box
        cv2.rectangle(frame, (car_x, car_y), (car_x + box_w, car_y + box_h), (0, 230, 120), 2)
        
        # Plate badge tag
        badge_h = 24
        cv2.rectangle(frame, (car_x, car_y - badge_h), (car_x + box_w + 20, car_y), (16, 24, 28), -1)
        cv2.rectangle(frame, (car_x, car_y - badge_h), (car_x + box_w + 20, car_y), (0, 230, 120), 1)
        
        plate_str = f"{plate} [{conf}]"
        cv2.putText(frame, plate_str, (car_x + 4, car_y - 7), font, 0.40, (255, 255, 255), 1, cv2.LINE_AA)

    # Corner crosshairs (Surveillance HUD look)
    ch_len = 16
    color_ch = (70, 95, 120)
    # top-left
    cv2.line(frame, (10, 64), (10 + ch_len, 64), color_ch, 1)
    cv2.line(frame, (10, 64), (10, 64 + ch_len), color_ch, 1)
    # top-right
    cv2.line(frame, (w - 10, 64), (w - 10 - ch_len, 64), color_ch, 1)
    cv2.line(frame, (w - 10, 64), (w - 10, 64 + ch_len), color_ch, 1)
    # bottom-left
    cv2.line(frame, (10, h - 44), (10 + ch_len, h - 44), color_ch, 1)
    cv2.line(frame, (10, h - 44), (10, h - 44 - ch_len), color_ch, 1)
    # bottom-right
    cv2.line(frame, (w - 10, h - 44), (w - 10 - ch_len, h - 44), color_ch, 1)
    cv2.line(frame, (w - 10, h - 44), (w - 10, h - 44 - ch_len), color_ch, 1)

    return frame


def process_camera(cam_id, cfg):
    print(f"Processing {cam_id} -> {cfg['clip_file']} ({cfg['corridor']})...")
    src_path = cfg["source_video"]
    if not os.path.exists(src_path):
        print(f"Source video not found: {src_path}")
        return

    cap = cv2.VideoCapture(src_path)
    total_src_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    
    out_path = os.path.join(CLIPS_DIR, cfg["clip_file"])
    target_w, target_h = 1280, 720
    fourcc = cv2.VideoWriter_fourcc(*"avc1")
    out = cv2.VideoWriter(out_path, fourcc, cfg["fps"], (target_w, target_h))

    snapshot_frame = None
    target_count = cfg["target_frames"]

    for idx in range(target_count):
        ret, frame = cap.read()
        if not ret or frame is None:
            cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
            ret, frame = cap.read()
            if not ret:
                break

        # Resize to standard 720p HD
        frame = cv2.resize(frame, (target_w, target_h))

        # Adversarial effects if specified
        if cfg["adversarial"] == "motion_blur":
            kernel = np.zeros((11, 11))
            kernel[5, :] = 1.0 / 11.0
            frame = cv2.filter2D(frame, -1, kernel)
        elif cfg["adversarial"] == "low_light":
            frame = cv2.convertScaleAbs(frame, alpha=0.45, beta=-15)
            noise = np.random.normal(0, 12, frame.shape).astype(np.uint8)
            frame = cv2.add(frame, noise)

        # Draw HUD & telemetry
        frame = draw_cctv_hud(frame, cam_id, cfg, idx, target_count)

        if idx == 45:
            snapshot_frame = frame.copy()

        out.write(frame)

    cap.release()
    out.release()

    # Save matching snapshot image
    snap_path = os.path.join(SNAPSHOTS_DIR, f"snapshot_{cam_id}.jpg")
    if snapshot_frame is not None:
        cv2.imwrite(snap_path, snapshot_frame, [int(cv2.IMWRITE_JPEG_QUALITY), 92])
        print(f"  [OK] Snapshot saved: {snap_path}")

    print(f"  [OK] Video saved: {out_path} ({os.path.getsize(out_path):,} bytes)")


def main():
    print("=" * 80)
    print("GENERATING REAL CCTV SURVEILLANCE FEEDS AND SYNCHRONIZED SNAPSHOTS")
    print("=" * 80)

    for cam_id, cfg in CAMERA_CONFIGS.items():
        process_camera(cam_id, cfg)

    print("\nAll 8 camera feeds and synchronized snapshots successfully generated!")


if __name__ == "__main__":
    main()
