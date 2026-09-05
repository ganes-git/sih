import urllib.request
import json
import asyncio
import websockets

async def main():
    try:
        resp = urllib.request.urlopen("http://127.0.0.1:9222/json")
        tabs = json.loads(resp.read().decode("utf-8"))
        page_tab = next(t for t in tabs if t.get("type") == "page" and "8000" in t.get("url", ""))
        ws = await websockets.connect(page_tab["webSocketDebuggerUrl"])

        msg_id = 0
        async def send(method, params=None):
            nonlocal msg_id
            msg_id += 1
            cur_id = msg_id
            await ws.send(json.dumps({"id": cur_id, "method": method, "params": params or {}}))
            while True:
                r = json.loads(await ws.recv())
                if r.get("id") == cur_id:
                    return r.get("result", {})

        print("Hard reloading page in browser...")
        await send("Page.reload", {"ignoreCache": True})
        await asyncio.sleep(2.5)

        # Click on Live Camera Feeds
        await send("Runtime.evaluate", {"expression": 'document.querySelector("[data-view=\'feeds\']").click()'})
        await asyncio.sleep(2.5)

        # Check video states
        res = await send("Runtime.evaluate", {
            "expression": """
            (function() {
                const videos = Array.from(document.querySelectorAll('video'));
                return videos.map((v, i) => ({
                    index: i,
                    id: v.closest('.camera-card') ? v.closest('.camera-card').querySelector('.camera-card-header span').textContent : 'sighting_or_popup',
                    src: v.src || (v.querySelector('source') ? v.querySelector('source').src : ''),
                    currentSrc: v.currentSrc,
                    paused: v.paused,
                    readyState: v.readyState,
                    networkState: v.networkState,
                    error: v.error ? { code: v.error.code, message: v.error.message } : null,
                    videoWidth: v.videoWidth,
                    videoHeight: v.videoHeight,
                    currentTime: v.currentTime,
                    duration: v.duration
                }));
            })()
            """,
            "returnByValue": True
        })

        print(json.dumps(res, indent=2))
    except Exception as e:
        print("Diagnosis error:", e)

if __name__ == "__main__":
    asyncio.run(main())
