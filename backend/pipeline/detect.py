"""
Vehicle Detection Module (Stage 3)
Loads pretrained YOLOv8 model to detect vehicles and extract vehicle bounding box + plate crops.

KNOWN SHORTCUT / SYSTEM LIMITATION:
-----------------------------------
Pretrained YOLOv8 weights (trained on the standard COCO dataset) classify general vehicle categories
(car, bus, truck, motorcycle) but do not contain a dedicated bounding-box head for license plates.
In this pipeline, the license plate region is approximated as the lower third (bottom 40%) of the
detected vehicle bounding box crop.

In an end-to-end production ANPR architecture, a dedicated two-stage cascade (YOLO vehicle detector ->
YOLO license plate detector / WPOD-NET) would be placed between vehicle detection and OCR character
extraction to localize angled, recessed, or off-center plates.
"""

import os
from typing import List, Dict, Any, Tuple, Optional
import cv2
import numpy as np
from ultralytics import YOLO

# COCO vehicle class IDs: 2: car, 3: motorcycle, 5: bus, 7: truck
VEHICLE_CLASS_IDS = {2: "car", 3: "motorcycle", 5: "bus", 7: "truck"}

DEFAULT_MODEL_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "yolov8n.pt")


class VehicleDetector:
    """Wraps YOLOv8 for vehicle detection and approximated plate crop extraction."""

    def __init__(self, model_path: str = DEFAULT_MODEL_PATH, conf_thresh: float = 0.35):
        self.model_path = model_path if os.path.exists(model_path) else "yolov8n.pt"
        self.model = YOLO(self.model_path)
        self.conf_thresh = conf_thresh

    def detect_frame(self, frame: np.ndarray) -> List[Dict[str, Any]]:
        """
        Run vehicle detection on a single frame.

        Returns:
            List of detection dicts containing:
            - 'bbox': [x1, y1, x2, y2] pixel coordinates
            - 'class_name': detected vehicle category ('car', 'bus', 'truck')
            - 'confidence': detector confidence score (0.0 to 1.0)
            - 'vehicle_crop': full vehicle bounding box image patch
            - 'plate_crop': approximated lower-third plate crop
        """
        if frame is None or frame.size == 0:
            return []

        results = self.model(frame, verbose=False, conf=self.conf_thresh)
        detections = []
        h, w = frame.shape[:2]

        for r in results:
            for box in r.boxes:
                cls_id = int(box.cls[0])
                if cls_id in VEHICLE_CLASS_IDS:
                    conf = float(box.conf[0])
                    x1, y1, x2, y2 = [int(v) for v in box.xyxy[0].tolist()]

                    # Clamp coordinates to frame dimensions
                    x1, y1 = max(0, x1), max(0, y1)
                    x2, y2 = min(w, x2), min(h, y2)

                    if x2 <= x1 or y2 <= y1:
                        continue

                    vehicle_crop = frame[y1:y2, x1:x2].copy()
                    vh, vw = vehicle_crop.shape[:2]

                    # KNOWN SHORTCUT:
                    # License plate region approximated as lower 40% of the vehicle crop.
                    plate_y_start = int(vh * 0.58)
                    plate_crop = vehicle_crop[plate_y_start:vh, :].copy()

                    detections.append({
                        "bbox": [x1, y1, x2, y2],
                        "class_name": VEHICLE_CLASS_IDS[cls_id],
                        "confidence": conf,
                        "vehicle_crop": vehicle_crop,
                        "plate_crop": plate_crop,
                    })

        return detections


def load_detector(model_path: str = DEFAULT_MODEL_PATH, conf_thresh: float = 0.35) -> VehicleDetector:
    """Factory helper to instantiate VehicleDetector."""
    return VehicleDetector(model_path=model_path, conf_thresh=conf_thresh)
