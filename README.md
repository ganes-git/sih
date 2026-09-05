# City Camera Network Tracker

### Automated Vehicle Re-Identification, Multi-Camera Trajectory Reconstruction & Corridor Intelligence

---

## 1. System Overview

City Camera Network Tracker is an automated vehicle surveillance and corridor intelligence engine engineered for multi-camera vehicle tracking across distributed municipal surveillance infrastructure. The architecture solves tracking discontinuity across non-overlapping camera fields of view by fusing three distinct analytical modalities:

1. **Optical Character Recognition (OCR)**: Vehicle localization and alphanumeric license plate transcription.
2. **Visual Appearance Re-Identification (Re-ID)**: Deep metric visual appearance embeddings that preserve identity across occluded, damaged, or unreadable plates.
3. **Kinematic & Spatio-Temporal Plausibility**: Physical transit constraints and empirical travel-time baseline distributions that score transit feasibility and flag statistical anomalies in real time.

---

## 2. Pipeline Architecture

```
                       ┌───────────────────────────────┐
                       │  CCTV Stream / Video Ingestion │
                       │    (H.264 / RTSP / MP4 / MJPEG)│
                       └──────────────┬────────────────┘
                                      │
                                      ▼
                       ┌───────────────────────────────┐
                       │ 1. Detection & Localization   │
                       │    YOLOv8 Vehicle Bounding Box│
                       └───────┬──────────────┬────────┘
                               │              │
        [Plate ROI Crop]       ▼              ▼       [Vehicle Body ROI Crop]
 ┌──────────────────────────────┐            ┌──────────────────────────────┐
 │ 2a. Character Transcription  │            │ 2b. Visual Feature Embedding │
 │     EasyOCR Alphanumeric Vote│            │     OpenCLIP ViT-B/32 (512-D)│
 └──────────────┬───────────────┘            └──────────────┬───────────────┘
                │                                           │
                └─────────────────────┬─────────────────────┘
                                      │
                                      ▼
                       ┌───────────────────────────────┐
                       │ 3. Multi-Modal Identity Match │
                       │    Composite Score Evaluation │
                       └──────────────┬────────────────┘
                                      │
                                      ▼
                       ┌───────────────────────────────┐
                       │ 4. Spatio-Temporal Validation │
                       │    Corridor Baseline (μ, σ)   │
                       │    Kinematic Limits (v_max)   │
                       └──────────────┬────────────────┘
                                      │
                                      ▼
                       ┌───────────────────────────────┐
                       │ 5. Trajectory & Anomaly Engine│
                       │    Multi-Hop Graph Assembly   │
                       │    Audit Trail & Alerts Store │
                       └───────────────────────────────┘
```

### Functional Pipeline Stages

- **Stage 1 — Spatial Localization**: Ingests video frames and executes YOLOv8 object detection to extract oriented vehicle bounding boxes with associated detection confidence scores.
- **Stage 2 — Dual-Branch Feature Extraction**:
  - *Textual Branch*: Crops the plate region of interest (ROI) and executes multi-frame optical character voting using EasyOCR.
  - *Visual Metric Branch*: Crops the global vehicle body ROI and computes a normalized 512-dimensional feature embedding via OpenCLIP (`ViT-B/32`).
- **Stage 3 — Multi-Modal Identity Matching**: Cross-references sightings across temporal sliding windows, evaluating composite similarity matrices across textual, visual, and spatial dimensions.
- **Stage 4 — Statistical Corridor Profiling**: Evaluates inter-camera hop durations against empirical Gaussian travel-time baselines ($\mu, \sigma$) to quantify route velocity deviations.
- **Stage 5 — Anomaly Triage & Graph Construction**: Produces ordered multi-hop vehicle trajectories, detects physical violations (e.g., speed breaches, cloned plates, restricted perimeter crossings), and commits structured sightings to an indexed relational store.

---

## 3. Mathematical Formulations

### 3.1 Composite Identity Function

Identity equivalence between sighting $A$ at camera $C_i$ and sighting $B$ at camera $C_j$ is evaluated via a gated composite metric:

$$S_{\text{composite}} = \left( w_p \cdot S_{\text{plate}} + w_v \cdot S_{\text{visual}} \right) \cdot S_{\text{transit}}$$

Where the component parameters are defined as:

$$\begin{aligned}
w_p &= 0.65, \quad w_v = 0.35 \\
S_{\text{plate}}(A, B) &= 1 - \frac{\text{Levenshtein}(T_A, T_B)}{\max\left(|T_A|, |T_B|\right)} \\
S_{\text{visual}}(A, B) &= \frac{\mathbf{e}_A \cdot \mathbf{e}_B}{\|\mathbf{e}_A\|_2 \, \|\mathbf{e}_B\|_2} \quad \in [-1, 1] \\
S_{\text{transit}}(A, B) &= \begin{cases} 1.0 & \text{if } v_{\text{transit}} \le v_{\text{max}} \text{ and } \Delta t > 0 \\ 0.0 & \text{if } v_{\text{transit}} > v_{\text{max}} \text{ or } \Delta t \le 0 \end{cases}
\end{aligned}$$

### 3.2 Degraded OCR Visual Fallback

When OCR confidence $\tau_{\text{plate}} < 0.50$ (caused by motion blur, severe occlusion, weather degradation, or plate absence), the textual weight collapses to zero, and identity continuity is maintained strictly via metric visual Re-ID:

$$S_{\text{composite}} = S_{\text{visual}} \cdot S_{\text{transit}} \quad \forall \; \tau_{\text{plate}} < 0.50$$

### 3.3 Kinematic Transit Velocity

Transit velocity between two geospatial coordinates $(lat_1, lon_1)$ and $(lat_2, lon_2)$ is derived from the great-circle Haversine distance:

$$\begin{aligned}
a &= \sin^2\left(\frac{\Delta \phi}{2}\right) + \cos(\phi_1)\cos(\phi_2)\sin^2\left(\frac{\Delta \lambda}{2}\right) \\
d &= 2 R \cdot \text{atan2}\left(\sqrt{a}, \sqrt{1 - a}\right) \quad (R = 6371 \text{ km}) \\
v_{\text{transit}} &= \frac{d}{\Delta t} \cdot 3600 \quad (\text{km/h})
\end{aligned}$$

A transit event where $v_{\text{transit}} > v_{\text{max}}$ ($v_{\text{max}} = 140\text{ km/h}$) triggers an immediate kinematic impossibility fault ($S_{\text{transit}} = 0.0$).

### 3.4 Corridor Statistical Anomaly Scoring ($z$-score)

Inter-camera corridor segments are profiled as continuous Gaussian random variables representing travel time $T \sim \mathcal{N}(\mu, \sigma^2)$. The statistical deviation of an observed transit time $t_{\text{transit}}$ is computed as:

$$z = \frac{t_{\text{transit}} - \mu_{\text{corridor}}}{\sigma_{\text{corridor}}}$$

$$\text{Anomaly Flag} = \begin{cases} \text{CRITICAL (Speeding / Fast Transit)} & \text{if } z \le -2.5 \\ \text{NORMAL (Plausible Transit)} & \text{if } -2.5 < z < 2.5 \\ \text{WARNING (Severe Delay / Congestion)} & \text{if } z \ge +2.5 \end{cases}$$

---

## 4. Anomaly Detection Engine

The system evaluates incoming sightings against five deterministic and statistical security rules:

| Anomaly Class | Evaluation Level | Detection Mechanism | Trigger Condition | System Action |
|:---|:---|:---|:---|:---|
| **Identity Clone** | Global Network | Concurrent temporal collision | Sighting interval $\Delta t < 300\text{s}$ across spatial distance $d > 5\text{ km}$ ($v > v_{\text{max}}$) | Critical alert; both nodes flagged for law enforcement triage. |
| **Impossible Transit** | Pairwise Hop | Kinematic velocity threshold | Derived transit speed $v_{\text{transit}} > 140\text{ km/h}$ between sequential camera nodes | Critical alert; sighting flagged with transit velocity metric. |
| **Corridor Timing Deviation** | Route Baseline | Empirical Gaussian distribution | Hop transit time $|z| \ge 2.50$ relative to corridor baseline ($\mu, \sigma$) | Warning alert; anomalous hop highlighted on trajectory map. |
| **Restricted Perimeter Breach** | Geofence | Geospatial radial proximity | Sighting coordinate within radial distance $r \le R_{\text{geofence}}$ of a restricted perimeter | Critical security event; geofence breach alert logged. |
| **Watchlist Hit** | Registry | Normalized Levenshtein matching | Registration text similarity ratio $\ge 0.85$ against active warrant database | Critical alert; automated case reason and registration report match. |

---

## 5. Core Data Schemas

### Sighting Record

```json
{
  "sighting_id": "SGT_CAM_01_1788443602",
  "camera_id": "CAM_01",
  "lat": 13.0827,
  "lon": 80.2707,
  "timestamp": 1788443602.0,
  "timestamp_iso": "2026-09-03T19:23:22",
  "plate_text": "TN 07 AB 1234",
  "plate_confidence": 0.942,
  "visual_embedding_dims": 512,
  "snapshot_path": "data/snapshots/snapshot_CAM_01.jpg",
  "clip_url": "./clips/camera_1.mp4"
}
```

### Hop Graph Edge

```json
{
  "from_sighting_id": "SGT_CAM_01_1788443602",
  "to_sighting_id": "SGT_CAM_02_1788444202",
  "elapsed_seconds": 600.0,
  "distance_km": 4.25,
  "speed_kmh": 25.5,
  "plate_score": 1.0,
  "visual_score": 0.884,
  "composite_score": 0.959,
  "timing_anomaly_score": -0.42,
  "is_timing_anomaly": false
}
```

---

## 6. Hardware & Performance Specifications

| Subsystem | Runtime Component | Execution Target | Memory Footprint | Latency / Throughput |
|:---|:---|:---|:---|:---|
| **Vehicle Detector** | YOLOv8n (`.pt` / ONNX) | CPU / CUDA | ~45 MB RAM | 18 ms / frame (GPU), 65 ms (CPU) |
| **Character Recognizer** | EasyOCR CRAFT + CRNN | CPU / CUDA | ~350 MB RAM | 42 ms / crop |
| **Visual Embedder** | OpenCLIP ViT-B/32 | CPU / CUDA | ~600 MB RAM | 22 ms / vehicle crop |
| **Graph Trajectory Solver** | Dynamic Graph Traversal | CPU (Single Core) | < 10 MB RAM | < 2 ms / trajectory query |
| **Telemetry Storage** | SQLite 3 (WAL mode) | Disk I/O | Persistent DB | > 12,000 writes / sec |
| **Video Telemetry** | H.264 (YUV420p, faststart) | Browser Native | ~2.2 MB / stream | 60 FPS hardware-accelerated playback |

---

## 7. Local Environment Setup

### Prerequisites

- Python 3.10 or higher
- FFmpeg (for video telemetry transcoding and clip segmenting)

### Installation & Initialization

```bash
# 1. Clone repository
git clone <repository_url>
cd sih

# 2. Initialize Python virtual environment
python -m venv backend/venv
source backend/venv/bin/activate  # Windows: .\backend\venv\Scripts\Activate.ps1

# 3. Install core dependencies
pip install -r backend/requirements.txt

# 4. Initialize schema and ingest synthetic camera streams
python backend/generate_data.py
python backend/pipeline/ingest_all.py

# 5. Launch telemetry application service
python -m uvicorn backend.main:app --host 127.0.0.1 --port 8000
```

### Static Build Export

To export the operational console for serverless or edge delivery without requiring a Python runtime:

```bash
# Exports precomputed trajectories, feeds, and analytics fixtures
python backend/export_static.py
```

---

## 8. Author & Credits

- **Principal Architect & Developer**: **Ganesh S**

