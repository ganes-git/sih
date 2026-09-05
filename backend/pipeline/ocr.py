"""
Plate OCR Module (Stage 3)
Runs EasyOCR on approximated plate crops extracted from detected vehicles.
Samples every 5th frame of a vehicle's appearance in a clip to collect all candidate text readings.
"""

from typing import List, Dict, Any, Tuple, Optional
import cv2
import numpy as np
import easyocr


class PlateOCR:
    """Wraps EasyOCR for text extraction and character confidence scoring on plate crops."""

    def __init__(self, languages: Optional[List[str]] = None, gpu: bool = False):
        if languages is None:
            languages = ["en"]
        self.reader = easyocr.Reader(languages, gpu=gpu, download_enabled=False)

    def read_plate(self, plate_crop: np.ndarray) -> List[Tuple[str, float]]:
        """
        Run OCR on an individual plate crop image patch.

        Returns:
            List of (text, confidence) tuples detected in the crop.
        """
        if plate_crop is None or plate_crop.size == 0:
            return []

        # Enhance low resolution crops to assist character boundary detection
        ph, pw = plate_crop.shape[:2]
        img_for_ocr = plate_crop
        if ph < 60 or pw < 180:
            scale = max(2.0, 180.0 / max(1, pw))
            img_for_ocr = cv2.resize(
                plate_crop, (0, 0), fx=scale, fy=scale, interpolation=cv2.INTER_CUBIC
            )

        try:
            results = self.reader.readtext(img_for_ocr)
        except Exception:
            return []

        readings = []
        for bbox, text, conf in results:
            cleaned_str = text.strip() if text else ""
            if cleaned_str:
                readings.append((cleaned_str, float(conf)))

        return readings


def load_ocr_reader(gpu: bool = False) -> PlateOCR:
    """Factory helper to instantiate PlateOCR reader."""
    return PlateOCR(languages=["en"], gpu=gpu)


def extract_clip_readings(
    video_path: str,
    detector,
    ocr_reader: PlateOCR,
    frame_stride: int = 5,
) -> Dict[str, Any]:
    """
    Process a video clip:
    - Iterates over frames with frame_stride (every 5th frame)
    - Detects vehicles via YOLOv8
    - Crops approximated plate region
    - Runs OCR on each vehicle's plate crop
    - Aggregates all candidate text readings across frames

    Returns:
        Dict containing:
        - 'video_path': path to video file
        - 'total_frames': total frame count in clip
        - 'sampled_frames': number of sampled frames
        - 'vehicle_detections_count': total vehicle detections
        - 'ocr_readings': list of raw candidate reading dicts
        - 'sample_vehicle_crop': representative vehicle crop for visual matching
    """
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        return {
            "video_path": video_path,
            "error": "Could not open video file",
            "ocr_readings": [],
            "vehicle_detections_count": 0,
            "sampled_frames": 0,
            "total_frames": 0,
            "sample_vehicle_crop": None,
        }

    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    frame_idx = 0
    sampled_count = 0
    total_vehicle_detections = 0
    all_readings = []
    vehicle_crops = []

    while True:
        ret, frame = cap.read()
        if not ret:
            break

        if frame_idx % frame_stride == 0:
            sampled_count += 1
            dets = detector.detect_frame(frame)
            if dets:
                total_vehicle_detections += len(dets)
                for d in dets:
                    plate_crop = d["plate_crop"]
                    if d["vehicle_crop"] is not None:
                        vehicle_crops.append(d["vehicle_crop"])

                    ocr_results = ocr_reader.read_plate(plate_crop)
                    for text, conf in ocr_results:
                        all_readings.append({
                            "frame_idx": frame_idx,
                            "bbox": d["bbox"],
                            "raw_text": text,
                            "ocr_confidence": conf,
                            "plate_crop": plate_crop,
                        })

        frame_idx += 1

    cap.release()

    return {
        "video_path": video_path,
        "total_frames": total_frames,
        "sampled_frames": sampled_count,
        "vehicle_detections_count": total_vehicle_detections,
        "ocr_readings": all_readings,
        "sample_vehicle_crop": vehicle_crops[len(vehicle_crops) // 2] if vehicle_crops else None,
    }
