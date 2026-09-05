# Stage 3: Vehicle Detection, OCR & Multi-Frame Voting Pipeline

This stage implements the core ANPR pipeline and measures empirical character recognition accuracy against the ground truth dataset.

## Pipeline Architecture

The detection and recognition pipeline consists of three sequential modules:
1. `backend/pipeline/detect.py`: Pretrained YOLOv8 vehicle detection and bounding box cropping.
2. `backend/pipeline/ocr.py`: EasyOCR character extraction sampled on every 5th frame of vehicle appearance.
3. `backend/pipeline/vote.py`: Syntax repair for Indian look-alike character confusions and multi-frame confidence voting.

## Documented Shortcut & System Limitation

> [!IMPORTANT]
> **Plate Region Localization Shortcut:**
> Pretrained YOLOv8 weights (trained on the standard COCO dataset) classify general vehicle categories (`car`, `bus`, `truck`, `motorcycle`), but do not contain a dedicated anchor head for license plates.
> In this prototype pipeline, the plate region is approximated as the lower third (bottom 40%) of the vehicle's detected bounding box crop (`plate_y_start = int(vh * 0.58)`).
> 
> *Limitation Note for Evaluation:* In a commercial production ANPR system, a two-stage cascade (YOLO vehicle detector -> dedicated YOLO plate detector or WPOD-NET) is required to accurately isolate plates that are angled, off-center, or mounted at irregular bumper heights.

## Multi-Frame Confidence Voting Formula

For each unique candidate plate string $S$ with $k$ frame votes and individual OCR confidences $\{c_1, \dots, c_k\}$ out of $N$ total readings:
1. **Mean OCR Quality**: $\bar{c}_S = \frac{1}{k}\sum_{i=1}^k c_i$
2. **Vote Agreement / Frequency**: $f_S = \frac{k}{N}$
3. **Consistency Multiplier**: $p_S = \min\left(1.0, \frac{k}{k_{\min}}\right)$ where $k_{\min} = 2$
4. **Aggregate Score**:
   $$\text{Score}(S) = \bar{c}_S \times (0.65 \times f_S + 0.35 \times p_S) \times (\text{syntax validity bonus})$$

**Decision Rule**:
If $\text{Score}(S) \ge 0.50$, $k \ge 2$, and $S$ conforms to Indian registration syntax, the plate is **CONFIRMED**. Otherwise, the pipeline returns `plate_text = None` with `unconfirmed = True`.

## Multi-Camera Pipeline Test Output

Execution output from `python backend/pipeline/run_pipeline_test.py`:

```
==========================================================================================
          VEHICLE ANPR PIPELINE: STAGE 3 MULTI-CAMERA EVALUATION
==========================================================================================
Loading YOLOv8 detector (yolov8n.pt)...
Loading EasyOCR engine...
Pipelines loaded successfully.

[CAM_01] camera_1.mp4   | Detections: 26 | Plate: TN 07 AB 1234  | Conf: 0.7552 | Votes: 18/20 | [PASS - CLEAN]
[CAM_02] camera_2.mp4   | Detections: 29 | Plate: MH 12 CD 5678  | Conf: 0.8199 | Votes: 18/21 | [PASS - CLEAN]
[CAM_03] camera_3.mp4   | Detections: 27 | Plate: DL 01 EF 9012  | Conf: 0.7595 | Votes: 17/20 | [PASS - CLEAN]
[CAM_04] camera_4.mp4   | Detections: 28 | Plate: KA 05 GH 3456  | Conf: 0.8071 | Votes: 18/22 | [PASS - CLEAN]
[CAM_05] camera_5.mp4   | Detections: 26 | Plate: KL 07 JK 7890  | Conf: 0.7399 | Votes: 17/20 | [PASS - CLEAN]
[CAM_06] camera_6.mp4   | Detections: 29 | Plate: TS 09 LM 2345  | Conf: 0.7168 | Votes: 18/22 | [PASS - CLEAN]
[CAM_07] camera_7.mp4   | Detections: 29 | Plate: UNCONFIRMED    | Conf: 0.0000 | Votes: 0/0   | [PASS - ADVERSARIAL UNCONFIRMED]
[CAM_08] camera_8.mp4   | Detections:  0 | Plate: UNCONFIRMED    | Conf: 0.0000 | Votes: 0/0   | [PASS - ADVERSARIAL UNCONFIRMED]

==========================================================================================
Camera ID  | Condition                 | Detections | Plate Text       | Confidence | Status      
------------------------------------------------------------------------------------------
CAM_01     | Daylight Standard         | 26         | TN 07 AB 1234    | 0.7552     | CONFIRMED   
CAM_02     | Daylight Standard         | 29         | MH 12 CD 5678    | 0.8199     | CONFIRMED   
CAM_03     | Daylight Standard         | 27         | DL 01 EF 9012    | 0.7595     | CONFIRMED   
CAM_04     | Daylight Standard         | 28         | KA 05 GH 3456    | 0.8071     | CONFIRMED   
CAM_05     | Daylight Standard         | 26         | KL 07 JK 7890    | 0.7399     | CONFIRMED   
CAM_06     | Daylight Standard         | 29         | TS 09 LM 2345    | 0.7168     | CONFIRMED   
CAM_07     | Adversarial Degraded      | 29         | UNCONFIRMED      | 0.0000     | UNCONFIRMED 
CAM_08     | Adversarial Degraded      | 0          | UNCONFIRMED      | 0.0000     | UNCONFIRMED 
==========================================================================================
```

### Observations
- **Clean Clips (CAM_01 to CAM_06)**: Read cleanly with high confidence (0.7168 to 0.8199) and 17 to 18 consistent frame votes each.
- **Adversarial Clips (CAM_07 and CAM_08)**:
  - `CAM_07`: Vehicle is detected across 29 frames, but directional motion blur and physical occlusion prevent character extraction, correctly returning `UNCONFIRMED` with 0.0000 confidence.
  - `CAM_08`: Extreme 12% low illumination and high sensor noise cause detection and OCR failure, returning `UNCONFIRMED`.
  - Both adversarial clips satisfy the design requirement that plate reading fails under degraded conditions, providing the exact trigger needed for Stage 4 appearance re-identification.

## Measured OCR Accuracy

Execution output from `python backend/pipeline/eval_ocr.py`:

```
====================================================================================================
                 STAGE 3 OCR PIPELINE EVALUATION AGAINST GROUND TRUTH
====================================================================================================
Camera ID  | Type         | True Plate      | Predicted Plate | Conf     | Exact   | Lev Ratio 
----------------------------------------------------------------------------------------------------
CAM_01     | Standard     | TN 07 AB 1234   | TN 07 AB 1234   | 0.7552   | YES     | 100.00  %
CAM_02     | Standard     | MH 12 CD 5678   | MH 12 CD 5678   | 0.8199   | YES     | 100.00  %
CAM_03     | Standard     | DL 01 EF 9012   | DL 01 EF 9012   | 0.7595   | YES     | 100.00  %
CAM_04     | Standard     | KA 05 GH 3456   | KA 05 GH 3456   | 0.8071   | YES     | 100.00  %
CAM_05     | Standard     | KL 07 JK 7890   | KL 07 JK 7890   | 0.7399   | YES     | 100.00  %
CAM_06     | Standard     | TS 09 LM 2345   | TS 09 LM 2345   | 0.7168   | YES     | 100.00  %
CAM_07     | Adversarial  | HR 26 PQ 6789   | UNCONFIRMED     | 0.0000   | NO      | 0.00    %
CAM_08     | Adversarial  | UP 16 XY 4321   | UNCONFIRMED     | 0.0000   | NO      | 0.00    %
====================================================================================================
SUMMARY METRICS:
  (a) Exact-Match Accuracy (All 8 clips):          6/8 (75.00%)
  (b) Exact-Match Accuracy (6 Clean clips):       6/6 (100.00%)
  (c) Average Levenshtein Similarity (All 8):     75.00%
====================================================================================================
```

### Accuracy Analysis
- **Overall Dataset Accuracy**: 75.00% exact match across all 8 clips. This measured figure falls short of 90% because 2 of the 8 clips (25% of the dataset) are intentionally degraded adversarial inputs designed to defeat standard OCR.
- **Non-Adversarial Accuracy**: 100.00% exact match (6/6) across standard daylight clips with visible plates.
- **Character Similarity**: 75.00% average Levenshtein similarity across the full 8-camera network.
