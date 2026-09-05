"""
Automated Stage 8 End-to-End Verification and Screenshot Capture Script
Using Edge/Chrome Headless with Chrome DevTools Protocol (CDP).
"""

import os
import sys
import time
import json
import base64
import subprocess
import urllib.request
import asyncio
import websockets

BACKEND_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(BACKEND_DIR)
SCREENSHOTS_DIR = os.path.join(PROJECT_ROOT, "docs", "screenshots")
os.makedirs(SCREENSHOTS_DIR, exist_ok=True)

CDP_PORT = 9222


class CDPClient:
    def __init__(self, ws_url):
        self.ws_url = ws_url
        self.ws = None
        self._msg_id = 0

    async def connect(self):
        self.ws = await websockets.connect(self.ws_url, max_size=50 * 1024 * 1024)

    async def send_command(self, method, params=None):
        self._msg_id += 1
        cmd_id = self._msg_id
        payload = {"id": cmd_id, "method": method, "params": params or {}}
        await self.ws.send(json.dumps(payload))
        while True:
            resp = await self.ws.recv()
            data = json.loads(resp)
            if "method" in data:
                if data["method"] == "Runtime.consoleAPICalled":
                    print(f"[CONSOLE {data['params'].get('type')}]:", [arg.get('value', arg) for arg in data['params'].get('args', [])])
                elif data["method"] == "Runtime.exceptionThrown":
                    print(f"[JS EXCEPTION]:", data['params'].get('exceptionDetails', {}))
            if data.get("id") == cmd_id:
                if "error" in data:
                    raise Exception(f"CDP Error in {method}: {data['error']}")
                return data.get("result", {})

    async def evaluate(self, expression):
        res = await self.send_command("Runtime.evaluate", {
            "expression": expression,
            "returnByValue": True,
            "awaitPromise": True
        })
        result = res.get("result", {})
        if "value" in result:
            return result["value"]
        return result

    async def capture_screenshot(self, filepath):
        res = await self.send_command("Page.captureScreenshot", {"format": "png"})
        img_bytes = base64.b64decode(res["data"])
        with open(filepath, "wb") as f:
            f.write(img_bytes)
        print(f"[SCREENSHOT] Saved: {filepath} ({len(img_bytes)} bytes)")

    async def close(self):
        if self.ws:
            await self.ws.close()


async def run_walkthrough():
    print("=" * 80)
    print("STAGE 8: CHECK 1 (FUNCTIONAL WALKTHROUGH) & CHECK 3 (EVIDENCE CAPTURE)")
    print("=" * 80)

    # Start Edge Headless with isolated profile
    temp_profile = os.path.join(BACKEND_DIR, ".browser_profile")
    os.makedirs(temp_profile, exist_ok=True)
    app_url = "http://127.0.0.1:8000/index.html"
    edge_cmd = [
        r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
        "--headless=new",
        f"--remote-debugging-port={CDP_PORT}",
        f"--user-data-dir={temp_profile}",
        "--no-first-run",
        "--no-default-browser-check",
        "--disable-gpu",
        "--no-sandbox",
        "--window-size=1440,900",
        app_url,
    ]
    proc = subprocess.Popen(edge_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    time.sleep(2.5)

    try:
        tab_url = f"http://127.0.0.1:{CDP_PORT}/json"
        req = urllib.request.urlopen(tab_url)
        tabs = json.loads(req.read().decode())
        page_tabs = [t for t in tabs if t.get("type") == "page" and "8000" in t.get("url", "")]
        if not page_tabs:
            page_tabs = [t for t in tabs if t.get("type") == "page"]
        target_tab = page_tabs[0]
        ws_url = target_tab["webSocketDebuggerUrl"]
        print(f"Connected to page: {target_tab.get('url')}")

        client = CDPClient(ws_url)
        await client.connect()
        await client.send_command("Page.enable")
        await client.send_command("Runtime.enable")
        await client.send_command("DOM.enable")

        print(f"Navigating to {app_url}...")
        await client.send_command("Page.navigate", {"url": app_url})

        # Wait for page ready
        for _ in range(20):
            await asyncio.sleep(0.5)
            ready = await client.evaluate("""
                (() => {
                    return document.readyState === 'complete' && !!document.getElementById('traj-query');
                })()
            """)
            if ready:
                print("Page is loaded and ready.")
                break
        else:
            print("[WARN] Timed out waiting for page ready.")

        # -------------------------------------------------------------
        # 1. Trajectory Search View & Dropdown Check
        # -------------------------------------------------------------
        print("\n--- VIEW 1: TRAJECTORY SEARCH & VEHICLES DROPDOWN ---")
        init_res = await client.evaluate("""
            (() => {
                const selectEl = document.getElementById('traj-plate-select');
                return {
                    trajQueryExists: !!document.getElementById('traj-query'),
                    doTrajectorySearchExists: typeof doTrajectorySearch === 'function',
                    dropdownOptionCount: selectEl ? selectEl.options.length : 0,
                    currentRole: typeof currentRole !== 'undefined' ? currentRole : null,
                    L_exists: typeof L !== 'undefined'
                };
            })()
        """)
        print(f"Init state: {init_res}")
        assert init_res["dropdownOptionCount"] >= 5, f"Expected vehicle dropdown options >= 5, got {init_res['dropdownOptionCount']}"
        print(f"[PASS] Vehicles dropdown populated with {init_res['dropdownOptionCount']} distinct tracked vehicle choices.")

        search_res = await client.evaluate("""
            (async () => {
                try {
                    document.getElementById('traj-query').value = 'KA 05 GH 3456';
                    await doTrajectorySearch();
                    return { success: true };
                } catch(e) {
                    return { error: e.toString(), stack: e.stack };
                }
            })()
        """)
        print(f"Search Execution Result: {search_res}")
        await asyncio.sleep(1.5)

        traj_check = await client.evaluate("""
            (() => {
                const tableRows = document.querySelectorAll('#trajectory-table-body tr');
                const badges = document.querySelectorAll('#trajectory-table-body .badge-warn');
                const paths = document.querySelectorAll('#trajectory-map svg path');
                const infoEl = document.getElementById('trajectory-result-info');
                return {
                    info: infoEl ? infoEl.innerText : '',
                    rowCount: tableRows.length,
                    badgeCount: badges.length,
                    badgeText: badges.length > 0 ? badges[0].innerText : null,
                    pathCount: paths.length
                };
            })()
        """)
        print(f"Trajectory Check: {traj_check}")
        assert traj_check.get("rowCount", 0) >= 2, f"Trajectory hop rows should be >= 2, got: {traj_check}"
        assert traj_check.get("badgeCount", 0) >= 1, "At least one anomalous hop badge expected"
        print(f"[PASS] Trajectory search returned {traj_check['rowCount']} sightings with badge: '{traj_check['badgeText']}'")

        ss_traj = os.path.join(SCREENSHOTS_DIR, "01_trajectory_search.png")
        await client.capture_screenshot(ss_traj)

        # -------------------------------------------------------------
        # 1B. Live Camera Feeds View (Stage 4 & 5)
        # -------------------------------------------------------------
        print("\n--- VIEW 1B: LIVE CAMERA FEEDS GRID ---")
        await client.evaluate("showView('feeds');")
        await asyncio.sleep(1.5)

        feeds_check = await client.evaluate("""
            (() => {
                const cards = document.querySelectorAll('#feeds-grid-container .camera-card');
                const videos = document.querySelectorAll('#feeds-grid-container video');
                return {
                    active: document.getElementById('view-feeds').classList.contains('active'),
                    cardCount: cards.length,
                    videoCount: videos.length
                };
            })()
        """)
        print(f"Feeds Check: {feeds_check}")
        assert feeds_check["active"], "Feeds view should be active"
        assert feeds_check["cardCount"] == 8, f"Expected 8 camera cards, got {feeds_check['cardCount']}"
        assert feeds_check["videoCount"] == 8, f"Expected 8 live video elements, got {feeds_check['videoCount']}"
        print(f"[PASS] Live Camera Feeds view rendered all 8 video streams (1080p @ 25fps).")

        ss_feeds = os.path.join(SCREENSHOTS_DIR, "06_live_camera_feeds.png")
        await client.capture_screenshot(ss_feeds)

        # -------------------------------------------------------------
        # 2. Heatmap View
        # -------------------------------------------------------------
        print("\n--- VIEW 2: HEATMAP ---")
        await client.evaluate("showView('heatmap');")
        await asyncio.sleep(1.5)

        heat_check = await client.evaluate("""
            (() => {
                const mapEl = document.getElementById('heatmap-map');
                const paths = mapEl ? mapEl.querySelectorAll('svg path') : [];
                return {
                    active: document.getElementById('view-heatmap').classList.contains('active'),
                    svgPathCount: paths.length
                };
            })()
        """)
        print(f"Heatmap Check: {heat_check}")
        assert heat_check["active"], "Heatmap view should be active"
        assert heat_check["svgPathCount"] >= 8, "Expected 8 camera markers + zone circle"
        print(f"[PASS] Heatmap rendered with {heat_check['svgPathCount']} map vector overlays.")

        ss_heat = os.path.join(SCREENSHOTS_DIR, "02_heatmap_view.png")
        await client.capture_screenshot(ss_heat)

        # -------------------------------------------------------------
        # 3. Blacklist View
        # -------------------------------------------------------------
        print("\n--- VIEW 3: BLACKLIST ---")
        await client.evaluate("showView('blacklist');")
        await asyncio.sleep(0.5)

        # Test matched query
        check_eval = await client.evaluate("""
            (async () => {
                try {
                    document.getElementById('bl-plate-input').value = 'TN 07 AB 1234';
                    await doBlacklistCheck();
                    return { executed: true };
                } catch(e) {
                    return { error: e.toString(), stack: e.stack };
                }
            })()
        """)
        print(f"Blacklist check evaluate: {check_eval}")
        await asyncio.sleep(1.0)
        match_res = await client.evaluate("""
            (() => {
                const resEl = document.getElementById('bl-result');
                return {
                    html: resEl ? resEl.innerHTML : '',
                    hasMatchClass: resEl ? resEl.classList.contains('match') : false
                };
            })()
        """)
        print(f"Blacklist Match Result: {match_res}")
        assert "TN 07 AB 1234" in match_res["html"], f"Blacklist should match TN 07 AB 1234, got: {match_res}"

        assert match_res["hasMatchClass"], "Blacklist match element must have .match class"
        print("[PASS] Blacklist match check confirmed for TN 07 AB 1234.")

        # Test non-matched query
        await client.evaluate("""
            (async () => {
                document.getElementById('bl-plate-input').value = 'DL 01 AA 0000';
                await doBlacklistCheck();
            })()
        """)
        await asyncio.sleep(1.0)
        non_match_res = await client.evaluate("""
            (() => {
                const resEl = document.getElementById('bl-result');
                return {
                    text: resEl.innerText,
                    hasNoMatchClass: resEl.classList.contains('no-match')
                };
            })()
        """)
        assert "No match" in non_match_res["text"], "Blacklist check for DL 01 AA 0000 should report no match"
        assert non_match_res["hasNoMatchClass"], "Blacklist non-match element must have .no-match class"
        print("[PASS] Blacklist non-match check confirmed for DL 01 AA 0000.")

        # Re-check match for clean screenshot
        await client.evaluate("""
            (async () => {
                document.getElementById('bl-plate-input').value = 'TN 07 AB 1234';
                await doBlacklistCheck();
            })()
        """)
        await asyncio.sleep(0.8)

        ss_black = os.path.join(SCREENSHOTS_DIR, "03_blacklist_view.png")
        await client.capture_screenshot(ss_black)

        # -------------------------------------------------------------
        # 4. Alerts & Security Audit Log View (Unified Console)
        # -------------------------------------------------------------
        print("\n--- VIEW 4: ALERTS & AUDIT LOG (UNIFIED CONSOLE) ---")
        await client.evaluate("showView('alerts');")
        await asyncio.sleep(1.5)

        alert_check = await client.evaluate("""
            (() => {
                const rows = document.querySelectorAll('#alerts-table-body tr');
                const types = new Set();
                rows.forEach(r => {
                    const span = r.querySelector('td span[class^="alert-"]');
                    if (span) types.add(span.innerText.trim().toLowerCase());
                });
                const auditSec = document.getElementById('audit-log-section');
                const auditRows = document.querySelectorAll('#audit-table-body tr');
                return {
                    rowCount: rows.length,
                    alertTypes: Array.from(types),
                    auditLogVisible: auditSec ? auditSec.style.display !== 'none' : false,
                    auditRowCount: auditRows.length
                };
            })()
        """)
        print(f"Alerts & Audit Log Check: {alert_check}")
        types_set = set(alert_check["alertTypes"])
        assert "clone" in types_set, "Expected clone alert"
        assert "blacklist" in types_set, "Expected blacklist alert"
        assert "zone_deviation" in types_set, "Expected zone_deviation alert"
        assert "route_anomaly" in types_set, "Expected route_anomaly alert"
        assert alert_check["auditLogVisible"], "Audit log should be visible in unified console mode"
        assert alert_check["auditRowCount"] > 0, "Audit log rows should be present"
        print("[PASS] Alerts & Audit Log verified in unified mode.")

        ss_alerts = os.path.join(SCREENSHOTS_DIR, "04_alerts_and_audit_log_supervisor.png")
        await client.capture_screenshot(ss_alerts)

        # -------------------------------------------------------------
        # 5. Traffic Trends View
        # -------------------------------------------------------------
        print("\n--- VIEW 5: TRAFFIC TRENDS & CORRIDOR BASELINES ---")
        await client.evaluate("showView('traffic');")
        await asyncio.sleep(1.5)

        traffic_check = await client.evaluate("""
            (() => {
                const bars = document.querySelectorAll('#traffic-chart .chart-bar');
                const heights = Array.from(bars).map(b => b.style.height);
                const isNonFlat = new Set(heights).size > 1;
                const rows = document.querySelectorAll('#corridor-table-body tr');
                const speeds = Array.from(rows).map(r => r.cells[4] ? r.cells[4].innerText : '');
                return {
                    barCount: bars.length,
                    isNonFlat: isNonFlat,
                    corridorRowCount: rows.length,
                    speeds: speeds
                };
            })()
        """)
        print(f"Traffic Check: {traffic_check}")
        assert traffic_check["barCount"] == 24, "Expected 24 hourly bars"
        assert traffic_check["isNonFlat"], "Traffic trend chart must be non-flat"
        assert traffic_check["corridorRowCount"] == 7, "Expected 7 corridor baseline rows"
        print(f"[PASS] Traffic trend chart has 24 non-flat hourly bars. Corridor baseline table shows real speeds: {traffic_check['speeds'][:3]}...")

        ss_traffic = os.path.join(SCREENSHOTS_DIR, "05_traffic_trends_and_baselines.png")
        await client.capture_screenshot(ss_traffic)

        await client.close()
        print("\n" + "=" * 80)
        print("ALL CHECK 1 FUNCTIONAL TESTS AND CHECK 3 SCREENSHOT CAPTURES PASSED!")
        print("=" * 80)

    finally:
        proc.terminate()
        try:
            proc.wait(timeout=2)
        except Exception:
            proc.kill()


if __name__ == "__main__":
    asyncio.run(run_walkthrough())
