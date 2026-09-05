# Stage 6: FastAPI REST API & Multi-Modal Verification

This stage exposes the multi-modal detection, identity fusion, corridor baseline, and anomaly scanning logic built in Stages 3–5 through a high-performance REST API built with FastAPI.

No new ML, matching, or anomaly logic was created here; this stage strictly surfaces the existing capabilities over HTTP.

---

## 1. REST API Architecture

The service is defined in [`backend/main.py`](file:///C:/Users/ganes/.gemini/antigravity-ide/scratch/city-camera-network/backend/main.py) with CORS enabled for all origins (`*`) and static mounting of vehicle snapshot images at `/snapshots/`.

### Endpoints Overview

| Method | Path | Description | Role / Audit Behavior |
|:---|:---|:---|:---|
| `GET` | `/api/health` | Service health probe and version status | Public |
| `GET` | `/api/trajectory` | Multi-camera vehicle trajectory reconstruction with component scores ($S_{\text{plate}}, S_{\text{visual}}, S_{\text{transit}}, S_{\text{composite}}$) and corridor baseline metrics ($z$-score, $P_{\text{rare}}$) | Logs to `audit_log` with role (`operator` / `supervisor`) |
| `GET` | `/api/heatmap` | Sighting counts grouped by camera location with GPS coordinates | Public |
| `GET` | `/api/zones` | List of circular high-security restricted geofences and radiuses | Public |
| `GET` | `/api/corridor-baseline` | Corridor transit profiles including mean time, standard deviation, sample frequency, and average speed in km/h | Public |
| `GET` | `/api/traffic-trend` | 24-hour activity distribution for hourly sightings chart | Public |
| `GET` | `/api/blacklist/check` | Fuzzy Levenshtein lookup against flagged registration plates | Logs to `audit_log` with role (`operator` / `supervisor`) |
| `GET` | `/api/alerts` | Chronological feed of all generated alerts (most recent first) | Public |
| `POST` | `/api/alerts/scan` | Re-executes multi-modal alert checks (clones, impossible transit, zones, blacklist, route anomalies) | Public |
| `GET` | `/api/audit-log` | Search operation history with timestamp, query, and operator role | Public |

### Architectural Design Choice: Consolidated Corridor Baseline Endpoint
`GET /api/corridor-baseline` returns the full transit profile for each corridor hop, including `avg_speed_kmh` computed directly per row ($\frac{\text{distance\_km}}{\text{mean\_transit\_seconds} / 3600}$). This single endpoint deliberately consolidates both the average-speed-per-corridor and the traffic-pattern requirements rather than splitting them into separate routes, since the underlying data lives entirely within `corridor_baseline`.

---

## 2. Live HTTP Verification & Example Responses

All responses below were captured directly from the live FastAPI daemon running on `http://127.0.0.1:8000`.

### A. Trajectory Reconstruction with Route Anomaly
**Request**:
```http
GET /api/trajectory?query=KA%2005%20GH%203456&role=operator
```

**Response**:
```json
{
  "query": "KA 05 GH 3456",
  "role": "operator",
  "match_count": 2,
  "sightings": [
    {
      "sighting_id": "SGT_CAM_04_CLIP",
      "camera_id": "CAM_04",
      "camera_name": "Anna Salai - Pallavan Salai Junction",
      "corridor": "Anna Salai (Mount Road)",
      "lat": 13.0762,
      "lon": 80.2738,
      "timestamp": 1757052000.0,
      "timestamp_iso": "2025-09-05T11:30:00",
      "plate_text": "KA 05 GH 3456",
      "plate_confidence": 0.8071,
      "snapshot_path": "data/snapshots/snapshot_CAM_04.jpg",
      "snapshot_url": "/snapshots/snapshot_CAM_04.jpg",
      "hop": {
        "to_sighting_id": "SGT_CAM_07_CLIP",
        "to_camera_id": "CAM_07",
        "elapsed_seconds": 1320.0,
        "elapsed_minutes": 22.0,
        "distance_km": 1.944,
        "speed_kmh": 5.3,
        "plate_score": 0.0,
        "visual_score": 0.7164,
        "transit_score": 1.0,
        "composite_score": 0.7164,
        "timing_anomaly_score": 43.47,
        "is_path_rare": false,
        "is_timing_anomaly": true,
        "corridor_mean_seconds": 314.08,
        "corridor_stddev_seconds": 23.14
      }
    },
    {
      "sighting_id": "SGT_CAM_07_CLIP",
      "camera_id": "CAM_07",
      "camera_name": "Rajaji Salai - Parrys Corner High Court Junction",
      "corridor": "Rajaji Salai (Port Corridor)",
      "lat": 13.0892,
      "lon": 80.2858,
      "timestamp": 1757053320.0,
      "timestamp_iso": "2025-09-05T11:52:00",
      "plate_text": null,
      "plate_confidence": null,
      "snapshot_path": "data/snapshots/snapshot_CAM_07.jpg",
      "snapshot_url": "/snapshots/snapshot_CAM_07.jpg",
      "hop": null
    }
  ]
}
```
*Verification*: Demonstrates multi-sighting trajectory continuity across an adversarial camera (`CAM_07`), component score breakdowns, and the engineered route anomaly ($z = 43.47$).

---

### B. Multi-Modal Alerts Feed
**Request**:
```http
GET /api/alerts
```

**Response (Sample showing clone, zone_deviation, and route_anomaly)**:
```json
[
  {
    "alert_id": "ALT_ROUTE_EDC1E500",
    "alert_type": "route_anomaly",
    "sighting_id_a": "SGT_CAM_04_CLIP",
    "sighting_id_b": "SGT_CAM_07_CLIP",
    "detail_text": "ROUTE ANOMALY: Hop CAM_04→CAM_07 took 22.0 min vs. corridor normal of 5.2±0.4 min (z=43.47).",
    "created_at": 1788616797.8078043,
    "created_at_iso": "2026-09-05T19:29:57.807804"
  },
  {
    "alert_id": "ALT_CLONE_800D2733",
    "alert_type": "clone",
    "sighting_id_a": "SGT_C1_PASS_1",
    "sighting_id_b": "SGT_C2_PASS_1",
    "detail_text": "CLONED PLATE ALERT: Identical/similar plate 'TN 07 AB 1000' / 'TN 07 AB 1000' observed on visually disparate vehicles between CAM_01 and CAM_02 (visual similarity 0.53 < 0.60).",
    "created_at": 1788616797.798629,
    "created_at_iso": "2026-09-05T19:29:57.798629"
  },
  {
    "alert_id": "ALT_ZONE_0FD89E7A",
    "alert_type": "zone_deviation",
    "sighting_id_a": "SGT_C1_PASS_1",
    "sighting_id_b": null,
    "detail_text": "ZONE DEVIATION: Sighting at CAM_01 (0.0m from center) intruded into restricted zone 'Central Station Security Perimeter' (limit: 400m). Reason: High-security railway terminus perimeter; restricted commercial transport access",
    "created_at": 1788616797.798629,
    "created_at_iso": "2026-09-05T19:29:57.798629"
  },
  {
    "alert_id": "ALT_BL_9D6E49A2",
    "alert_type": "blacklist",
    "sighting_id_a": "SGT_CAM_01_CLIP",
    "sighting_id_b": null,
    "detail_text": "BLACKLIST ALERT: Vehicle 'TN 07 AB 1234' detected at camera CAM_01. Reason: Flagged in hit-and-run investigation #CR-8821 (Chennai Central Traffic)",
    "created_at": 1788616797.798629,
    "created_at_iso": "2026-09-05T19:29:57.798629"
  }
]
```
*Verification*: Confirms that `clone`, `zone_deviation`, and `route_anomaly` alert types are all present and populated with plain mathematical and situational detail.

---

### C. Corridor Baselines with Speeds
**Request**:
```http
GET /api/corridor-baseline
```

**Response**:
```json
[
  {
    "id": "BASE_CAM_01_CAM_02",
    "camera_from": "CAM_01",
    "camera_to": "CAM_02",
    "distance_km": 0.952,
    "mean_transit_seconds": 160.0,
    "mean_transit_minutes": 2.7,
    "stddev_transit_seconds": 8.2,
    "sample_count": 5,
    "avg_speed_kmh": 21.4,
    "source": "observed",
    "updated_at": 1788616550.4676933
  },
  {
    "id": "BASE_CAM_02_CAM_03",
    "camera_from": "CAM_02",
    "camera_to": "CAM_03",
    "distance_km": 1.146,
    "mean_transit_seconds": 211.2,
    "mean_transit_minutes": 3.5,
    "stddev_transit_seconds": 26.6,
    "sample_count": 18,
    "avg_speed_kmh": 19.5,
    "source": "seed",
    "updated_at": 1788616550.4676933
  },
  {
    "id": "BASE_CAM_04_CAM_05",
    "camera_from": "CAM_04",
    "camera_to": "CAM_05",
    "distance_km": 0.76,
    "mean_transit_seconds": 114.0,
    "mean_transit_minutes": 1.9,
    "stddev_transit_seconds": 13.5,
    "sample_count": 18,
    "avg_speed_kmh": 24.0,
    "source": "seed",
    "updated_at": 1788616550.4676933
  },
  {
    "id": "BASE_CAM_04_CAM_07",
    "camera_from": "CAM_04",
    "camera_to": "CAM_07",
    "distance_km": 1.944,
    "mean_transit_seconds": 314.1,
    "mean_transit_minutes": 5.2,
    "stddev_transit_seconds": 23.1,
    "sample_count": 18,
    "avg_speed_kmh": 22.3,
    "source": "seed",
    "updated_at": 1788616550.4676933
  },
  {
    "id": "BASE_CAM_05_CAM_06",
    "camera_from": "CAM_05",
    "camera_to": "CAM_06",
    "distance_km": 1.282,
    "mean_transit_seconds": 188.0,
    "mean_transit_minutes": 3.1,
    "stddev_transit_seconds": 28.1,
    "sample_count": 18,
    "avg_speed_kmh": 24.5,
    "source": "seed",
    "updated_at": 1788616550.4676933
  },
  {
    "id": "BASE_CAM_07_CAM_08",
    "camera_from": "CAM_07",
    "camera_to": "CAM_08",
    "distance_km": 0.883,
    "mean_transit_seconds": 148.8,
    "mean_transit_minutes": 2.5,
    "stddev_transit_seconds": 15.1,
    "sample_count": 18,
    "avg_speed_kmh": 21.4,
    "source": "seed",
    "updated_at": 1788616550.4676933
  }
]
```
*Verification*: `avg_speed_kmh` is computed and present on each row, correctly differentiating `observed` vs `seed` baseline sources.

---

## 3. Automated Test Suite Output (`backend/tests/test_api.py`)

Executed with:
```powershell
& ".\venv\Scripts\python.exe" tests/test_api.py
```

```
==========================================================================================
         STAGE 6: FASTAPI REST ENDPOINTS VERIFICATION SUITE
==========================================================================================
[PASS] GET /api/health -> 200 OK
[PASS] POST /api/alerts/scan -> 200 OK (16 alerts generated)
[PASS] GET /api/trajectory -> 200 OK (Reconstructed 2 hops with score breakdown & route_anomaly z=43.47)
[PASS] GET /api/heatmap -> 200 OK (8 cameras mapped)
[PASS] GET /api/zones -> 200 OK (1 zone(s) registered)
[PASS] GET /api/corridor-baseline -> 200 OK (6 routes with avg_speed_kmh computed)
[PASS] GET /api/traffic-trend -> 200 OK (24 hourly buckets, 19 total sightings)
[PASS] GET /api/blacklist/check -> 200 OK (Matched: TN 07 AB 1234 | Reason: Flagged in hit-and-run investigation #CR...)
[INFO] Alert types present in /api/alerts: {'zone_deviation', 'clone', 'blacklist', 'impossible_transit', 'route_anomaly'}
[PASS] GET /api/alerts -> 200 OK (16 alerts, confirmed 'clone', 'zone_deviation', and 'route_anomaly' are all present)
[PASS] GET /api/audit-log -> 200 OK (2 audit entries logged with operator/supervisor roles)
==========================================================================================
ALL 10 API ENDPOINTS VALIDATED SUCCESSFULLY (100% PASS)
==========================================================================================
```
