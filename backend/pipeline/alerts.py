"""
Unified Multi-Modal Alert Scanner (Stage 6)
Computes and repopulates all system alerts:
1. Cloned plate detection (similar plate, divergent visual embedding)
2. Impossible transit velocities (> 90 km/h)
3. Restricted zone intrusions (Haversine distance <= radius)
4. Blacklist hits (fuzzy / exact plate match)
5. Statistical route anomalies (corridor baseline z-score > 2.5 or rare path)
"""

import os
import sys
import time
import uuid
import json
import sqlite3
from typing import Dict, Any, List, Optional

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from database import get_db_connection
from pipeline.match import (
    haversine_distance_km,
    clone_flag,
    plate_score,
    visual_score,
    transit_score,
    composite_score,
    MAX_CITY_SPEED_KMH,
)
from pipeline.baseline import generate_route_anomaly_alerts


def scan_and_repopulate_alerts() -> Dict[str, Any]:
    """
    Executes full multi-modal alert scan across sightings in anpr.db:
    - Clears existing alerts table.
    - Scans blacklist, restricted zones, cloned plates, impossible transit.
    - Triggers baseline route-anomaly alert generator.
    - Returns summary dictionary of created alerts.
    """
    conn = get_db_connection()
    cursor = conn.cursor()

    # Clear existing alerts to ensure clean idempotency
    cursor.execute("DELETE FROM alerts")

    # Load all sightings sorted chronologically
    cursor.execute("""
        SELECT sighting_id, camera_id, lat, lon, timestamp,
               plate_text, plate_confidence, embedding, snapshot_path
        FROM sightings
        ORDER BY timestamp ASC
    """)
    sightings = cursor.fetchall()
    sightings_data = []
    for s in sightings:
        s_dict = dict(s)
        try:
            s_dict["embedding"] = json.loads(s["embedding"])
        except Exception:
            s_dict["embedding"] = []
        sightings_data.append(s_dict)

    now = time.time()
    created_counts = {
        "blacklist": 0,
        "zone_deviation": 0,
        "clone": 0,
        "impossible_transit": 0,
        "route_anomaly": 0,
    }

    # 1. Blacklist Check
    cursor.execute("SELECT plate_text, reason FROM blacklist")
    bl_rows = cursor.fetchall()

    for s in sightings_data:
        p = s.get("plate_text")
        if p:
            norm_p = p.replace(" ", "").upper()
            for bl in bl_rows:
                norm_bl = bl["plate_text"].replace(" ", "").upper()
                if norm_p == norm_bl or plate_score(p, bl["plate_text"]) >= 0.90:
                    alert_id = f"ALT_BL_{uuid.uuid4().hex[:8].upper()}"
                    detail = (
                        f"BLACKLIST ALERT: Vehicle '{p}' detected at camera {s['camera_id']}. "
                        f"Reason: {bl['reason']}"
                    )
                    cursor.execute("""
                        INSERT INTO alerts (alert_id, alert_type, sighting_id_a, sighting_id_b, detail_text, created_at)
                        VALUES (?, ?, ?, ?, ?, ?)
                    """, (alert_id, "blacklist", s["sighting_id"], None, detail, now))
                    created_counts["blacklist"] += 1
                    break

    # 2. Restricted Zone Deviations
    cursor.execute("SELECT zone_id, name, center_lat, center_lon, radius_meters, reason FROM restricted_zones")
    zones = cursor.fetchall()

    for s in sightings_data:
        s_lat, s_lon = s["lat"], s["lon"]
        for z in zones:
            dist_km = haversine_distance_km(s_lat, s_lon, z["center_lat"], z["center_lon"])
            dist_m = dist_km * 1000.0
            if dist_m <= z["radius_meters"]:
                alert_id = f"ALT_ZONE_{uuid.uuid4().hex[:8].upper()}"
                detail = (
                    f"ZONE DEVIATION: Sighting at {s['camera_id']} ({dist_m:.1f}m from center) "
                    f"intruded into restricted zone '{z['name']}' (limit: {z['radius_meters']:.0f}m). "
                    f"Reason: {z['reason']}"
                )
                cursor.execute("""
                    INSERT INTO alerts (alert_id, alert_type, sighting_id_a, sighting_id_b, detail_text, created_at)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (alert_id, "zone_deviation", s["sighting_id"], None, detail, now))
                created_counts["zone_deviation"] += 1

    # 3. Clone and Impossible Transit across Sighting Pairs
    num_sightings = len(sightings_data)
    for i in range(num_sightings):
        for j in range(i + 1, num_sightings):
            s_a = sightings_data[i]
            s_b = sightings_data[j]

            # Clone check: similar plate, divergent visual embedding
            if clone_flag(s_a, s_b):
                alert_id = f"ALT_CLONE_{uuid.uuid4().hex[:8].upper()}"
                v_sim = visual_score(s_a["embedding"], s_b["embedding"])
                detail = (
                    f"CLONED PLATE ALERT: Identical/similar plate '{s_a['plate_text']}' / '{s_b['plate_text']}' "
                    f"observed on visually disparate vehicles between {s_a['camera_id']} and {s_b['camera_id']} "
                    f"(visual similarity {v_sim:.2f} < 0.60)."
                )
                cursor.execute("""
                    INSERT INTO alerts (alert_id, alert_type, sighting_id_a, sighting_id_b, detail_text, created_at)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (alert_id, "clone", s_a["sighting_id"], s_b["sighting_id"], detail, now))
                created_counts["clone"] += 1

            # Impossible transit check:
            # Check if sightings share identity (either plate or visual match) but travel impossibly fast
            p_match = plate_score(s_a.get("plate_text"), s_b.get("plate_text")) >= 0.85
            v_match = visual_score(s_a["embedding"], s_b["embedding"]) >= 0.70
            if (p_match or v_match) and s_a["camera_id"] != s_b["camera_id"]:
                dt = abs(s_b["timestamp"] - s_a["timestamp"])
                dist_km = haversine_distance_km(s_a["lat"], s_a["lon"], s_b["lat"], s_b["lon"])
                if dt < 1.0 and dist_km > 0.1:
                    speed_kmh = 9999.0
                elif dt > 0:
                    speed_kmh = dist_km / (dt / 3600.0)
                else:
                    speed_kmh = 9999.0

                if speed_kmh > MAX_CITY_SPEED_KMH:
                    alert_id = f"ALT_TRANSIT_{uuid.uuid4().hex[:8].upper()}"
                    detail = (
                        f"IMPOSSIBLE TRANSIT: Vehicle traveled {dist_km:.2f} km between "
                        f"{s_a['camera_id']} and {s_b['camera_id']} in {dt:.1f}s "
                        f"(implied velocity {speed_kmh:.1f} km/h > {MAX_CITY_SPEED_KMH} km/h limit)."
                    )
                    cursor.execute("""
                        INSERT INTO alerts (alert_id, alert_type, sighting_id_a, sighting_id_b, detail_text, created_at)
                        VALUES (?, ?, ?, ?, ?, ?)
                    """, (alert_id, "impossible_transit", s_a["sighting_id"], s_b["sighting_id"], detail, now))
                    created_counts["impossible_transit"] += 1

    conn.commit()
    conn.close()

    # 4. Route Anomalies from Corridor Baseline Engine
    route_alerts = generate_route_anomaly_alerts()
    created_counts["route_anomaly"] = len(route_alerts)

    total_created = sum(created_counts.values())
    return {
        "status": "success",
        "total_alerts": total_created,
        "counts": created_counts,
        "timestamp": now,
    }


if __name__ == "__main__":
    res = scan_and_repopulate_alerts()
    print("Alert scan completed:", res)
