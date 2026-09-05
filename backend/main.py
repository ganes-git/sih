"""
City Camera Network ANPR Service - FastAPI Application (Stage 6)
Exposes REST endpoints for vehicle trajectory queries, corridor baselines,
heatmaps, traffic trends, restricted zones, blacklist checking, audit logs, and alert scans.
"""

import os
import sys
import json
import time
import math
import uuid
import sqlite3
from datetime import datetime
from typing import Dict, Any, List, Optional

from fastapi import FastAPI, Query, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

BACKEND_DIR = os.path.dirname(os.path.abspath(__file__))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from database import get_db_connection, log_audit_event, SNAPSHOTS_DIR
from pipeline.match import (
    composite_score,
    plate_score,
    visual_score,
    transit_score,
    clean_plate_string,
    haversine_distance_km,
    CONFIRMATION_MATCH_THRESH,
)
from pipeline.baseline import score_hop, recompute_corridor_baselines
from pipeline.alerts import scan_and_repopulate_alerts

app = FastAPI(
    title="City Camera Network ANPR Service",
    description="Automated multi-modal vehicle re-identification, corridor baseline, and route anomaly detection API.",
    version="1.0.0",
)

# Enable CORS for all origins (per Stage 6 requirement)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Serve vehicle snapshot images statically
if os.path.exists(SNAPSHOTS_DIR):
    app.mount("/snapshots", StaticFiles(directory=SNAPSHOTS_DIR), name="snapshots")

# Serve camera video clips statically (Stage 4/5 requirement)
CLIPS_DIR = os.path.join(BACKEND_DIR, "data", "clips")
if os.path.exists(CLIPS_DIR):
    app.mount("/clips", StaticFiles(directory=CLIPS_DIR), name="clips")


# Load camera metadata helper
CAMERA_METADATA_PATH = os.path.join(BACKEND_DIR, "data", "camera_metadata.json")
CAMERA_METADATA = {}
if os.path.exists(CAMERA_METADATA_PATH):
    try:
        with open(CAMERA_METADATA_PATH, "r", encoding="utf-8") as f:
            CAMERA_METADATA = json.load(f)
    except Exception:
        CAMERA_METADATA = {}


def parse_timestamp_filter(val: Optional[str]) -> Optional[float]:
    """Parse date_from / date_to parameter into POSIX timestamp float."""
    if not val or not val.strip():
        return None
    val = val.strip()
    try:
        return float(val)
    except ValueError:
        pass
    # Try ISO formats
    for fmt in ("%Y-%m-%d", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S"):
        try:
            dt = datetime.strptime(val, fmt)
            return dt.timestamp()
        except ValueError:
            continue
    return None


# -----------------------------------------------------------------------------
# 1. Health Probe
# -----------------------------------------------------------------------------
@app.get("/api/health", summary="Health check")
def health_check():
    """Returns service health status, service name, and version."""
    return {
        "status": "ok",
        "service": "City Camera Network ANPR Service",
        "version": "1.0.0",
        "timestamp": time.time(),
    }


# -----------------------------------------------------------------------------
# 1B. Vehicles Registry & Camera Feed Endpoints (Stage 4/5)
# -----------------------------------------------------------------------------
@app.get("/api/vehicles", summary="List all distinct vehicles in database for quick search selection")
def get_vehicles():
    """Returns all tracked vehicle plate numbers, sighting counts, and camera locations."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT plate_text, COUNT(*) as sighting_count, GROUP_CONCAT(camera_id) as cameras,
               MIN(timestamp) as first_seen, MAX(timestamp) as last_seen
        FROM sightings
        WHERE plate_text IS NOT NULL AND plate_text != ''
        GROUP BY plate_text
        ORDER BY sighting_count DESC, plate_text ASC
    """)
    rows = cursor.fetchall()
    conn.close()

    vehicles = []
    for r in rows:
        cams = r["cameras"].split(",") if r["cameras"] else []
        vehicles.append({
            "plate_text": r["plate_text"],
            "sighting_count": r["sighting_count"],
            "cameras": list(dict.fromkeys(cams)),  # deduplicate
            "first_seen": r["first_seen"],
            "last_seen": r["last_seen"],
        })
    return vehicles


@app.get("/api/cameras", summary="List all 8 camera nodes with metadata and video feed URLs")
def get_cameras():
    """Returns camera nodes, coordinates, corridors, status, and video clip feed URLs."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT camera_id, COUNT(*) as sighting_count FROM sightings GROUP BY camera_id")
    counts = {r["camera_id"]: r["sighting_count"] for r in cursor.fetchall()}
    conn.close()

    cameras = []
    for cam_id, meta in sorted(CAMERA_METADATA.items()):
        cam_num = cam_id.replace("CAM_", "")
        clip_name = f"camera_{int(cam_num)}.mp4" if cam_num.isdigit() else f"camera_1.mp4"
        cameras.append({
            "camera_id": cam_id,
            "label": meta.get("label", cam_id),
            "corridor": meta.get("corridor", "Arterial Road"),
            "lat": meta["lat"],
            "lon": meta["lon"],
            "sighting_count": counts.get(cam_id, 0),
            "clip_url": f"/clips/{clip_name}",
            "stream_url": f"/api/stream/{cam_id}",
            "status": "online",
            "fps": 25,
            "resolution": "1080p",
        })
    return cameras


@app.get("/api/stream/{camera_id}", summary="Stream camera video feed")
def stream_camera(camera_id: str):
    """Returns video clip URL or metadata for specified camera node."""
    cam_id = camera_id.upper()
    if cam_id not in CAMERA_METADATA:
        raise HTTPException(status_code=404, detail=f"Camera {camera_id} not found")
    cam_num = cam_id.replace("CAM_", "")
    clip_name = f"camera_{int(cam_num)}.mp4" if cam_num.isdigit() else "camera_1.mp4"
    clip_path = os.path.join(CLIPS_DIR, clip_name)
    if not os.path.exists(clip_path):
        raise HTTPException(status_code=404, detail=f"Video feed for {cam_id} not found")
    return {
        "camera_id": cam_id,
        "clip_url": f"/clips/{clip_name}",
        "status": "streaming",
        "fps": 25,
        "resolution": "1080p",
    }


# -----------------------------------------------------------------------------
# 2. Trajectory Reconstruction & Multi-Modal Matching
# -----------------------------------------------------------------------------
@app.get("/api/trajectory", summary="Reconstruct vehicle trajectory across cameras")
def get_trajectory(
    query: str = Query(..., description="License plate text or sighting_id to reconstruct"),
    date_from: Optional[str] = Query(None, description="Start date/time filter"),
    date_to: Optional[str] = Query(None, description="End date/time filter"),
    role: str = Query("operator", description="User role ('operator' or 'supervisor')"),
):
    """
    Reconstructs the multi-camera trajectory for a vehicle:
    - Fuses plate text, OpenCLIP appearance embeddings, and transit plausibility.
    - Resolves degraded / occluded plates via visual Re-ID.
    - Provides per-hop score breakdown (plate, visual, transit, composite).
    - Annotates corridor baseline metrics (z-score timing anomaly and path rarity).
    - Logs search operation to audit_log.
    """
    # Log audit event
    log_audit_event(searched_query=f"Trajectory query: {query}", searched_by=role)

    t_start = parse_timestamp_filter(date_from)
    t_end = parse_timestamp_filter(date_to)

    conn = get_db_connection()
    cursor = conn.cursor()

    # Query all sightings in optional time window
    time_conditions = []
    params = []
    if t_start is not None:
        time_conditions.append("timestamp >= ?")
        params.append(t_start)
    if t_end is not None:
        time_conditions.append("timestamp <= ?")
        params.append(t_end)

    where_clause = f"WHERE {' AND '.join(time_conditions)}" if time_conditions else ""
    cursor.execute(f"SELECT * FROM sightings {where_clause} ORDER BY timestamp ASC", params)
    all_rows = cursor.fetchall()
    conn.close()

    if not all_rows:
        return {"query": query, "role": role, "match_count": 0, "sightings": []}

    sightings = []
    for r in all_rows:
        s_dict = dict(r)
        try:
            s_dict["embedding"] = json.loads(r["embedding"])
        except Exception:
            s_dict["embedding"] = []
        s_dict["unconfirmed_plate"] = (
            r["plate_text"] is None
            or (r["plate_confidence"] is not None and r["plate_confidence"] < 0.50)
        )
        sightings.append(s_dict)

    # Find anchor sighting(s) matching query
    clean_q = clean_plate_string(query)
    anchor_sightings = []
    for s in sightings:
        if s["sighting_id"].upper() == query.strip().upper():
            anchor_sightings.append(s)
        elif s["plate_text"] and clean_plate_string(s["plate_text"]) == clean_q:
            anchor_sightings.append(s)

    if not anchor_sightings:
        # Fallback to fuzzy plate match on query
        best_anchor = None
        best_ratio = 0.0
        for s in sightings:
            if s["plate_text"]:
                ratio = plate_score(clean_q, s["plate_text"])
                if ratio > best_ratio:
                    best_ratio = ratio
                    best_anchor = s
        if best_anchor and best_ratio >= 0.85:
            anchor_sightings.append(best_anchor)

    if not anchor_sightings:
        return {
            "query": query,
            "role": role,
            "match_count": 0,
            "sightings": [],
            "message": "No vehicle sightings matching query found.",
        }

    # Use the primary anchor to match trajectory candidates across the network
    primary_anchor = anchor_sightings[0]
    matched_sightings = [primary_anchor]

    for candidate in sightings:
        if candidate["sighting_id"] == primary_anchor["sighting_id"]:
            continue

        # If identical plate string, verify it is not a clone
        if (
            primary_anchor["plate_text"]
            and candidate["plate_text"]
            and clean_plate_string(primary_anchor["plate_text"]) == clean_plate_string(candidate["plate_text"])
        ):
            c_eval = composite_score(primary_anchor, candidate)
            if not c_eval["clone_flag"]:
                matched_sightings.append(candidate)
        else:
            # Degraded plate or visual re-id matching
            c_eval = composite_score(primary_anchor, candidate)
            if c_eval["is_match"] and c_eval["composite_score"] >= CONFIRMATION_MATCH_THRESH:
                matched_sightings.append(candidate)

    # Sort matched sightings chronologically
    matched_sightings.sort(key=lambda x: x["timestamp"])

    # Build response with per-hop breakdown
    results = []
    for i in range(len(matched_sightings)):
        curr = matched_sightings[i]
        hop_info = None

        if i < len(matched_sightings) - 1:
            nxt = matched_sightings[i + 1]
            dt_sec = abs(nxt["timestamp"] - curr["timestamp"])
            dist_km = haversine_distance_km(curr["lat"], curr["lon"], nxt["lat"], nxt["lon"])
            speed_kmh = (dist_km / (dt_sec / 3600.0)) if dt_sec > 0 else 0.0

            # Match scores for hop
            c_eval = composite_score(curr, nxt)
            baseline_eval = score_hop(curr["camera_id"], nxt["camera_id"], dt_sec)

            hop_info = {
                "to_sighting_id": nxt["sighting_id"],
                "to_camera_id": nxt["camera_id"],
                "elapsed_seconds": round(dt_sec, 1),
                "elapsed_minutes": round(dt_sec / 60.0, 1),
                "distance_km": round(dist_km, 3),
                "speed_kmh": round(speed_kmh, 1),
                "plate_score": c_eval["plate_score"],
                "visual_score": c_eval["visual_score"],
                "transit_score": c_eval["transit_score"],
                "composite_score": c_eval["composite_score"],
                "timing_anomaly_score": baseline_eval["z_score"],
                "is_path_rare": baseline_eval["is_path_rare"],
                "is_timing_anomaly": baseline_eval["is_anomaly"],
                "corridor_mean_seconds": baseline_eval["mean_seconds"],
                "corridor_stddev_seconds": baseline_eval["stddev_seconds"],
            }

        cam_meta = CAMERA_METADATA.get(curr["camera_id"], {})
        snapshot_url = (
            f"/snapshots/{os.path.basename(curr['snapshot_path'])}"
            if curr.get("snapshot_path")
            else None
        )

        cam_num = curr["camera_id"].replace("CAM_", "")
        clip_name = f"camera_{int(cam_num)}.mp4" if cam_num.isdigit() else "camera_1.mp4"
        clip_url = f"/clips/{clip_name}"

        results.append({
            "sighting_id": curr["sighting_id"],
            "camera_id": curr["camera_id"],
            "camera_name": cam_meta.get("label", curr["camera_id"]),
            "corridor": cam_meta.get("corridor", "Urban Arterial"),
            "lat": curr["lat"],
            "lon": curr["lon"],
            "timestamp": curr["timestamp"],
            "timestamp_iso": datetime.fromtimestamp(curr["timestamp"]).isoformat(),
            "plate_text": curr["plate_text"],
            "plate_confidence": curr["plate_confidence"],
            "snapshot_path": curr.get("snapshot_path"),
            "snapshot_url": snapshot_url,
            "clip_url": clip_url,
            "hop": hop_info,
        })

    return {
        "query": query,
        "role": role,
        "match_count": len(results),
        "sightings": results,
    }


# -----------------------------------------------------------------------------
# 3. Network Heatmap
# -----------------------------------------------------------------------------
@app.get("/api/heatmap", summary="Camera sighting density heatmap")
def get_heatmap(
    date_from: Optional[str] = Query(None, description="Start timestamp"),
    date_to: Optional[str] = Query(None, description="End timestamp"),
):
    """Returns camera locations and sighting counts for spatial density mapping."""
    t_start = parse_timestamp_filter(date_from)
    t_end = parse_timestamp_filter(date_to)

    conn = get_db_connection()
    cursor = conn.cursor()

    time_conditions = []
    params = []
    if t_start is not None:
        time_conditions.append("timestamp >= ?")
        params.append(t_start)
    if t_end is not None:
        time_conditions.append("timestamp <= ?")
        params.append(t_end)

    where_clause = f"WHERE {' AND '.join(time_conditions)}" if time_conditions else ""

    cursor.execute(f"""
        SELECT camera_id, COUNT(*) as sighting_count, AVG(lat) as lat, AVG(lon) as lon
        FROM sightings
        {where_clause}
        GROUP BY camera_id
    """, params)
    rows = cursor.fetchall()
    conn.close()

    counts_by_cam = {r["camera_id"]: r["sighting_count"] for r in rows}

    # Ensure all cameras in camera_metadata are represented
    heatmap_data = []
    for cam_id, meta in CAMERA_METADATA.items():
        count = counts_by_cam.get(cam_id, 0)
        heatmap_data.append({
            "camera_id": cam_id,
            "name": meta.get("label", cam_id),
            "corridor": meta.get("corridor", ""),
            "lat": meta["lat"],
            "lon": meta["lon"],
            "sighting_count": count,
        })

    return heatmap_data


# -----------------------------------------------------------------------------
# 4. Restricted Zones
# -----------------------------------------------------------------------------
@app.get("/api/zones", summary="List restricted zones and geofences")
def get_zones():
    """Returns all circular restricted zones and high-security geofences."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT zone_id, name, center_lat, center_lon, radius_meters, reason FROM restricted_zones")
    rows = cursor.fetchall()
    conn.close()

    return [
        {
            "zone_id": r["zone_id"],
            "name": r["name"],
            "center_lat": r["center_lat"],
            "center_lon": r["center_lon"],
            "radius_meters": r["radius_meters"],
            "reason": r["reason"],
        }
        for r in rows
    ]


# -----------------------------------------------------------------------------
# 5. Corridor Baselines & Speed Profiles
# -----------------------------------------------------------------------------
@app.get("/api/corridor-baseline", summary="Statistical corridor transit baselines")
def get_corridor_baselines():
    """
    Returns statistical corridor transit baselines across camera pairs:
    Includes mean transit time, standard deviation, path frequency (sample_count),
    source ('seed' | 'observed'), and average speed (avg_speed_kmh).

    Design Note: This single endpoint covers both the average-speed-per-corridor
    and traffic-pattern requirements, deliberately not split into separate endpoints
    since the data already lives in one table.
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT id, camera_from, camera_to, distance_km, mean_transit_seconds,
               stddev_transit_seconds, sample_count, avg_speed_kmh, source, updated_at
        FROM corridor_baseline
        ORDER BY camera_from, camera_to
    """)
    rows = cursor.fetchall()
    conn.close()

    results = []
    for r in rows:
        mean_sec = r["mean_transit_seconds"]
        dist_km = r["distance_km"]
        computed_speed_kmh = round(dist_km / (mean_sec / 3600.0), 1) if mean_sec > 0 else 0.0

        results.append({
            "id": r["id"],
            "camera_from": r["camera_from"],
            "camera_to": r["camera_to"],
            "distance_km": round(dist_km, 3),
            "mean_transit_seconds": round(mean_sec, 1),
            "mean_transit_minutes": round(mean_sec / 60.0, 1),
            "stddev_transit_seconds": round(r["stddev_transit_seconds"], 1),
            "sample_count": r["sample_count"],
            "avg_speed_kmh": computed_speed_kmh,
            "source": r["source"],
            "updated_at": r["updated_at"],
        })

    return results


# -----------------------------------------------------------------------------
# 6. Traffic Trend (Hourly Buckets)
# -----------------------------------------------------------------------------
@app.get("/api/traffic-trend", summary="Hourly sighting distribution for traffic trend chart")
def get_traffic_trend(
    date_from: Optional[str] = Query(None, description="Start timestamp"),
    date_to: Optional[str] = Query(None, description="End timestamp"),
):
    """Returns vehicle sighting counts grouped by hour bucket for activity histograms."""
    t_start = parse_timestamp_filter(date_from)
    t_end = parse_timestamp_filter(date_to)

    conn = get_db_connection()
    cursor = conn.cursor()

    time_conditions = []
    params = []
    if t_start is not None:
        time_conditions.append("timestamp >= ?")
        params.append(t_start)
    if t_end is not None:
        time_conditions.append("timestamp <= ?")
        params.append(t_end)

    where_clause = f"WHERE {' AND '.join(time_conditions)}" if time_conditions else ""
    cursor.execute(f"SELECT timestamp FROM sightings {where_clause} ORDER BY timestamp ASC", params)
    rows = cursor.fetchall()
    conn.close()

    # Bucket by hour (0 to 23)
    hour_counts = {h: 0 for h in range(24)}
    for r in rows:
        dt = datetime.fromtimestamp(r["timestamp"])
        hour_counts[dt.hour] += 1

    # Format into list for chart rendering
    trend = []
    for h in range(24):
        trend.append({
            "hour": h,
            "hour_bucket": f"{h:02d}:00",
            "sighting_count": hour_counts[h],
        })

    return trend


# -----------------------------------------------------------------------------
# 7. Blacklist Check
# -----------------------------------------------------------------------------
@app.get("/api/blacklist/check", summary="Fuzzy check plate against blacklist")
def check_blacklist(
    plate: str = Query(..., description="Plate text to check"),
    role: str = Query("operator", description="User role ('operator' or 'supervisor')"),
):
    """
    Performs fuzzy Levenshtein match against blacklisted plates:
    - Returns match status, similarity ratio, and reason if matched.
    - Records search operation in audit_log.
    """
    log_audit_event(searched_query=f"Blacklist check: {plate}", searched_by=role)

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT plate_text, reason, added_on FROM blacklist")
    rows = cursor.fetchall()
    conn.close()

    clean_q = clean_plate_string(plate)
    best_match = None
    best_sim = 0.0

    for r in rows:
        target_plate = r["plate_text"]
        sim = plate_score(clean_q, target_plate)
        if clean_q == clean_plate_string(target_plate):
            sim = 1.0

        if sim > best_sim:
            best_sim = sim
            best_match = r

    matched = best_sim >= 0.85
    return {
        "query_plate": plate,
        "matched": matched,
        "similarity": round(best_sim, 4),
        "matched_entry": {
            "plate_text": best_match["plate_text"],
            "reason": best_match["reason"],
            "added_on": best_match["added_on"],
            "added_on_iso": datetime.fromtimestamp(best_match["added_on"]).isoformat(),
        } if matched and best_match else None,
    }


# -----------------------------------------------------------------------------
# 8. Alerts
# -----------------------------------------------------------------------------
@app.get("/api/alerts", summary="Retrieve all alerts most recent first")
def get_alerts():
    """Returns all recorded alerts ordered by creation timestamp descending."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT alert_id, alert_type, sighting_id_a, sighting_id_b, detail_text, created_at
        FROM alerts
        ORDER BY created_at DESC
    """)
    rows = cursor.fetchall()
    conn.close()

    return [
        {
            "alert_id": r["alert_id"],
            "alert_type": r["alert_type"],
            "sighting_id_a": r["sighting_id_a"],
            "sighting_id_b": r["sighting_id_b"],
            "detail_text": r["detail_text"],
            "created_at": r["created_at"],
            "created_at_iso": datetime.fromtimestamp(r["created_at"]).isoformat(),
        }
        for r in rows
    ]


@app.post("/api/alerts/scan", summary="Recompute and repopulate all alerts")
def scan_alerts():
    """
    Recomputes clone, impossible transit, zone deviation, blacklist,
    and corridor route-anomaly alerts across all sightings.
    """
    res = scan_and_repopulate_alerts()
    return res


# -----------------------------------------------------------------------------
# 9. Audit Log
# -----------------------------------------------------------------------------
@app.get("/api/audit-log", summary="Retrieve system search audit logs")
def get_audit_log():
    """Returns all audit log search entries ordered by timestamp descending."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT log_id, searched_by, searched_query, searched_at
        FROM audit_log
        ORDER BY searched_at DESC
    """)
    rows = cursor.fetchall()
    conn.close()

    return [
        {
            "log_id": r["log_id"],
            "searched_by": r["searched_by"],
            "searched_query": r["searched_query"],
            "searched_at": r["searched_at"],
            "searched_at_iso": datetime.fromtimestamp(r["searched_at"]).isoformat(),
        }
        for r in rows
    ]


# -----------------------------------------------------------------------------
# 10. Static Frontend Mount
# -----------------------------------------------------------------------------
FRONTEND_DIR = os.path.join(os.path.dirname(BACKEND_DIR), "frontend")
if os.path.exists(FRONTEND_DIR):
    app.mount("/", StaticFiles(directory=FRONTEND_DIR, html=True), name="frontend")
