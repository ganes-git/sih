# Stage 4: Multi-Modal Identity Fusion & Trajectory Matching

This stage is not the project's main differentiator. It serves as the underlying plumbing that maintains continuous vehicle identity across camera hops, providing reliable trajectories for the corridor route-anomaly engine built in Stage 5.

Standard commercial ANPR systems identify vehicles strictly through plate text strings. This single-signal approach fails when plates are obscured, damaged, unlit, or cloned. This stage fuses three distinct signals into a unified identity model:
1. Plate text fuzzy similarity (from Stage 3 OCR).
2. Visual appearance embedding (OpenCLIP ViT-B-32).
3. Spatio-temporal transit plausibility (Haversine distance vs. elapsed travel time).

## Pipeline Modules

- `backend/pipeline/embed.py`: Wraps OpenCLIP (`ViT-B-32`, `laion2b_s34b_b79k`) to generate fixed-length 512-dimensional L2-normalized feature vectors for vehicle crops.
- `backend/pipeline/sighting.py`: Canonical `Sighting` data model capturing camera ID, GPS coordinates, timestamp, plate text, plate confidence, 512-D embedding, and snapshot path.
- `backend/pipeline/match.py`: Scoring functions (`plate_score`, `visual_score`, `transit_score`, `composite_score`, `clone_flag`).
- `backend/pipeline/test_embed.py`: Embedding sanity check validating dimensionality and same-vehicle vs. different-vehicle separation.
- `backend/pipeline/test_match.py`: Verification of trajectory continuity across adversarial clips, clone detection, and transit gating.

## Scoring Formulas & Weighting

### 1. Plate Text Score ($S_{\text{plate}}$)
Computed via Levenshtein ratio on normalized plate strings:
$$S_{\text{plate}} = \text{LevenshteinRatio}(\text{plate}_a, \text{plate}_b)$$
Returns $0.0$ if either sighting lacks a confirmed plate reading.

### 2. Visual Appearance Score ($S_{\text{visual}}$)
Computed via cosine similarity between 512-dimensional OpenCLIP embeddings:
$$S_{\text{visual}} = \max\left(0.0, \min\left(1.0, \mathbf{v}_a \cdot \mathbf{v}_b\right)\right)$$

### 3. Transit Plausibility Score ($S_{\text{transit}}$)
Calculates implied travel speed $v = \frac{\text{distance\_km}}{\Delta t_{\text{hours}}}$ using the Haversine distance between camera coordinates:
- If $v \le 90.0\text{ km/h}$ (constant `MAX_CITY_SPEED_KMH`): $S_{\text{transit}} = 1.0$.
- If $v > 90.0\text{ km/h}$: decays toward zero via Gaussian roll-off:
  $$S_{\text{transit}} = \exp\left(-\frac{(v - 90)^2}{2 \times 25^2}\right)$$
- If elapsed time is near zero ($\Delta t < 1\text{s}$) across distant cameras, $S_{\text{transit}} = 0.0$ (impossible teleportation).

### 4. Composite Score ($S_{\text{composite}}$)
The fusion logic operates under two regimes:
- **Dual Confirmed Plates**: Plate text carries primary weight, while visual appearance confirms:
  $$S_{\text{base}} = 0.65 \times S_{\text{plate}} + 0.35 \times S_{\text{visual}}$$
- **Unconfirmed / Degraded Plate**: Visual appearance carries 100% of the identity signal:
  $$S_{\text{base}} = S_{\text{visual}}$$

The transit score acts as an gating multiplier:
$$S_{\text{composite}} = S_{\text{base}} \times S_{\text{transit}}$$
A match is confirmed when $S_{\text{composite}} \ge 0.65$ and `clone_flag` is false.

### 5. Cloned Plate Alert (`clone_flag`)
Returns `True` when plate texts match near-identically ($S_{\text{plate}} \ge 0.88$) but visual embeddings differ significantly ($S_{\text{visual}} < 0.60$), flagging vehicle plate tampering or cloning.

## Embedding Sanity Check Output

Output from `python backend/pipeline/test_embed.py`:

```
================================================================================
        OPENCLIP VEHICLE EMBEDDING SANITY CHECK (STAGE 4)
================================================================================
Loading detector and embedder...

Extracting vehicle crops:
  - White Car (CAM_01 f50) crop shape:  (196, 478, 3)
  - White Car (CAM_01 f100) crop shape: (199, 478, 3)
  - White Car (CAM_03 f75) crop shape:  (202, 478, 3)
  - Blue Coupe (CAM_02 f75) crop shape: (216, 480, 3)
  - Blue Coupe (CAM_04 f75) crop shape: (217, 480, 3)

Computing embeddings...

[PASS] Fixed output embedding dimension: 512-D (ViT-B-32)

================================================================================
                    COSINE SIMILARITY COMPARISONS
================================================================================
  Same Vehicle (Intra-camera, f50 vs f100):     0.9861
  Same Vehicle (Cross-camera CAM_01 vs CAM_03): 0.7569
  Same Vehicle (Cross-camera CAM_02 vs CAM_04): 0.8154
  Different Vehicles (CAM_01 White vs CAM_02 Blue): 0.5228
  Different Vehicles (CAM_03 White vs CAM_04 Blue): 0.4452
--------------------------------------------------------------------------------
Separation Margin (Min Same - Max Diff): +0.2341

[PASS] Same-vehicle appearance similarity is clearly higher than different-vehicle similarity.
================================================================================
```

## Matching Evaluation Output

Output from `python backend/pipeline/test_match.py`:

```
==========================================================================================
          MULTI-MODAL IDENTITY FUSION TEST SUITE (STAGE 4)
==========================================================================================
Loading pipeline models...
Models loaded successfully.

Extracting multi-camera sightings across all 8 clips:
  [CAM_01] EVR Salai - Central Station North Gate | Plate: TN 07 AB 1234  | Emb: 512D
  [CAM_02] EVR Salai - Periamet Signal            | Plate: MH 12 CD 5678  | Emb: 512D
  [CAM_03] EVR Salai - Vepery High Road Junction  | Plate: DL 01 EF 9012  | Emb: 512D
  [CAM_04] Anna Salai - Pallavan Salai Junction   | Plate: KA 05 GH 3456  | Emb: 512D
  [CAM_05] Anna Salai - Chintadripet Junction     | Plate: KL 07 JK 7890  | Emb: 512D
  [CAM_06] Anna Salai - Thousand Lights LIC Junct | Plate: TS 09 LM 2345  | Emb: 512D
  [CAM_07] Rajaji Salai - Parrys Corner High Cour | Plate: UNCONFIRMED    | Emb: 512D
  [CAM_08] Rajaji Salai - Harbour Subway Underpas | Plate: UNCONFIRMED    | Emb: 512D

==========================================================================================
TEST A: TRAJECTORY CONTINUITY ACROSS ADVERSARIAL DEGRADED CAMERA (CAM_07)
==========================================================================================
Sighting A: CAM_04 (Plate: KA 05 GH 3456, Conf: 0.8071)
Sighting B: CAM_07 (Plate: None, Unconfirmed: True)
------------------------------------------------------------------------------------------
  Plate Score (fuzzy text):           0.0000  (Plate unconfirmed on CAM_07)
  Visual Score (OpenCLIP cosine):     0.7164  (Appearance carries identity)
  Transit Score (distance/speed):     1.0000  (1.944 km in 540.0s)
  Matching Regime:                    VISUAL_REID_DOMINATED
  Composite Identity Score:           0.7164
  Trajectory Match Decision:          CONFIRMED MATCH
[PASS] Trajectory survived unreadable plate via OpenCLIP visual appearance fallback.

==========================================================================================
TEST B: CLONED PLATE DETECTION (IDENTICAL PLATE TEXT, DIFFERENT VEHICLE)
==========================================================================================
Vehicle A (Original): CAM_01 White Sedan (Plate: TN 07 AB 1234)
Vehicle B (Clone):    CAM_CLONE Blue Coupe (Plate: TN 07 AB 1234)
------------------------------------------------------------------------------------------
  Plate Score:                        1.0000 (Near-exact match)
  Visual Score:                       0.5281 (Visually disparate vehicles)
  Clone Detection Flag:               True
  Composite Decision:                 BLOCKED AS CLONE
[PASS] Cloned plate successfully detected and blocked from erroneous trajectory merging.

==========================================================================================
TEST C: SPATIO-TEMPORAL TRANSIT PLAUSIBILITY GATING
==========================================================================================
Trip: CAM_01 -> CAM_FAR (28.993 km in 30.0s)
  Implied Speed:                      3479.1 km/h
  Transit Plausibility Score:         0.0000
  Composite Score:                    0.0000 (Pulled down by transit gate)
  Match Decision:                     REJECTED (IMPLAUSIBLE)
[PASS] Spatio-temporal transit gate rejected physically implausible trajectory hop.
==========================================================================================
```
