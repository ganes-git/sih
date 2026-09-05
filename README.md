# City Camera Network Tracker

A vehicle surveillance and corridor intelligence system designed for automated vehicle re-identification, multi-camera trajectory reconstruction, and transit anomaly detection across municipal camera networks. The platform fuses optical character recognition (OCR), visual appearance embeddings, and spatio-temporal physics to maintain tracking continuity across degraded nodes while computing empirical corridor travel-time baselines to detect transit anomalies in real time.

---

## Live Demonstration

- **Interactive Operations Console**: [https://ganes-git.github.io/sih/](https://ganes-git.github.io/sih/)
- **Zero-Dependency Static Export**: Fully functional client-side demo with precomputed multi-hop trajectories, density heatmaps, blacklist verification, and video telemetry.

---

## Key Capabilities

- **Optical Character Recognition**: Localizes vehicle bounding boxes via YOLOv8 and performs multi-frame optical character voting using EasyOCR.
- **Visual Appearance Re-ID**: Extracts 512-dimensional visual feature vectors with OpenCLIP (ViT-B/32) to maintain tracking when license plates are degraded, occluded, or unreadable.
- **Multi-Modal Route Fusion**: Reconstructs multi-hop journeys by evaluating composite identity scores across plate text similarity, visual feature cosine similarity, and kinematic travel feasibility.
- **Corridor Transit Profiling**: Calculates statistical normal distributions ($\mu, \sigma$) across camera hops and flags transit anomalies exceeding standard statistical thresholds ($|z| > 2.5$).
- **Kinematic & Security Rule Engine**: Detects physically impossible transits (speed limit violations), license plate cloning (simultaneous sightings across distant nodes), and watchlist matches (fuzzy Levenshtein lookup).
- **Spatial Geofencing**: Monitors high-security perimeters and flags unauthorized vehicle entries inside restricted radii.
- **Operations Dashboard**: Real-time console providing synchronized video feed playback, interactive route mapping, sighting density heatmaps, and security audit logging.

---

## Pipeline Architecture

The system operates across a five-stage processing pipeline:

```
[Camera Stream / Video Input]
          │
          ▼
┌──────────────────────────────────────┐
│  1. Ingestion & Detection            │  YOLOv8 vehicle detection & bounding box localization
└──────────────────┬───────────────────┘
                   │
                   ▼
┌──────────────────────────────────────┐
│  2. Feature Extraction               │  Lower-third plate OCR (EasyOCR) + OpenCLIP (ViT-B/32) 512-D embeddings
└──────────────────┬───────────────────┘
                   │
                   ▼
┌──────────────────────────────────────┐
│  3. Multi-Modal Identity Matching    │  Composite score evaluation (S_plate, S_visual, S_transit)
└──────────────────┬───────────────────┘
                   │
                   ▼
┌──────────────────────────────────────┐
│  4. Corridor Statistical Profiling   │  Learned baseline distributions (μ, σ) & z-score anomaly detection
└──────────────────┬───────────────────┘
                   │
                   ▼
┌──────────────────────────────────────┐
│  5. API & Operations Interface       │  FastAPI service + Vanilla JS/Leaflet dashboard (0 external CSS/UI libs)
└──────────────────────────────────────┘
```

### Multi-Modal Scoring Formulation

Identity confirmation between sightings $A$ and $B$ is evaluated using the composite scoring function:

$$S_{\text{composite}} = (0.65 \cdot S_{\text{plate}} + 0.35 \cdot S_{\text{visual}}) \cdot S_{\text{transit}}$$

Where:
- $S_{\text{plate}} = 1 - \frac{\text{Levenshtein}(A, B)}{\max(\text{len}(A), \text{len}(B))}$
- $S_{\text{visual}} = \frac{\mathbf{v}_A \cdot \mathbf{v}_B}{\|\mathbf{v}_A\| \|\mathbf{v}_B\|}$ (cosine similarity of normalized OpenCLIP embeddings)
- $S_{\text{transit}} = \begin{cases} 1.0 & \text{if } v_{\text{transit}} \le v_{\text{max}} \\ 0.0 & \text{if } v_{\text{transit}} > v_{\text{max}} \end{cases}$

When plate confidence falls below $0.50$, the system transitions to visual feature tracking:

$$S_{\text{composite}} = S_{\text{visual}} \cdot S_{\text{transit}}$$

---

## REST API Reference

| Method | Endpoint | Description |
|:---|:---|:---|
| `GET` | `/api/health` | Service health status probe. |
| `GET` | `/api/trajectory` | Reconstructs multi-hop journey for a target plate, returning per-hop similarity scores and z-score anomaly metrics. |
| `GET` | `/api/heatmap` | Camera geographic coordinates and aggregated sighting density counts. |
| `GET` | `/api/zones` | Circular restricted zone geofences, center coordinates, and radii in meters. |
| `GET` | `/api/corridor-baseline` | Empirical corridor transit statistics ($\mu, \sigma$), sample counts, and average speeds (km/h). |
| `GET` | `/api/traffic-trend` | 24-hour activity distribution binned into hourly buckets. |
| `GET` | `/api/blacklist/check` | Fuzzy Levenshtein watchlist query against registered law enforcement watchlists. |
| `GET` | `/api/alerts` | Chronological feed of generated alerts (`clone`, `impossible_transit`, `blacklist`, `zone_deviation`, `route_anomaly`). |
| `POST` | `/api/alerts/scan` | Re-executes the complete anomaly detection suite across all sightings in the database. |
| `GET` | `/api/audit-log` | Search audit log entries with timestamps, queries, and clearance roles. |
| `GET` | `/api/vehicles` | List of all distinct vehicle plates and identifiers observed across camera nodes. |
| `GET` | `/api/cameras` | List of all 8 camera nodes, GPS coordinates, and streaming clip routes. |

---

## Known Limitations

- **Corridor Baseline Seeding**: Initial corridor travel-time baselines for six of the seven routes use synthetic seeds due to limited historical observation density.
- **Plate Bounding Approximation**: License plate crops are derived from the lower 40% of the vehicle bounding box rather than a dedicated secondary plate localization model.
- **OCR Character Accuracy**: Measured exact-match OCR accuracy is 75.00% across the 8 benchmark test sequences (100.00% across clean video clips, 0.00% across adversarial/degraded clips resolved via visual Re-ID).
- **Clearance Controls**: Operator and supervisor clearance modes are interface-level controls without backend token validation or role-based access control.
- **Static Export Scope**: The public GitHub Pages demonstration operates from precomputed JSON fixtures; live database updates and real-time video stream transcoding require running the FastAPI backend locally.

---

## Local Setup & Development

### Prerequisites

- Python 3.10+
- FFmpeg (for video processing and stream synthesis)

### Installation

```bash
# 1. Clone repository
git clone https://github.com/ganes-git/sih.git
cd sih

# 2. Configure virtual environment
python -m venv backend/venv
backend/venv/Scripts/activate  # Linux/macOS: source backend/venv/bin/activate

# 3. Install dependencies
pip install -r backend/requirements.txt

# 4. Initialize database and generate test data
python backend/generate_data.py
python backend/pipeline/ingest_all.py

# 5. Start development server
python -m uvicorn backend.main:app --host 127.0.0.1 --port 8000
```

Access the local operations console at `http://127.0.0.1:8000/`.
