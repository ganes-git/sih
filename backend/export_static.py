"""
export_static.py — Generates precomputed JSON data fixtures for static GitHub Pages export.
Extracts live database queries and FastAPI endpoints into /frontend/static-data/.
"""

import os
import sys
import json

# Add backend root to path
BACKEND_DIR = os.path.dirname(os.path.abspath(__file__))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from starlette.testclient import TestClient
from main import app

client = TestClient(app)

FRONTEND_DIR = os.path.join(os.path.dirname(BACKEND_DIR), "frontend")
STATIC_DATA_DIR = os.path.join(FRONTEND_DIR, "static-data")
os.makedirs(STATIC_DATA_DIR, exist_ok=True)


def export_all():
    print("=" * 80)
    print("EXPORTING STATIC DATA FIXTURES FOR GITHUB PAGES DEMO")
    print("=" * 80)

    # 1. Trajectory (KA 05 GH 3456 - Blue Coupe with timing anomaly)
    print("Fetching /api/trajectory?query=KA 05 GH 3456...")
    res = client.get("/api/trajectory?query=KA 05 GH 3456&role=supervisor")
    assert res.status_code == 200, f"Failed /api/trajectory: {res.text}"
    traj_data = res.json()
    with open(os.path.join(STATIC_DATA_DIR, "trajectory.json"), "w", encoding="utf-8") as f:
        json.dump(traj_data, f, indent=2)
    print(f"  -> Exported trajectory.json ({len(traj_data.get('sightings', []))} sightings)")

    # 2. Heatmap
    print("Fetching /api/heatmap...")
    res = client.get("/api/heatmap")
    assert res.status_code == 200, f"Failed /api/heatmap: {res.text}"
    heatmap_data = res.json()
    with open(os.path.join(STATIC_DATA_DIR, "heatmap.json"), "w", encoding="utf-8") as f:
        json.dump(heatmap_data, f, indent=2)
    print(f"  -> Exported heatmap.json ({len(heatmap_data)} cameras)")

    # 3. Zones
    print("Fetching /api/zones...")
    res = client.get("/api/zones")
    assert res.status_code == 200, f"Failed /api/zones: {res.text}"
    zones_data = res.json()
    with open(os.path.join(STATIC_DATA_DIR, "zones.json"), "w", encoding="utf-8") as f:
        json.dump(zones_data, f, indent=2)
    print(f"  -> Exported zones.json ({len(zones_data)} zones)")

    # 4. Corridor Baseline
    print("Fetching /api/corridor-baseline...")
    res = client.get("/api/corridor-baseline")
    assert res.status_code == 200, f"Failed /api/corridor-baseline: {res.text}"
    corridor_data = res.json()
    with open(os.path.join(STATIC_DATA_DIR, "corridor-baseline.json"), "w", encoding="utf-8") as f:
        json.dump(corridor_data, f, indent=2)
    print(f"  -> Exported corridor-baseline.json ({len(corridor_data)} routes)")

    # 5. Traffic Trend
    print("Fetching /api/traffic-trend...")
    res = client.get("/api/traffic-trend")
    assert res.status_code == 200, f"Failed /api/traffic-trend: {res.text}"
    trend_data = res.json()
    with open(os.path.join(STATIC_DATA_DIR, "traffic-trend.json"), "w", encoding="utf-8") as f:
        json.dump(trend_data, f, indent=2)
    print(f"  -> Exported traffic-trend.json ({len(trend_data)} hourly buckets)")

    # 6. Blacklist Check (Matched: TN 07 AB 1234)
    print("Fetching /api/blacklist/check?plate=TN 07 AB 1234...")
    res = client.get("/api/blacklist/check?plate=TN 07 AB 1234&role=supervisor")
    assert res.status_code == 200, f"Failed /api/blacklist/check: {res.text}"
    bl_data = res.json()
    with open(os.path.join(STATIC_DATA_DIR, "blacklist-check.json"), "w", encoding="utf-8") as f:
        json.dump(bl_data, f, indent=2)
    print(f"  -> Exported blacklist-check.json (matched: {bl_data.get('matched')})")

    # 7. Alerts
    print("Fetching /api/alerts...")
    res = client.get("/api/alerts")
    assert res.status_code == 200, f"Failed /api/alerts: {res.text}"
    alerts_data = res.json()
    with open(os.path.join(STATIC_DATA_DIR, "alerts.json"), "w", encoding="utf-8") as f:
        json.dump(alerts_data, f, indent=2)
    print(f"  -> Exported alerts.json ({len(alerts_data)} alerts)")

    # 8. Audit Log
    print("Fetching /api/audit-log...")
    res = client.get("/api/audit-log")
    assert res.status_code == 200, f"Failed /api/audit-log: {res.text}"
    audit_data = res.json()
    with open(os.path.join(STATIC_DATA_DIR, "audit-log.json"), "w", encoding="utf-8") as f:
        json.dump(audit_data, f, indent=2)
    print(f"  -> Exported audit-log.json ({len(audit_data)} entries)")

    # 9. Vehicles
    print("Fetching /api/vehicles...")
    res = client.get("/api/vehicles")
    assert res.status_code == 200, f"Failed /api/vehicles: {res.text}"
    vehicles_data = res.json()
    with open(os.path.join(STATIC_DATA_DIR, "vehicles.json"), "w", encoding="utf-8") as f:
        json.dump(vehicles_data, f, indent=2)
    v_count = len(vehicles_data) if isinstance(vehicles_data, list) else len(vehicles_data.get('vehicles', []))
    print(f"  -> Exported vehicles.json ({v_count} vehicles)")

    # 10. Cameras
    print("Fetching /api/cameras...")
    res = client.get("/api/cameras")
    assert res.status_code == 200, f"Failed /api/cameras: {res.text}"
    cameras_data = res.json()
    with open(os.path.join(STATIC_DATA_DIR, "cameras.json"), "w", encoding="utf-8") as f:
        json.dump(cameras_data, f, indent=2)
    c_count = len(cameras_data) if isinstance(cameras_data, list) else len(cameras_data.get('cameras', []))
    print(f"  -> Exported cameras.json ({c_count} cameras)")


    print("\n[SUCCESS] All 10 static fixtures exported to:", STATIC_DATA_DIR)


if __name__ == "__main__":
    export_all()
