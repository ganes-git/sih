"""
verify_live_pages.py — Validates the real published GitHub Pages URL https://ganes-git.github.io/sih/
"""

import asyncio
import json
import urllib.request
import websockets

CDP_PORT = 9222
LIVE_PAGES_URL = "https://ganes-git.github.io/sih/"


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


async def run_live_check():
    print("=" * 80)
    print(f"PART D: CHECK 2 — VERIFYING LIVE GITHUB PAGES DEPLOYMENT AT {LIVE_PAGES_URL}")
    print("=" * 80)

    req = urllib.request.urlopen(f"http://127.0.0.1:{CDP_PORT}/json")
    pages = json.loads(req.read().decode())
    target_page = next((p for p in pages if p.get("type") == "page"), None)
    assert target_page, "No open browser tab found"

    client = CDPClient(target_page["webSocketDebuggerUrl"])
    await client.connect()

    print(f"Navigating to live deployment: {LIVE_PAGES_URL}...")
    await client.send("Page.navigate", {"url": LIVE_PAGES_URL})
    await asyncio.sleep(3.0)

    # 1. Verify Trajectory View
    print("\n--- TEST 1: LIVE TRAJECTORY RECONSTRUCTION ---")
    traj_res = await client.evaluate("""
        (async () => {
            await doTrajectorySearch();
            await new Promise(r => setTimeout(r, 600));
            const rows = document.querySelectorAll('#trajectory-table-body tr');
            const badges = document.querySelectorAll('#trajectory-table-body .badge-warn');
            const paths = document.querySelectorAll('#trajectory-map svg path');
            return {
                title: document.title,
                rowCount: rows.length,
                badgeCount: badges.length,
                badgeText: badges.length > 0 ? badges[0].innerText : null,
                pathCount: paths.length
            };
        })()
    """)
    print(f"Live Trajectory Result: {traj_res}")
    assert traj_res["rowCount"] >= 2, f"Expected >= 2 rows on live site, got: {traj_res}"
    assert traj_res["badgeCount"] >= 1, "Expected timing anomaly badge on live site"
    print("[PASS] Live GitHub Pages Trajectory Search verified.")

    # 2. Verify Alerts View
    print("\n--- TEST 2: LIVE ALERTS & AUDIT TRAIL ---")
    await client.evaluate("showView('alerts');")
    await asyncio.sleep(0.5)
    alerts_res = await client.evaluate("""
        (async () => {
            await loadAlerts();
            await new Promise(r => setTimeout(r, 800));
            const alertRows = document.querySelectorAll('#alerts-table-body tr');
            const auditRows = document.querySelectorAll('#audit-table-body tr');
            return {
                alertCount: alertRows.length,
                auditCount: auditRows.length
            };
        })()
    """)
    print(f"Live Alerts Result: {alerts_res}")
    assert alerts_res["alertCount"] >= 15, f"Expected >= 15 alerts on live site, got: {alerts_res}"
    assert alerts_res["auditCount"] >= 10, f"Expected >= 10 audit rows on live site, got: {alerts_res}"
    print("[PASS] Live GitHub Pages Alerts & Audit Log verified.")


    # 3. Verify Blacklist View
    print("\n--- TEST 3: LIVE BLACKLIST CHECK ---")
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
    print(f"Live Blacklist Result: hasMatch={bl_res['hasMatch']}")
    assert bl_res["hasMatch"], "Expected match on live site blacklist check"
    print("[PASS] Live GitHub Pages Blacklist Check verified.")

    print("\n" + "=" * 80)
    print("ALL LIVE GITHUB PAGES CHECKS PASSED WITH 100% SUCCESS!")
    print("=" * 80)

    await client.close()


if __name__ == "__main__":
    asyncio.run(run_live_check())
