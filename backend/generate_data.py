"""
Synthetic Video Clip Generator for Vehicle Re-ID + ANPR Pipeline (Stage 2)
Generates 8 realistic traffic clips (6 clean, 2 adversarial) using photorealistic
vehicle cutouts with rendered Indian license plates moving across road backgrounds.
"""

import os
import cv2
import numpy as np
import urllib.request

CLIPS_DIR = os.path.join(os.path.dirname(__file__), "data", "clips")
os.makedirs(CLIPS_DIR, exist_ok=True)

# Curated open-licensed high-res car images from Unsplash (permissive license)
CAR_TEMPLATES = [
    {
        "id": "car_red",
        "url": "https://images.unsplash.com/photo-1549399542-7e3f8b79c341?w=800",
        "crop_box": (100, 350, 700, 700),  # y1, x1, y2, x2
    },
    {
        "id": "car_white",
        "url": "https://images.unsplash.com/photo-1552519507-da3b142c6e3d?w=800",
        "crop_box": (150, 100, 420, 680),
    },
    {
        "id": "car_blue",
        "url": "https://images.unsplash.com/photo-1503376780353-7e6692767b70?w=800",
        "crop_box": (120, 80, 410, 660),
    },
    {
        "id": "car_silver",
        "url": "https://images.unsplash.com/photo-1583121274602-3e2820c69888?w=800",
        "crop_box": (130, 80, 430, 680),
    },
]

CLIP_CONFIGS = [
    {
        "filename": "camera_1.mp4",
        "camera_id": "CAM_01",
        "car_idx": 1,  # car_white
        "plate_text": "TN 07 AB 1234",
        "adversarial": None,
    },
    {
        "filename": "camera_2.mp4",
        "camera_id": "CAM_02",
        "car_idx": 2,  # car_blue
        "plate_text": "MH 12 CD 5678",
        "adversarial": None,
    },
    {
        "filename": "camera_3.mp4",
        "camera_id": "CAM_03",
        "car_idx": 1,  # car_white
        "plate_text": "DL 01 EF 9012",
        "adversarial": None,
    },
    {
        "filename": "camera_4.mp4",
        "camera_id": "CAM_04",
        "car_idx": 2,  # car_blue
        "plate_text": "KA 05 GH 3456",
        "adversarial": None,
    },
    {
        "filename": "camera_5.mp4",
        "camera_id": "CAM_05",
        "car_idx": 1,  # car_white
        "plate_text": "KL 07 JK 7890",
        "adversarial": None,
    },
    {
        "filename": "camera_6.mp4",
        "camera_id": "CAM_06",
        "car_idx": 2,  # car_blue
        "plate_text": "TS 09 LM 2345",
        "adversarial": None,
    },
    {
        "filename": "camera_7.mp4",
        "camera_id": "CAM_07",
        "car_idx": 2,  # car_blue
        "plate_text": "HR 26 PQ 6789",
        "adversarial": "motion_blur_and_occlusion",
    },
    {
        "filename": "camera_8.mp4",
        "camera_id": "CAM_08",
        "car_idx": 1,  # car_white
        "plate_text": "UP 16 XY 4321",
        "adversarial": "low_light_and_noise",
    },
]


def download_car_images():
    """Download and cache car templates."""
    cached = []
    headers = {"User-Agent": "Mozilla/5.0"}
    for t in CAR_TEMPLATES:
        req = urllib.request.Request(t["url"], headers=headers)
        with urllib.request.urlopen(req, timeout=10) as resp:
            arr = np.asarray(bytearray(resp.read()), dtype=np.uint8)
            img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
            y1, x1, y2, x2 = t["crop_box"]
            crop = img[y1:y2, x1:x2]
            cached.append(crop)
    return cached


def create_road_background(w=1280, h=720, cam_idx=1):
    """Create a textured asphalt road background with realistic road scenery."""
    bg = np.zeros((h, w, 3), dtype=np.uint8)
    
    # Sky / background scenery (top 35%)
    sky_colors = [
        (220, 200, 180),  # daylight
        (210, 210, 190),
        (200, 215, 210),
        (220, 210, 200),
        (215, 205, 195),
        (225, 215, 205),
        (190, 180, 170),  # overcast coastal
        (30, 25, 35),     # dark tunnel
    ]
    sky_c = sky_colors[cam_idx - 1]
    bg[0:int(h*0.35), :] = sky_c
    
    # Road surface (lower 65%)
    road_y = int(h * 0.35)
    road_h = h - road_y
    road_color = (45, 48, 52) if cam_idx != 8 else (20, 22, 25)
    bg[road_y:, :] = road_color
    
    # Road texture noise
    noise = np.random.randint(-5, 6, (road_h, w, 3), dtype=np.int16)
    road_area = np.clip(bg[road_y:, :].astype(np.int16) + noise, 0, 255).astype(np.uint8)
    bg[road_y:, :] = road_area
    
    # Lane divider lines
    for x in range(0, w, 120):
        cv2.rectangle(bg, (x, int(h*0.75)), (x+60, int(h*0.75)+12), (230, 230, 230), -1)
    
    # Sidewalk / curb
    cv2.rectangle(bg, (0, int(h*0.35)), (w, int(h*0.38)), (140, 140, 140), -1)
    
    return bg


def generate_clip(cfg, car_img, out_path, duration_sec=10, fps=15):
    """Generate an MP4 clip with smooth vehicle traversal and plate rendering."""
    w, h = 1280, 720
    total_frames = int(duration_sec * fps)
    
    # Vehicle scaling (keep target width ~500px, height ~300px)
    target_cw = 520
    scale = target_cw / car_img.shape[1]
    target_ch = int(car_img.shape[0] * scale)
    car_resized = cv2.resize(car_img, (target_cw, target_ch), interpolation=cv2.INTER_LANCZOS4)
    
    # Render clear Indian number plate onto the lower bumper area
    car_with_plate = car_resized.copy()
    pw, ph = int(target_cw * 0.44), int(target_ch * 0.20)
    px = int((target_cw - pw) / 2)
    py = int(target_ch * 0.68)
    
    # Plate background (white with black border)
    cv2.rectangle(car_with_plate, (px, py), (px+pw, py+ph), (255, 255, 255), -1)
    cv2.rectangle(car_with_plate, (px, py), (px+pw, py+ph), (10, 10, 10), 3)
    
    # Plate text
    font_scale = 0.85
    thickness = 2
    text_x = px + 12
    text_y = py + int(ph * 0.72)
    cv2.putText(
        car_with_plate,
        cfg["plate_text"],
        (text_x, text_y),
        cv2.FONT_HERSHEY_SIMPLEX,
        font_scale,
        (0, 0, 0),
        thickness,
        cv2.LINE_AA,
    )
    
    # Adversarial Modifications on Plate
    if cfg["adversarial"] == "motion_blur_and_occlusion":
        # Heavy horizontal motion blur kernel on plate region
        ksize = 35
        kernel_motion_blur = np.zeros((ksize, ksize))
        kernel_motion_blur[int((ksize-1)/2), :] = np.ones(ksize) / ksize
        blurred_plate = cv2.filter2D(car_with_plate[py:py+ph, px:px+pw], -1, kernel_motion_blur)
        car_with_plate[py:py+ph, px:px+pw] = blurred_plate
        
        # Heavy physical occlusion / mud smudge across middle of the plate
        cv2.rectangle(car_with_plate, (px + int(pw*0.35), py - 2), (px + int(pw*0.75), py + ph + 2), (35, 45, 55), -1)
        cv2.circle(car_with_plate, (px + int(pw*0.5), py + int(ph*0.5)), 25, (40, 50, 60), -1)
    
    cam_num = int(cfg["camera_id"].split("_")[1])
    base_bg = create_road_background(w, h, cam_num)
    
    # Video writer
    fourcc = cv2.VideoWriter_fourcc(*'mp4v')
    writer = cv2.VideoWriter(out_path, fourcc, fps, (w, h))
    
    # Traversal coordinates: vehicle enters from right or left, moves through frame
    start_x = -target_cw + 50
    end_x = w + 50
    fixed_y = int(h * 0.40)
    
    for frame_idx in range(total_frames):
        frame = base_bg.copy()
        
        # Linear motion across the scene
        t = frame_idx / float(total_frames)
        curr_x = int(start_x + t * (end_x - start_x))
        curr_y = fixed_y
        
        # Composite vehicle onto frame
        x1_src = max(0, -curr_x)
        y1_src = max(0, -curr_y)
        x2_src = min(target_cw, w - curr_x)
        y2_src = min(target_ch, h - curr_y)
        
        x1_dst = max(0, curr_x)
        y1_dst = max(0, curr_y)
        x2_dst = min(w, curr_x + target_cw)
        y2_dst = min(h, curr_y + target_ch)
        
        if x2_dst > x1_dst and y2_dst > y1_dst and x2_src > x1_src and y2_src > y1_src:
            car_patch = car_with_plate[y1_src:y2_src, x1_src:x2_src]
            frame[y1_dst:y2_dst, x1_dst:x2_dst] = car_patch
        
        # Adversarial Clip 8: Low Light / Extreme Noise / Sensor Degradation
        if cfg["adversarial"] == "low_light_and_noise":
            # Scale brightness down to 12% (very dark night scene)
            dark_frame = (frame.astype(np.float32) * 0.12).astype(np.uint8)
            # Add heavy Gaussian sensor noise
            noise = np.random.normal(0, 35, dark_frame.shape).astype(np.float32)
            noisy_dark = np.clip(dark_frame.astype(np.float32) + noise, 0, 255).astype(np.uint8)
            frame = noisy_dark
            
        writer.write(frame)
        
    writer.release()
    print(f"Generated {out_path} ({total_frames} frames, {duration_sec}s @ {fps}fps)")


def main():
    print("Downloading base car templates...")
    car_images = download_car_images()
    print(f"Downloaded {len(car_images)} car templates.")
    
    for cfg in CLIP_CONFIGS:
        out_file = os.path.join(CLIPS_DIR, cfg["filename"])
        car_img = car_images[cfg["car_idx"]]
        print(f"Rendering {cfg['filename']} for {cfg['camera_id']} ({cfg['plate_text']})...")
        generate_clip(cfg, car_img, out_file, duration_sec=10, fps=15)
        
    print("\nAll 8 synthetic camera clips successfully generated in backend/data/clips/!")


if __name__ == "__main__":
    main()
