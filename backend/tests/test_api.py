"""
REST API Automated Test Suite (Stage 6)
Validates all FastAPI endpoints using TestClient:
- /api/health
- /api/trajectory
- /api/heatmap
- /api/zones
- /api/corridor-baseline
- /api/traffic-trend
- /api/blacklist/check
- /api/alerts
- /api/alerts/scan
- /api/audit-log
"""

import os
import sys
from fastapi.testclient import TestClient

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from main import app

client = TestClient(app)


def test_api_endpoints():
    print("=" * 90)
    print("         STAGE 6: FASTAPI REST ENDPOINTS VERIFICATION SUITE")
    print("=" * 90)

    # 1. Health check
    res = client.get("/api/health")
    assert res.status_code == 200, f"Health check failed: {res.text}"
    body = res.json()
    assert body.get("status") == "ok"
    assert "version" in body
    print("[PASS] GET /api/health -> 200 OK")

    # 2. Alerts scan (POST /api/alerts/scan)
    res = client.post("/api/alerts/scan")
    assert res.status_code == 200, f"Alert scan failed: {res.text}"
    body = res.json()
    assert body.get("status") == "success"
    assert body.get("total_alerts", 0) > 0
    print(f"[PASS] POST /api/alerts/scan -> 200 OK ({body.get('total_alerts')} alerts generated)")

    # 3. Trajectory query (GET /api/trajectory)
    res = client.get("/api/trajectory?query=KA 05 GH 3456&role=operator")
    assert res.status_code == 200, f"Trajectory query failed: {res.text}"
    traj = res.json()
    assert traj["query"] == "KA 05 GH 3456"
    assert traj["role"] == "operator"
    assert traj["match_count"] >= 2, f"Expected at least 2 sightings for Blue Coupe, got {traj['match_count']}"
    assert len(traj["sightings"]) >= 2

    # Verify per-hop score breakdown & baseline anomaly metrics
    first_sighting = traj["sightings"][0]
    hop = first_sighting.get("hop")
    assert hop is not None, "First sighting must have a hop object connecting to the next sighting"
    assert "plate_score" in hop
    assert "visual_score" in hop
    assert "transit_score" in hop
    assert "composite_score" in hop
    assert "timing_anomaly_score" in hop
    assert "is_path_rare" in hop
    assert hop["timing_anomaly_score"] is not None
    assert hop["is_timing_anomaly"] is True, f"Expected engineered route anomaly, got z={hop['timing_anomaly_score']}"
    print(f"[PASS] GET /api/trajectory -> 200 OK (Reconstructed {traj['match_count']} hops with score breakdown & route_anomaly z={hop['timing_anomaly_score']})")

    # 4. Heatmap (GET /api/heatmap)
    res = client.get("/api/heatmap")
    assert res.status_code == 200, f"Heatmap failed: {res.text}"
    heatmap = res.json()
    assert isinstance(heatmap, list)
    assert len(heatmap) >= 8
    first_cam = heatmap[0]
    assert "camera_id" in first_cam
    assert "lat" in first_cam
    assert "lon" in first_cam
    assert "sighting_count" in first_cam
    print(f"[PASS] GET /api/heatmap -> 200 OK ({len(heatmap)} cameras mapped)")

    # 5. Restricted Zones (GET /api/zones)
    res = client.get("/api/zones")
    assert res.status_code == 200, f"Zones failed: {res.text}"
    zones = res.json()
    assert isinstance(zones, list)
    assert len(zones) >= 1
    zone0 = zones[0]
    assert "zone_id" in zone0
    assert "name" in zone0
    assert "center_lat" in zone0
    assert "center_lon" in zone0
    assert "radius_meters" in zone0
    print(f"[PASS] GET /api/zones -> 200 OK ({len(zones)} zone(s) registered)")

    # 6. Corridor Baselines (GET /api/corridor-baseline)
    res = client.get("/api/corridor-baseline")
    assert res.status_code == 200, f"Corridor baseline failed: {res.text}"
    baselines = res.json()
    assert isinstance(baselines, list)
    assert len(baselines) >= 6
    b0 = baselines[0]
    assert "camera_from" in b0
    assert "camera_to" in b0
    assert "distance_km" in b0
    assert "avg_speed_kmh" in b0
    assert b0["avg_speed_kmh"] > 0
    assert "source" in b0
    print(f"[PASS] GET /api/corridor-baseline -> 200 OK ({len(baselines)} routes with avg_speed_kmh computed)")

    # 7. Traffic Trend (GET /api/traffic-trend)
    res = client.get("/api/traffic-trend")
    assert res.status_code == 200, f"Traffic trend failed: {res.text}"
    trend = res.json()
    assert isinstance(trend, list)
    assert len(trend) == 24
    assert "hour" in trend[0]
    assert "hour_bucket" in trend[0]
    assert "sighting_count" in trend[0]
    total_sightings = sum(t["sighting_count"] for t in trend)
    assert total_sightings > 0, "Expected non-zero sightings in traffic trend"
    print(f"[PASS] GET /api/traffic-trend -> 200 OK (24 hourly buckets, {total_sightings} total sightings)")

    # 8. Blacklist Check (GET /api/blacklist/check)
    res = client.get("/api/blacklist/check?plate=TN 07 AB 1234&role=supervisor")
    assert res.status_code == 200, f"Blacklist check failed: {res.text}"
    bl = res.json()
    assert bl["matched"] is True
    assert bl["similarity"] >= 0.95
    assert bl["matched_entry"] is not None
    assert "reason" in bl["matched_entry"]
    print(f"[PASS] GET /api/blacklist/check -> 200 OK (Matched: {bl['matched_entry']['plate_text']} | Reason: {bl['matched_entry']['reason'][:40]}...)")

    # 9. Alerts (GET /api/alerts)
    res = client.get("/api/alerts")
    assert res.status_code == 200, f"Alerts failed: {res.text}"
    alerts = res.json()
    assert isinstance(alerts, list)
    assert len(alerts) > 0
    alert_types = {a["alert_type"] for a in alerts}
    print(f"[INFO] Alert types present in /api/alerts: {alert_types}")
    assert "clone" in alert_types, "Expected at least one 'clone' alert in /api/alerts"
    assert "zone_deviation" in alert_types, "Expected at least one 'zone_deviation' alert in /api/alerts"
    assert "route_anomaly" in alert_types, "Expected at least one 'route_anomaly' alert in /api/alerts"
    print(f"[PASS] GET /api/alerts -> 200 OK ({len(alerts)} alerts, confirmed 'clone', 'zone_deviation', and 'route_anomaly' are all present)")

    # 10. Audit Log (GET /api/audit-log)
    res = client.get("/api/audit-log")
    assert res.status_code == 200, f"Audit log failed: {res.text}"
    logs = res.json()
    assert isinstance(logs, list)
    assert len(logs) >= 2, "Expected at least 2 audit log entries from trajectory & blacklist queries"
    searched_queries = [l["searched_query"] for l in logs]
    searched_roles = {l["searched_by"] for l in logs}
    assert any("KA 05 GH 3456" in q for q in searched_queries)
    assert any("TN 07 AB 1234" in q for q in searched_queries)
    assert "operator" in searched_roles
    assert "supervisor" in searched_roles
    print(f"[PASS] GET /api/audit-log -> 200 OK ({len(logs)} audit entries logged with operator/supervisor roles)")

    print("=" * 90)
    print("ALL 10 API ENDPOINTS VALIDATED SUCCESSFULLY (100% PASS)")
    print("=" * 90)


if __name__ == "__main__":
    test_api_endpoints()
