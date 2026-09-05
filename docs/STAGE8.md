# Stage 8: Local Full-Stack Verification, Live Feeds, & Operations Console

This stage verifies the end-to-end operation of the complete stack on localhost served from a single service and single port (FastAPI serving REST API at `/api/*` and mounting the static frontend at `/`).

---

## 1. Architecture & Key Features

- **Backend / Frontend Host**: FastAPI application running on `http://127.0.0.1:8000` via Uvicorn.
- **Single-Port Architecture**: `app.mount("/", StaticFiles(directory=FRONTEND_DIR, html=True))` handles both UI static assets and API routes.
- **Vehicle Selection Dropdown**: Dynamically populated dropdown (`GET /api/vehicles`) listing all 12 distinct tracked vehicles across the network with their sighting count and visited camera corridors. Selecting any plate immediately reconstructs and displays its multi-hop path on the map.
- **Live Camera Feeds View (Stage 4 & 5)**: Responsive grid displaying all 8 camera video feeds (`/clips/camera_1.mp4` ... `/clips/camera_8.mp4`, `GET /api/cameras`, `GET /api/stream/{camera_id}`) with 1080p @ 25fps video telemetry, corridor metadata, and direct "View on Map" links—requiring zero external API keys.
- **High-Visibility Trajectory Paths**: Dual-layer contrasting polylines (dark charcoal casing + forest green / amber route line) and custom numbered waypoint markers (`[1]`, `[2]`) with origin/destination tooltips and automatic map invalidation.
- **Real-Time KPI Metric Cards**: Summary statistics for identified vehicles, total transit distance, corridor routes, anomaly flags, critical incident queues, and live video telemetry.
- **Clear Operator vs. Supervisor Roles**:
  - **Operator Mode**: Focused live triage, trajectory re-ID, camera video monitoring, and incident tracking.
  - **Supervisor Mode (Level 3 Clearance)**: Unlocks security audit log trails, corridor baseline sensitivity calibration controls, blacklist management catalog, raw multi-modal fusion weight inspectors ($w_{\text{plate}}=0.65, w_{\text{visual}}=0.35$), and pipeline re-scan triggers.

---

## 2. Check Results

### CHECK 1 — Functional Walkthrough (Status: PASS)
Executed automated headless browser walkthrough exercising all views:

1. **Trajectory Search & Vehicle Dropdown**:
   - Query: `KA 05 GH 3456` (and dropdown populated with all 12 vehicles).
   - Results: Returned 2 sightings connecting `CAM_04` (Koyambedu) and `CAM_07` (Airport).
   - Multi-Modal Scores: Per-hop breakdown ($S_{\text{plate}}=1.000, S_{\text{visual}}=0.999, S_{\text{transit}}=1.000, S_{\text{composite}}=1.000$).
   - Anomaly Flag: Timing anomaly ($z = 33.86$) displayed with an amber badge `TIMING ANOMALY` in the hop table.
   - Map: Leaflet map rendered high-visibility numbered waypoints `[1]`, `[2]` and dual-layer polyline path with muted OSM greyscale tile filter.

2. **Live Camera Feeds View**:
   - Results: All 8 camera cards streaming 1080p video feeds (`camera_1.mp4` through `camera_8.mp4`) with live telemetry indicators, GPS coordinates, corridor tags, and sighting counts.

3. **Heatmap View**:
   - Results: Rendered 8 camera pins scaled by sighting density across Chennai coordinates.
   - Restricted Zone: `ZONE_01` (Secretariat Restricted Zone) rendered with a red dashed perimeter circle (`#B3262A`).

4. **Blacklist View**:
   - Match Test: `TN 07 AB 1234` returned a critical red card with reason `Flagged in hit-and-run investigation #CR-2024-881`, added timestamp, and similarity `1.0000`.
   - Non-Match Test: `DL 01 AA 0000` returned muted `No match for DL 01 AA 0000 in the blacklist.` with class `.no-match`.
   - Supervisor Mode: Displays full Blacklist Registry Management catalog.

5. **Alerts & Supervisor Audit Log View**:
   - Alerts Table: Displayed all 17 multi-modal alerts spanning `clone`, `blacklist`, `zone_deviation`, `impossible_transit`, and `route_anomaly`.
   - Role Gating: In `operator` mode, `#audit-log-section` remained hidden.
   - Role Toggle: Switching role to `supervisor` immediately rendered `#audit-log-section` populated with recorded search events from `/api/audit-log` and unlocked the force-rescan trigger.

6. **Traffic Trends View**:
   - Activity Chart: 24 DOM `<div>` bars dynamically sized by hourly counts, exhibiting non-flat distribution.
   - Corridor Baselines Table: Displayed all 7 corridor routes with computed `avg_speed_kmh` (e.g., `21.4 km/h` on CAM_01 $\rightarrow$ CAM_02), and seed rows rendered in muted styling (`.row-seed`).
   - Supervisor Mode: Displays Corridor Sensitivity Calibration controls.

---

### CHECK 2 — Design-Contract Audit (Status: PASS)
Ran `frontend/tools/slop_check.py` against all integrated HTML, CSS, and JS files.

**Checker Output:**
```
SLOP CHECK: 0 violations. All 11 frontend files are clean.
```
- Zero unauthorized color values (no blue/purple/indigo).
- Zero gradients, box shadows, backdrop filters, or non-compliant border radiuses ($> 4\text{px}$).
- Strict compliance with font stacks and copy tone.

---

### CHECK 3 — Evidence Capture (Status: PASS)
Captured high-resolution browser viewport screenshots saved into `/docs/screenshots/`:

1. `01_trajectory_search.png` (569.3 KB) — Trajectory search with vehicle dropdown, dual-layer path, numbered waypoints, and amber anomaly badge.
2. `06_live_camera_feeds.png` (122.0 KB) — Live Camera Feeds 8-node video streaming grid (1080p @ 25fps).
3. `02_heatmap_view.png` (571.3 KB) — Sighting density heatmap with dashed red restricted zone and camera nodes.
4. `03_blacklist_view.png` (84.4 KB) — Matched plate alert card + Supervisor Blacklist Management catalog.
5. `04_alerts_and_audit_log_supervisor.png` (174.9 KB) — Multi-modal alerts table + Supervisor audit log table.
6. `05_traffic_trends_and_baselines.png` (118.5 KB) — 24-hour DOM traffic trend chart + Corridor baselines table + Sensitivity panel.

---

## 3. Summary

All checks passed unconditionally. The system is fully operational on `http://127.0.0.1:8000/` and ready for Stage 9.
