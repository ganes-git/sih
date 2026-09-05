"""
export_static.py — Generates precomputed JSON data fixtures for static GitHub Pages export.
Extracts live database queries and FastAPI endpoints into /frontend/static-data/ and /docs/static-data/.
"""

import os
import sys
import json
import shutil

# Add backend root to path
BACKEND_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(BACKEND_DIR)
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from starlette.testclient import TestClient
from main import app

client = TestClient(app)

FRONTEND_STATIC = os.path.join(PROJECT_ROOT, "frontend", "static-data")
DOCS_STATIC = os.path.join(PROJECT_ROOT, "docs", "static-data")
os.makedirs(FRONTEND_STATIC, exist_ok=True)
os.makedirs(DOCS_STATIC, exist_ok=True)


def save_json_fixture(filename, data):
    for target_dir in [FRONTEND_STATIC, DOCS_STATIC]:
        path = os.path.join(target_dir, filename)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)


def export_all():
    print("=" * 80)
    print("EXPORTING STATIC DATA FIXTURES & TRAJECTORIES FOR ALL VEHICLES")
    print("=" * 80)

    # 1. Vehicles
    print("Fetching /api/vehicles...")
    res = client.get("/api/vehicles")
    assert res.status_code == 200, f"Failed /api/vehicles: {res.text}"
    vehicles_data = res.json()
    save_json_fixture("vehicles.json", vehicles_data)
    v_count = len(vehicles_data) if isinstance(vehicles_data, list) else len(vehicles_data.get('vehicles', []))
    print(f"  -> Exported vehicles.json ({v_count} vehicles)")

    # 2. Trajectories dictionary for ALL vehicles (Instant switching)
    trajectories_dict = {}
    default_traj = None

    for v in (vehicles_data if isinstance(vehicles_data, list) else vehicles_data.get('vehicles', [])):
        plate = v["plate_text"]
        res = client.get(f"/api/trajectory?query={plate}&role=supervisor")
        if res.status_code == 200:
            t_data = res.json()
            # Normalize clip URLs to relative paths
            for s in t_data.get("sightings", []):
                cam_num = s.get("camera_id", "").replace("CAM_", "")
                if cam_num.isdigit():
                    s["clip_url"] = f"./clips/camera_{int(cam_num)}.mp4"
                else:
                    s["clip_url"] = "./clips/camera_1.mp4"
            trajectories_dict[plate] = t_data
            clean_p = plate.replace(" ", "").upper()
            trajectories_dict[clean_p] = t_data
            if plate == "KA 05 GH 3456" or default_traj is None:
                default_traj = t_data

    # Save all trajectories dictionary & default trajectory
    save_json_fixture("trajectories.json", trajectories_dict)
    save_json_fixture("trajectory.json", default_traj)
    print(f"  -> Exported trajectories.json ({len(trajectories_dict)} indexed plate keys for 0ms switching)")
    print(f"  -> Exported default trajectory.json")

    # 3. Heatmap
    print("Fetching /api/heatmap...")
    res = client.get("/api/heatmap")
    assert res.status_code == 200, f"Failed /api/heatmap: {res.text}"
    heatmap_data = res.json()
    save_json_fixture("heatmap.json", heatmap_data)
    print(f"  -> Exported heatmap.json ({len(heatmap_data)} cameras)")

    # 4. Zones
    print("Fetching /api/zones...")
    res = client.get("/api/zones")
    assert res.status_code == 200, f"Failed /api/zones: {res.text}"
    zones_data = res.json()
    save_json_fixture("zones.json", zones_data)
    print(f"  -> Exported zones.json ({len(zones_data)} zones)")

    # 5. Corridor Baseline
    print("Fetching /api/corridor-baseline...")
    res = client.get("/api/corridor-baseline")
    assert res.status_code == 200, f"Failed /api/corridor-baseline: {res.text}"
    corridor_data = res.json()
    save_json_fixture("corridor-baseline.json", corridor_data)
    print(f"  -> Exported corridor-baseline.json ({len(corridor_data)} routes)")

    # 6. Traffic Trend
    print("Fetching /api/traffic-trend...")
    res = client.get("/api/traffic-trend")
    assert res.status_code == 200, f"Failed /api/traffic-trend: {res.text}"
    trend_data = res.json()
    save_json_fixture("traffic-trend.json", trend_data)
    print(f"  -> Exported traffic-trend.json ({len(trend_data)} hourly buckets)")

    # 7. Blacklist Check (Matched: TN 07 AB 1234)
    print("Fetching /api/blacklist/check?plate=TN 07 AB 1234...")
    res = client.get("/api/blacklist/check?plate=TN 07 AB 1234&role=supervisor")
    assert res.status_code == 200, f"Failed /api/blacklist/check: {res.text}"
    bl_data = res.json()
    save_json_fixture("blacklist-check.json", bl_data)
    print(f"  -> Exported blacklist-check.json (matched: {bl_data.get('matched')})")

    # 8. Alerts
    print("Fetching /api/alerts...")
    res = client.get("/api/alerts")
    assert res.status_code == 200, f"Failed /api/alerts: {res.text}"
    alerts_data = res.json()
    save_json_fixture("alerts.json", alerts_data)
    print(f"  -> Exported alerts.json ({len(alerts_data)} alerts)")

    # 9. Audit Log
    print("Fetching /api/audit-log...")
    res = client.get("/api/audit-log")
    assert res.status_code == 200, f"Failed /api/audit-log: {res.text}"
    audit_data = res.json()
    save_json_fixture("audit-log.json", audit_data)
    print(f"  -> Exported audit-log.json ({len(audit_data)} entries)")

    # 10. Cameras (Relative video clip URLs)
    print("Fetching /api/cameras...")
    res = client.get("/api/cameras")
    assert res.status_code == 200, f"Failed /api/cameras: {res.text}"
    cameras_data = res.json()
    for c in (cameras_data if isinstance(cameras_data, list) else cameras_data.get('cameras', [])):
        cam_num = c.get("camera_id", "").replace("CAM_", "")
        c["clip_url"] = f"./clips/camera_{int(cam_num)}.mp4" if cam_num.isdigit() else "./clips/camera_1.mp4"
    save_json_fixture("cameras.json", cameras_data)
    c_count = len(cameras_data) if isinstance(cameras_data, list) else len(cameras_data.get('cameras', []))
    print(f"  -> Exported cameras.json ({c_count} cameras with relative ./clips/ URLs)")

    # 11. Copy video clips to /docs/clips and /frontend/clips
    src_clips = os.path.join(PROJECT_ROOT, "backend", "data", "clips")
    for dest_dir in [os.path.join(PROJECT_ROOT, "docs", "clips"), os.path.join(PROJECT_ROOT, "frontend", "clips")]:
        os.makedirs(dest_dir, exist_ok=True)
        for f in os.listdir(src_clips):
            if f.endswith(".mp4"):
                shutil.copy2(os.path.join(src_clips, f), os.path.join(dest_dir, f))
    print("  -> Synced video clips into /docs/clips/ and /frontend/clips/")

    print("\n[SUCCESS] All static fixtures and video assets exported cleanly.")


if __name__ == "__main__":
    export_all()
