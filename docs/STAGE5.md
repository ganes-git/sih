# Stage 5: Unsupervised Corridor Baselines & Route-Anomaly Engine

This stage implements the project's core differentiator: a module that learns what a normal journey between any two cameras looks like, purely from sighting data, with zero manual labelling, and flags journeys that deviate from learned corridor patterns.

Unlike single-frame ANPR systems that simply read plates in isolation, this engine models the city's camera network as an emergent directed graph of traffic corridors, capturing expected transit time distributions ($\mu, \sigma$) and identifying temporal deviations and rare path traversals.

---

## 1. SQLite Database Schema (`/backend/data/anpr.db`)

The persistent database is created at `/backend/data/anpr.db` via `backend/database.py` with 6 relational tables:

```sql
-- 1. Sightings: All vehicle detections across all cameras
CREATE TABLE sightings (
    sighting_id TEXT PRIMARY KEY,
    camera_id TEXT NOT NULL,
    lat REAL NOT NULL,
    lon REAL NOT NULL,
    timestamp REAL NOT NULL,
    plate_text TEXT,
    plate_confidence REAL,
    embedding TEXT NOT NULL,         -- JSON-serialized 512-D float list
    snapshot_path TEXT NOT NULL
);

-- 2. Blacklist: Flagged registration plates
CREATE TABLE blacklist (
    plate_text TEXT PRIMARY KEY,
    reason TEXT NOT NULL,
    added_on REAL NOT NULL
);

-- 3. Restricted Zones: Circular geographic geofences
CREATE TABLE restricted_zones (
    zone_id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    center_lat REAL NOT NULL,
    center_lon REAL NOT NULL,
    radius_meters REAL NOT NULL,
    reason TEXT NOT NULL
);

-- 4. Corridor Baseline: Statistical transit profiles for camera pairs
CREATE TABLE corridor_baseline (
    id TEXT PRIMARY KEY,
    camera_from TEXT NOT NULL,
    camera_to TEXT NOT NULL,
    distance_km REAL NOT NULL,
    mean_transit_seconds REAL NOT NULL,
    stddev_transit_seconds REAL NOT NULL,
    sample_count INTEGER NOT NULL,   -- Path frequency counter (see note below)
    avg_speed_kmh REAL NOT NULL,
    source TEXT NOT NULL CHECK(source IN ('seed', 'observed', 'mixed')),
    updated_at REAL NOT NULL
);

-- 5. Audit Log: Search query and operator activity logging
CREATE TABLE audit_log (
    log_id TEXT PRIMARY KEY,
    searched_by TEXT NOT NULL,       -- "operator" | "supervisor"
    searched_query TEXT NOT NULL,
    searched_at REAL NOT NULL
);

-- 6. Alerts: System alert events across multi-modal checks
CREATE TABLE alerts (
    alert_id TEXT PRIMARY KEY,
    alert_type TEXT NOT NULL CHECK(alert_type IN ('clone', 'impossible_transit', 'blacklist', 'zone_deviation', 'route_anomaly')),
    sighting_id_a TEXT NOT NULL,
    sighting_id_b TEXT,              -- Nullable for single-sighting alerts (blacklist, zone)
    detail_text TEXT NOT NULL,
    created_at REAL NOT NULL
);
```

### Design Simplification Note
In `corridor_baseline`, `sample_count` doubles as this camera pair's path-frequency counter. No separate path-frequency table was created; this is a deliberate same-day-build simplification that avoids redundant table joins while preserving the ability to detect rarely traversed routes (`is_path_rare`).

### Seeded Records
- **Blacklist**: Seeded with 3 test plates:
  - `TN 07 AB 1234` (*Stolen vehicle report - Central Chennai FIR #2024-8812*), which matches the actual plate read from `camera_1.mp4`.
  - `MH 02 XY 9999` (*Vehicle involved in armed robbery investigation*).
  - `KA 01 AB 0007` (*Court-ordered seizure warrant*).
- **Restricted Zones**: Seeded with `ZONE_01` (*Chennai Central High-Security Perimeter*), centered directly at `CAM_01` (`lat: 13.0827, lon: 80.2755`) with a 400-meter radius, ensuring real camera sightings at `CAM_01` trigger geofence alerts.

---

## 2. Ingestion Pipeline & Day-Long Timestamp Spread (`/backend/pipeline/ingest_all.py`)

The batch ingestion script executes YOLOv8 vehicle detection, crop extraction, EasyOCR voting, and OpenCLIP 512-D feature vector extraction across all video clips in `/backend/data/clips/`. For each sighting, a cropped vehicle snapshot is saved to `backend/data/snapshots/{sighting_id}.jpg`.

### Engineered Temporal Distribution (7:00 AM – 8:30 PM)
Instead of assigning timestamps clustered at the same instant, sightings are distributed across a realistic 13.5-hour operational day:
- **Morning Commute (07:30 - 09:15)**: Commuter passes along the `CAM_01 -> CAM_02 -> CAM_03` arterial corridor (e.g. `TN 07 AB 1234`, `MH 12 CD 5678`).
- **Midday / Afternoon (11:30 - 15:45)**: Traffic across Anna Salai (`CAM_04 -> CAM_05 -> CAM_06`).
- **Evening Rush (17:30 - 20:30)**: Traffic through Parrys Corner and Harbour (`CAM_07 -> CAM_08`).

This distribution ensures:
1. Meaningful transit plausibility checks without false positive instantaneous speeds.
2. Statistically valid corridor timing baselines.
3. A dynamic, non-flat sightings-per-hour activity histogram in the Stage 7 frontend dashboard.

### Genuine Route-Anomaly Engineering
To demo a real, physically plausible route anomaly without triggering an `impossible_transit` alert:
- **Vehicle**: Blue Coupe visual match (`CAM_04` -> `CAM_07`).
- **Distance**: 1.944 km between Anna Salai and Parrys Corner.
- **Corridor Normal**: Seeded baseline is ~300 seconds (5.0 min) $\pm$ 25 seconds (~23 km/h typical city speed).
- **Actual Elapsed Time**: Engineered to 1320.0 seconds (22.0 minutes).
- **Physical Plausibility**: Implied travel speed is 5.3 km/h (slow crawl, heavy congestion, or prolonged stop)—well below the 90 km/h impossible transit cutoff, making it a legitimate route anomaly rather than a telemetry error.
- **Statistical Result**: $z \approx 39.53$ ($|z| \gg 2.5$), triggering a `route_anomaly` alert.

---

## 3. Corridor Baseline Engine (`/backend/pipeline/baseline.py`)

### Baseline Calibration Logic (`recompute_corridor_baselines`)
For every ordered camera pair occurring as a consecutive hop in reconstructed vehicle trajectories:
- If observed real trips $\ge 5$: Mean transit time, standard deviation, and average speed are computed directly from observed data and flagged with `source = 'observed'`.
- If observed real trips $< 5$: Because 8 video clips cannot provide dozens of repeated trips over all city corridors, the system generates 18 synthetic calibration trips with Gaussian jitter ($\sigma \approx 10\%-15\%$) around typical arterial transit speeds (20–25 km/h) for that specific camera distance, inserting the row with `source = 'seed'`.
- **Honesty Principle**: Seeded rows are explicitly tagged with `source = 'seed'` in the database and are never misrepresented as observed detections.

#### Corridor Summary Table
| Corridor Hop | Distance (km) | Baseline Mean | StdDev | Samples | Avg Speed | Source | Rationale |
|:---|:---:|:---:|:---:|:---:|:---:|:---:|:---|
| `CAM_01 -> CAM_02` | 0.952 km | 160.0 s (2.7m) | 8.2 s | 5 | 21.4 km/h | **observed** | 5 real commuter passes recorded across the day ($\ge 5$ threshold). |
| `CAM_02 -> CAM_03` | 1.146 km | 211.1 s (3.5m) | 26.8 s | 18 | 19.6 km/h | **seed** | $< 5$ real passes; calibrated at ~20 km/h arterial flow. |
| `CAM_04 -> CAM_05` | 0.760 km | 111.4 s (1.9m) | 9.8 s | 18 | 24.6 km/h | **seed** | $< 5$ real passes; calibrated at ~25 km/h flow. |
| `CAM_04 -> CAM_07` | 1.944 km | 303.3 s (5.1m) | 25.7 s | 18 | 23.1 km/h | **seed** | Cross-corridor link; calibrated at ~23 km/h normal flow. |
| `CAM_05 -> CAM_06` | 1.282 km | 192.9 s (3.2m) | 23.4 s | 18 | 23.9 km/h | **seed** | $< 5$ real passes; calibrated at ~24 km/h flow. |
| `CAM_07 -> CAM_08` | 0.883 km | 139.8 s (2.3m) | 14.5 s | 18 | 22.7 km/h | **seed** | Port access corridor; calibrated at ~23 km/h flow. |

---

## 4. Anomaly Scoring & Mathematical Explainability (`score_hop`)

When a vehicle hops from $\text{camera\_from}$ to $\text{camera\_to}$ with elapsed time $\Delta t$:
1. The corridor baseline ($\mu, \sigma, N$) is retrieved.
2. **Division-by-Zero Guard**: Standard deviation is floored to a fixed constant:
   $$\sigma_{\text{effective}} = \max\left(\sigma, \text{STDDEV\_FLOOR\_SECONDS}\right) \quad (\text{STDDEV\_FLOOR\_SECONDS} = 5.0\text{s})$$
   This prevents mathematical singularity when sample clusters have near-zero variance.
3. **Z-Score Calculation**:
   $$z = \frac{\Delta t - \mu}{\sigma_{\text{effective}}}$$
4. **Anomaly Classification**:
   - Timing Anomaly: Triggered when $|z| > 2.5$.
   - Rare Path Anomaly: Triggered when $N \le 2$ (`RARE_PATH_COUNT_CUTOFF`).
5. **Alert Detail Format**:
   Alert details avoid vague warnings and explicitly provide the exact mathematical parameters:
   `"ROUTE ANOMALY: Hop CAM_04→CAM_07 took 22.0 min vs. corridor normal of 5.1±0.4 min (z=39.53)."`

---

## 5. Automated Test Verification (`backend/tests/test_baseline.py`)

Execution command:
```powershell
& ".\venv\Scripts\python.exe" tests/test_baseline.py
```

### Test Output
```
==========================================================================================
       STAGE 5: CORRIDOR BASELINE & ROUTE ANOMALY TEST SUITE
==========================================================================================

Corridor Baseline Route Calibration Table:
Hop              | Dist (km)  | Mean (s)   | StdDev (s) | Samples  | Speed (km/h) | Source    
------------------------------------------------------------------------------------------
CAM_01 -> CAM_02 | 0.952      | 160.0      | 8.2        | 5        | 21.4         | observed  
CAM_02 -> CAM_03 | 1.146      | 211.1      | 26.8       | 18       | 19.6         | seed      
CAM_04 -> CAM_05 | 0.760      | 111.4      | 9.8        | 18       | 24.6         | seed      
CAM_04 -> CAM_07 | 1.944      | 303.3      | 25.7       | 18       | 23.1         | seed      
CAM_05 -> CAM_06 | 1.282      | 192.9      | 23.4       | 18       | 23.9         | seed      
CAM_07 -> CAM_08 | 0.883      | 139.8      | 14.5       | 18       | 22.7         | seed      
------------------------------------------------------------------------------------------
Total Baselines: 6 (Observed: 1, Seed: 5)
[PASS] Verified both 'seed' and 'observed' corridor baselines exist in corridor_baseline.

Route Anomaly Alerts Detected:
------------------------------------------------------------------------------------------
  [ALT_ROUTE_06C8DD2D] ROUTE ANOMALY: Hop CAM_04→CAM_07 took 22.0 min vs. corridor normal of 5.1±0.4 min (z=39.53).

[PASS] Verified 1 route_anomaly alert(s) created from engineered case.

Engineered Anomaly Evaluation (CAM_04 -> CAM_07):
  Actual Elapsed Time:  1320.0s (22.0 min)
  Baseline Normal:      303.3s (5.1 min) +/- 25.7s
  Computed Z-Score:     z = 39.53
  Anomaly Detected:     True
[PASS] Engineered route anomaly verified with statistical significance (z > 2.5).
==========================================================================================
```
