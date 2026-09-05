"""
Automated Test Suite for Corridor Baselines & Route Anomaly Detection (Stage 5)
Verifies:
1. recompute_corridor_baselines() populates corridor_baseline with both 'seed' and 'observed' routes.
2. generate_route_anomaly_alerts() produces at least one route_anomaly alert for the engineered case.
3. Detailed metrics and z-scores are printed plainly with full mathematical explainability.
"""

import os
import sys
import sqlite3

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
from pipeline.baseline import (
    recompute_corridor_baselines,
    generate_route_anomaly_alerts,
    score_hop,
)


def test_corridor_baselines_and_route_anomalies():
    print("=" * 90)
    print("       STAGE 5: CORRIDOR BASELINE & ROUTE ANOMALY TEST SUITE")
    print("=" * 90)

    # 1. Recompute corridor baselines
    baselines = recompute_corridor_baselines()
    assert len(baselines) > 0, "Expected at least one corridor baseline to be computed"

    conn = get_db_connection()
    cursor = conn.cursor()

    # Query all baseline rows
    cursor.execute("""
        SELECT camera_from, camera_to, distance_km, mean_transit_seconds,
               stddev_transit_seconds, sample_count, avg_speed_kmh, source
        FROM corridor_baseline
        ORDER BY camera_from, camera_to
    """)
    all_rows = cursor.fetchall()

    seed_rows = [r for r in all_rows if r["source"] == "seed"]
    observed_rows = [r for r in all_rows if r["source"] == "observed"]

    print("\nCorridor Baseline Route Calibration Table:")
    print(f"{'Hop':<16} | {'Dist (km)':<10} | {'Mean (s)':<10} | {'StdDev (s)':<10} | {'Samples':<8} | {'Speed (km/h)':<12} | {'Source':<10}")
    print("-" * 90)
    for r in all_rows:
        hop_str = f"{r['camera_from']} -> {r['camera_to']}"
        print(f"{hop_str:<16} | {r['distance_km']:<10.3f} | {r['mean_transit_seconds']:<10.1f} | {r['stddev_transit_seconds']:<10.1f} | {r['sample_count']:<8} | {r['avg_speed_kmh']:<12.1f} | {r['source']:<10}")

    print("-" * 90)
    print(f"Total Baselines: {len(all_rows)} (Observed: {len(observed_rows)}, Seed: {len(seed_rows)})")

    # Assertions required by Stage 5
    assert len(seed_rows) >= 1, f"Expected at least one 'seed' baseline, got {len(seed_rows)}"
    assert len(observed_rows) >= 1, f"Expected at least one 'observed' baseline, got {len(observed_rows)}"
    print("[PASS] Verified both 'seed' and 'observed' corridor baselines exist in corridor_baseline.")

    # 2. Generate and verify route anomaly alerts
    route_alerts = generate_route_anomaly_alerts()
    cursor.execute("""
        SELECT alert_id, alert_type, sighting_id_a, sighting_id_b, detail_text, created_at
        FROM alerts
        WHERE alert_type = 'route_anomaly'
    """)
    db_route_alerts = cursor.fetchall()

    print("\nRoute Anomaly Alerts Detected:")
    print("-" * 90)
    for a in db_route_alerts:
        print(f"  [{a['alert_id']}] {a['detail_text']}")

    assert len(db_route_alerts) >= 1, "Expected at least one route_anomaly alert in alerts table!"
    print(f"\n[PASS] Verified {len(db_route_alerts)} route_anomaly alert(s) created from engineered case.")

    # 3. Verify specific engineered anomaly on CAM_04 -> CAM_07
    eval_engineered = score_hop("CAM_04", "CAM_07", 1320.0)
    print("\nEngineered Anomaly Evaluation (CAM_04 -> CAM_07):")
    print(f"  Actual Elapsed Time:  1320.0s (22.0 min)")
    print(f"  Baseline Normal:      {eval_engineered['mean_seconds']:.1f}s ({eval_engineered['mean_seconds']/60.0:.1f} min) +/- {eval_engineered['stddev_seconds']:.1f}s")
    print(f"  Computed Z-Score:     z = {eval_engineered['z_score']}")
    print(f"  Anomaly Detected:     {eval_engineered['is_anomaly']}")
    assert eval_engineered["is_anomaly"], "Expected CAM_04 -> CAM_07 hop to be flagged as route anomaly!"
    print("[PASS] Engineered route anomaly verified with statistical significance (z > 2.5).")

    conn.close()
    print("=" * 90)


if __name__ == "__main__":
    test_corridor_baselines_and_route_anomalies()
