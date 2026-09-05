# Stage 2: Virtual Camera Data and Ground Truth

This stage produces demo input clips, ground truth plate labels, and real-world camera coordinates for pipeline testing.

## Input Clip Generation

Synthetic clip generation was chosen using OpenCV. Eight 10-second 1280x720 MP4 video clips at 15 frames per second were generated in `backend/data/clips/` (`camera_1.mp4` through `camera_8.mp4`).

- Clips 1 to 6 render vehicles traversing asphalt road scenes with visible, high-contrast Indian-format license plates.
- Clip 7 is an adversarial clip with directional horizontal motion blur and physical plate occlusion across the central characters.
- Clip 8 is an adversarial clip with low-light illumination scaled to 12% and additive Gaussian sensor noise ($\sigma = 35$) simulating an unlit tunnel.

## Ground Truth Verification

Ground truth plate labels are recorded in `backend/data/ground_truth.json`. All 8 camera IDs are mapped:

| Camera ID | Clip File | True Plate String | Condition |
| :--- | :--- | :--- | :--- |
| CAM_01 | camera_1.mp4 | TN 07 AB 1234 | Normal daylight |
| CAM_02 | camera_2.mp4 | MH 12 CD 5678 | Normal daylight |
| CAM_03 | camera_3.mp4 | DL 01 EF 9012 | Normal daylight |
| CAM_04 | camera_4.mp4 | KA 05 GH 3456 | Normal daylight |
| CAM_05 | camera_5.mp4 | KL 07 JK 7890 | Normal daylight |
| CAM_06 | camera_6.mp4 | TS 09 LM 2345 | Normal daylight |
| CAM_07 | camera_7.mp4 | HR 26 PQ 6789 | Motion blur and occlusion |
| CAM_08 | camera_8.mp4 | UP 16 XY 4321 | Low light and sensor noise |

## Camera Coordinates

Camera coordinates are anchored to Chennai Central (`13.0827, 80.2707`) and saved to `backend/data/camera_metadata.json`. Positions are aligned to three real arterial road corridors with nearest-neighbor distances between 750m and 1.6km:

1. **Poonamallee High Road (EVR Salai) Westbound Corridor**:
   - `CAM_01` (13.0827, 80.2707): EVR Salai - Central Station North Gate
   - `CAM_02` (13.0815, 80.2620): EVR Salai - Periamet Signal (~950m W)
   - `CAM_03` (13.0802, 80.2515): EVR Salai - Vepery High Road Junction (~1.1km W)
2. **Anna Salai (Mount Road) South-West Corridor**:
   - `CAM_04` (13.0762, 80.2738): Anna Salai - Pallavan Salai Junction (~800m S)
   - `CAM_05` (13.0708, 80.2695): Anna Salai - Chintadripet Junction (~750m SW)
   - `CAM_06` (13.0615, 80.2625): Anna Salai - Thousand Lights LIC Junction (~1.3km SW)
3. **Rajaji Salai (Port Corridor) North Corridor**:
   - `CAM_07` (13.0892, 80.2858): Rajaji Salai - Parrys Corner High Court Junction (~1.6km NE)
   - `CAM_08` (13.0965, 80.2890): Rajaji Salai - Harbour Subway Underpass (~900m N)
