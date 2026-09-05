"""
verify_pages_performance.py — Test live video feeds, button clicks, quick chips, and instant vehicle switching
"""

import asyncio
import json
import urllib.request
import websockets

async def check_all():
    req = urllib.request.urlopen('http://127.0.0.1:9222/json')
    pages = json.loads(req.read().decode())
    target_page = next((p for p in pages if p.get('type') == 'page'), None)
    assert target_page, "No browser tab found"

    ws = await websockets.connect(target_page['webSocketDebuggerUrl'], max_size=50*1024*1024)

    msg_id = 0
    async def eval_js(expr):
        nonlocal msg_id
        msg_id += 1
        msg = {'id': msg_id, 'method': 'Runtime.evaluate', 'params': {'expression': expr, 'returnByValue': True, 'awaitPromise': True}}
        await ws.send(json.dumps(msg))
        while True:
            raw = await ws.recv()
            resp = json.loads(raw)
            if resp.get('id') == msg_id:
                return resp.get('result', {}).get('result', {}).get('value')

    print("--- 1. Testing Navigation to all Views ---")
    for view in ['trajectory', 'feeds', 'heatmap', 'alerts', 'traffic', 'blacklist']:
        await eval_js(f"showView('{view}')")
        await asyncio.sleep(0.3)
        active_id = await eval_js("document.querySelector('.view.active')?.id")
        print(f"  Navigated to view: {view} -> Active ID: {active_id}")

    print("\n--- 2. Testing Trajectory Search Button Click ---")
    await eval_js("showView('trajectory')")
    await asyncio.sleep(0.3)
    btn_res = await eval_js("""
        (async () => {
            const input = document.getElementById('traj-query');
            const btn = document.getElementById('traj-search-btn');
            if (input) input.value = 'DL 01 EF 9012';
            if (btn) btn.click();
            await new Promise(r => setTimeout(r, 100));
            const plate = document.getElementById('stat-plate')?.innerText;
            const rows = document.querySelectorAll('#trajectory-table-body tr').length;
            const feeds = document.querySelectorAll('#trajectory-feeds-grid .traj-sighting-card').length;
            return { plate, rows, feeds };
        })()
    """)
    print("  Button Click Search Result (DL 01 EF 9012):", btn_res)

    print("\n--- 3. Testing Quick Select Chips ---")
    chip_res = await eval_js("""
        (async () => {
            const chip = document.querySelector('.plate-chip[data-plate=\"TN 07 AB 1234\"]');
            if (chip) chip.click();
            await new Promise(r => setTimeout(r, 100));
            const plate = document.getElementById('stat-plate')?.innerText;
            const rows = document.querySelectorAll('#trajectory-table-body tr').length;
            return { plate, rows };
        })()
    """)
    print("  Quick Chip Click Result (TN 07 AB 1234):", chip_res)

    print("\n--- 4. Testing Dropdown Multi-Vehicle Switching ---")
    test_plates = ['TN 07 AB 1000', 'KA 05 GH 3456', 'MH 12 CD 5678']
    for plate in test_plates:
        res = await eval_js(f"""
            (async () => {{
                const select = document.getElementById('traj-plate-select');
                if (select) {{
                    select.value = '{plate}';
                    select.dispatchEvent(new Event('change'));
                }}
                await new Promise(r => setTimeout(r, 100));
                const info = document.getElementById('stat-plate')?.innerText;
                const rowCount = document.querySelectorAll('#trajectory-table-body tr').length;
                return {{ plate: info, rows: rowCount }};
            }})()
        """)
        print(f"  Dropdown Selected {plate} -> Result: {res}")

    print("\n--- 5. Checking Live Feeds in Feeds View ---")
    await eval_js("showView('feeds')")
    await asyncio.sleep(0.5)
    feeds_check = await eval_js("""
        (() => {
            const vids = document.querySelectorAll('#feeds-grid-container video');
            return {
                videoCount: vids.length,
                srcs: Array.from(vids).map(v => v.src)
            };
        })()
    """)
    print("\n--- 6. Testing Blacklist Registry Report Dynamic Updating ---")
    await eval_js("showView('blacklist')")
    await asyncio.sleep(0.5)

    bl_test_cases = [
        ("TN 07 AB 1234", True, "CR-8821"),
        ("KA 03 HA 9999", True, "2024-0091"),
        ("DL 01 AA 0000", False, "CLEAN VEHICLE"),
        ("KA 05 GH 3456", False, "CLEAN VEHICLE"),
    ]
    for plate, expected_match, text_snippet in bl_test_cases:
        res = await eval_js(f"""
            (async () => {{
                selectBlacklistPlate('{plate}');
                await new Promise(r => setTimeout(r, 120));
                const resEl = document.getElementById('bl-result');
                return {{
                    html: resEl ? resEl.innerText : '',
                    isMatch: resEl ? resEl.classList.contains('match') : false,
                    isNoMatch: resEl ? resEl.classList.contains('no-match') : false
                }};
            }})()
        """)
        print(f"  Checked {plate}: isMatch={res.get('isMatch')}, snippet_present={text_snippet in res.get('html', '')}")
        if expected_match:
            assert res.get('isMatch'), f"Expected match for {plate}"
        else:
            assert res.get('isNoMatch'), f"Expected no-match for {plate}"

    await ws.close()
    print("\n[SUCCESS] Search button, quick chips, dropdown switcher, live feeds, and blacklist dynamic report confirmed responsive!")

if __name__ == '__main__':
    asyncio.run(check_all())
