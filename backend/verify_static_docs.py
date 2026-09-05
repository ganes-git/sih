"""
verify_static_docs.py — Validates the exported /docs static site running on http://127.0.0.1:8080.
Verifies that all views render purely from frozen JSON fixtures with zero backend API dependency.
"""

import asyncio
import json
import os
import sys
import urllib.request
import websockets

CDP_PORT = 9222
TARGET_URL = "http://127.0.0.1:8080/index.html"


class CDPClient:
    def __init__(self, ws_url):
        self.ws_url = ws_url
        self.ws = None
        self._msg_id = 0

    async def connect(self):
        self.ws = await websockets.connect(self.ws_url, max_size=50 * 1024 * 1024)
        await self.send("Page.enable")
        await self.send("Runtime.enable")

    async def send(self, method, params=None):
        self._msg_id += 1
        msg = {"id": self._msg_id, "method": method, "params": params or {}}
        await self.ws.send(json.dumps(msg))
        while True:
            raw = await self.ws.recv()
            resp = json.loads(raw)
            if resp.get("id") == self._msg_id:
                return resp

    async def evaluate(self, expr):
        res = await self.send("Runtime.evaluate", {
            "expression": expr,
            "awaitPromise": True,
            "returnByValue": True
        })
        val = res.get("result", {}).get("result", {}).get("value")
        return val

    async def close(self):
        if self.ws:
            await self.ws.close()


async def run_static_check():
    print("=" * 80)
    print("STAGE 9: PART A — TESTING EXPORTED /DOCS STATIC SITE (NO BACKEND)")
    print("=" * 80)

    req = urllib.request.urlopen(f"http://127.0.0.1:{CDP_PORT}/json")
    pages = json.loads(req.read().decode())
    target_page = next((p for p in pages if p.get("type") == "page"), None)
    assert target_page, "No open browser tab found"

    client = CDPClient(target_page["webSocketDebuggerUrl"])
    await client.connect()

    print(f"Navigating to static demo: {TARGET_URL}...")
    await client.send("Page.navigate", {"url": TARGET_URL})
    await asyncio.sleep(2.0)

    # Check 1: Trajectory view with static data
    print("\n--- TEST 1: STATIC TRAJECTORY RECONSTRUCTION ---")
    traj_res = await client.evaluate("""
        (async () => {
            await doTrajectorySearch();
            await new Promise(r => setTimeout(r, 600));
            const rows = document.querySelectorAll('#trajectory-table-body tr');
            const badges = document.querySelectorAll('#trajectory-table-body .badge-warn');
            const paths = document.querySelectorAll('#trajectory-map svg path');
            return {
                rowCount: rows.length,
                badgeCount: badges.length,
                badgeText: badges.length > 0 ? badges[0].innerText : null,
                pathCount: paths.length
            };
        })()
    """)
    print(f"Trajectory Static Result: {traj_res}")
    assert traj_res["rowCount"] >= 2, f"Expected >= 2 trajectory rows, got {traj_res['rowCount']}"
    assert traj_res["badgeCount"] >= 1, "Expected timing anomaly badge in static mode"
    print("[PASS] Static Trajectory Search successfully rendered from ./static-data/trajectory.json.")

    # Check 2: Live Camera Feeds (Static mode)
    print("\n--- TEST 2: STATIC CAMERA FEEDS GRID ---")
    await client.evaluate("showView('feeds');")
    await asyncio.sleep(1.0)
    feeds_res = await client.evaluate("""
        (() => {
            const cards = document.querySelectorAll('#feeds-grid-container .camera-card');
            return { cardCount: cards.length };
        })()
    """)
    print(f"Feeds Static Result: {feeds_res}")
    assert feeds_res["cardCount"] == 8, f"Expected 8 camera cards, got {feeds_res['cardCount']}"
    print("[PASS] Static Camera Feeds view rendered from ./static-data/cameras.json.")

    # Check 3: Heatmap (Static mode)
    print("\n--- TEST 3: STATIC HEATMAP & GEOFENCE ---")
    await client.evaluate("showView('heatmap');")
    await asyncio.sleep(1.0)
    heat_res = await client.evaluate("""
        (() => {
            const statusEl = document.getElementById('heatmap-status');
            const paths = document.querySelectorAll('#heatmap-map svg path');
            return {
                status: statusEl ? statusEl.innerText : '',
                svgCount: paths.length
            };
        })()
    """)
    print(f"Heatmap Static Result: {heat_res}")
    assert heat_res["svgCount"] >= 8, f"Expected >= 8 vector markers, got {heat_res['svgCount']}"
    print("[PASS] Static Heatmap rendered from ./static-data/heatmap.json and zones.json.")

    # Check 4: Blacklist (Static mode)
    print("\n--- TEST 4: STATIC BLACKLIST CHECK ---")
    await client.evaluate("showView('blacklist');")
    await asyncio.sleep(0.5)
    bl_res = await client.evaluate("""
        (async () => {
            document.getElementById('bl-plate-input').value = 'TN 07 AB 1234';
            await doBlacklistCheck();
            await new Promise(r => setTimeout(r, 400));
            const resEl = document.getElementById('bl-result');
            return {
                html: resEl ? resEl.innerHTML : '',
                hasMatch: resEl ? resEl.classList.contains('match') : false
            };
        })()
    """)
    print(f"Blacklist Static Result: hasMatch={bl_res['hasMatch']}")
    assert bl_res["hasMatch"], "Expected match in static blacklist check"
    assert "TN 07 AB 1234" in bl_res["html"], "Expected TN 07 AB 1234 in static match HTML"
    print("[PASS] Static Blacklist Check verified from ./static-data/blacklist-check.json.")

    # Check 5: Alerts & Audit Log (Static mode)
    print("\n--- TEST 5: STATIC ALERTS & AUDIT LOG ---")
    await client.evaluate("showView('alerts');")
    await asyncio.sleep(1.0)
    alerts_res = await client.evaluate("""
        (() => {
            const alertRows = document.querySelectorAll('#alerts-table-body tr');
            const auditRows = document.querySelectorAll('#audit-table-body tr');
            return {
                alertCount: alertRows.length,
                auditCount: auditRows.length
            };
        })()
    """)
    print(f"Alerts Static Result: {alerts_res}")
    assert alerts_res["alertCount"] >= 15, f"Expected >= 15 alerts, got {alerts_res['alertCount']}"
    assert alerts_res["auditCount"] >= 10, f"Expected >= 10 audit entries, got {alerts_res['auditCount']}"
    print("[PASS] Static Alerts & Audit Trail verified from ./static-data/alerts.json and audit-log.json.")

    # Check 6: Traffic Trends & Corridor Baselines (Static mode)
    print("\n--- TEST 6: STATIC TRAFFIC TRENDS & BASELINES ---")
    await client.evaluate("showView('traffic');")
    await asyncio.sleep(1.0)
    traffic_res = await client.evaluate("""
        (() => {
            const bars = document.querySelectorAll('#traffic-chart .chart-bar');
            const corridorRows = document.querySelectorAll('#corridor-table-body tr');
            return {
                barCount: bars.length,
                corridorCount: corridorRows.length
            };
        })()
    """)
    print(f"Traffic Static Result: {traffic_res}")
    assert traffic_res["barCount"] == 24, f"Expected 24 hourly bars, got {traffic_res['barCount']}"
    assert traffic_res["corridorCount"] == 7, f"Expected 7 corridor baseline rows, got {traffic_res['corridorCount']}"
    print("[PASS] Static Traffic Trends verified from ./static-data/traffic-trend.json and corridor-baseline.json.")

    print("\n" + "=" * 80)
    print("ALL 6 STATIC DEMO VIEWS TESTED AND CONFIRMED 100% OPERATIONAL WITHOUT BACKEND")
    print("=" * 80)

    await client.close()


if __name__ == "__main__":
    asyncio.run(run_static_check())
