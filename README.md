# City Camera Network Tracker

A vehicle tracking and transit anomaly detection system that operates across fixed camera networks. The system matches vehicles between cameras using license plate OCR, visual embeddings, and transit timing constraints, while calculating statistical travel-time baselines between camera pairs to flag abnormal delays, detours, and watchlist matches.

## What It Does

- Detects vehicles in camera video feeds using YOLOv8 bounding boxes.
- Extracts license plate characters using EasyOCR sampled across detection frames.
- Generates 512-dimensional visual appearance embeddings with OpenCLIP (ViT-B/32) when plates are occluded, degraded, or unreadable.
- Reconstructs vehicle routes across multiple camera nodes using a composite score combining plate text similarity, visual appearance similarity, and physical transit feasibility.
- Computes mean transit times and standard deviations for observed camera hops to detect anomalous transit durations ($|z| > 2.5$).
- Flags impossible transits that exceed maximum physical road speeds between camera locations.
- Detects plate cloning when identical plate numbers appear at distant cameras in unfeasible time windows.
- Matches detected plates against a law enforcement blacklist using Levenshtein distance matching.
- Monitors vehicle presence inside geographic geofences and restricted zones.
- Serves an operator web interface with route mapping, density heatmaps, live video grid, blacklist lookup, and incident alert triage.

## Architecture

| Layer | Component | Function |
|:---|:---|:---|
| 1. Ingestion & Detection | YOLOv8 + EasyOCR | Vehicle bounding box localization and frame-level optical character recognition. |
| 2. Feature Extraction | OpenCLIP (ViT-B/32) | 512-dimensional normalized visual appearance vector extraction for vehicle Re-ID. |
| 3. Multi-Modal Matching | Fusion Scoring Engine | Composite scoring evaluating $S_{\text{composite}} = (0.65 \cdot S_{\text{plate}} + 0.35 \cdot S_{\text{visual}}) \cdot S_{\text{transit}}$ (with visual fallback when plate confidence $< 0.50$). |
| 4. Corridor Intelligence | Statistical Transit Engine | Camera-pair baseline modeling ($\mu, \sigma$) and z-score anomaly calculation ($z = \frac{\Delta t - \mu}{\sigma}$). |
| 5. Storage & Presentation | SQLite + FastAPI + Vanilla JS | Relational sighting storage, REST API endpoints, and a browser console without external charting dependencies. |

## API Reference

| Method | Endpoint | Purpose |
|:---|:---|:---|
| `GET` | `/api/health` | Health check returning service status. |
| `GET` | `/api/trajectory` | Reconstructs multi-hop trajectory with per-hop score breakdown and anomaly z-scores; records query in audit log. |
| `GET` | `/api/heatmap` | Camera coordinates and aggregated sighting counts for spatial density mapping. |
| `GET` | `/api/zones` | List of circular restricted zones, center coordinates, and radii in meters. |
| `GET` | `/api/corridor-baseline` | Statistical transit distributions ($\mu, \sigma$), sample counts, and average speeds between camera pairs. |
| `GET` | `/api/traffic-trend` | 24-hour activity distribution binned by hour. |
| `GET` | `/api/blacklist/check` | Fuzzy Levenshtein match against blacklisted plates; records search in audit log. |
| `GET` | `/api/alerts` | List of generated alerts (`clone`, `impossible_transit`, `blacklist`, `zone_deviation`, `route_anomaly`). |
| `POST` | `/api/alerts/scan` | Re-executes detection, matching, geofence, and route anomaly scans over the sighting database. |
| `GET` | `/api/audit-log` | Search history log containing queries, timestamps, and clearance roles. |
| `GET` | `/api/vehicles` | List of all distinct vehicle plates and identifiers observed across camera nodes. |
| `GET` | `/api/cameras` | List of all 8 camera nodes, GPS coordinates, and streaming clip routes. |

## Known Limitations

- **Seeded Baselines**: Six of the seven corridor routes rely on initial synthetic seed baselines due to limited historical observation volume.
- **Plate Localization**: License plate crops are approximated from the lower 40% of vehicle bounding boxes rather than a dedicated plate detector model.
- **OCR Accuracy**: Measured end-to-end OCR accuracy is 75.00% across the 8 benchmark test clips (100.00% exact match across 6 clear clips, 0.00% on 2 adversarial degraded clips).
- **Authentication**: The operator clearance toggle is an interface-level control without server-side cryptographic authentication or session management.
- **Static Demo**: The public GitHub Pages link serves frozen precomputed JSON fixtures; live video streaming and real-time database queries require running the FastAPI server locally.

## Live Demo

https://ganes-git.github.io/sih/

## Local Setup

```bash
git clone https://github.com/ganes-git/sih.git
cd sih
python -m venv backend/venv
backend/venv/Scripts/activate  # On Linux/macOS: source backend/venv/bin/activate
pip install -r backend/requirements.txt
python backend/generate_data.py
python backend/pipeline/ingest_all.py
python -m uvicorn backend.main:app --host 127.0.0.1 --port 8000
```
Open `http://127.0.0.1:8000` in a browser.
