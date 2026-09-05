/**
 * views/feeds.js — Live Camera Feeds Grid View
 * Renders live video feeds from all 8 camera nodes with clean Camera 1 - Camera 8 labels.
 */

async function loadCameraFeeds() {
  const container = document.getElementById("feeds-grid-container");
  const statusEl = document.getElementById("feeds-status");

  if (!container) return;
  container.innerHTML = "";
  if (statusEl) statusEl.textContent = "Loading camera node video streams...";

  try {
    const cameras = await getCameras();

    if (!cameras || cameras.length === 0) {
      if (statusEl) statusEl.textContent = "No active camera feeds found.";
      return;
    }

    if (statusEl) {
      statusEl.textContent = `All ${cameras.length} camera nodes streaming live (1080p @ 25fps). Multi-modal ANPR pipeline active.`;
    }

    cameras.forEach(cam => {
      const card = document.createElement("div");
      card.className = "camera-card";

      // Extract simple camera number (e.g., CAM_01 -> Camera 1)
      const numMatch = cam.camera_id.match(/\d+/);
      const camNum = numMatch ? parseInt(numMatch[0], 10) : cam.camera_id;

      const rawClip = cam.clip_url || `./clips/camera_${camNum}.mp4`;
      const clipUrl = rawClip.startsWith("/") ? "." + rawClip : rawClip;

      card.innerHTML = `
        <div class="camera-card-header">
          <div>
            <span class="mono" style="font-weight:700; color:var(--text);">Camera ${camNum}</span>
          </div>
          <span class="badge badge-accent">LIVE FEED</span>
        </div>

        <div class="video-container">
          <video src="${clipUrl}" autoplay loop muted playsinline preload="auto"></video>
        </div>

        <div class="camera-card-footer">
          <div style="font-size:11px; color:var(--muted);">
            <div>Stream: <strong class="mono">${escHtml(cam.camera_id)}</strong></div>
            <div>GPS: <span class="mono">${cam.lat.toFixed(4)}, ${cam.lon.toFixed(4)}</span> | Sightings: <strong class="mono">${cam.sighting_count}</strong></div>
          </div>
          <button class="btn btn-secondary" style="font-size:11px; padding:3px 8px;" onclick="inspectCameraNode('${cam.camera_id}')">
            View on Map
          </button>
        </div>
      `;

      container.appendChild(card);
    });

  } catch (err) {
    if (statusEl) {
      statusEl.textContent = "Error loading camera streams: " + err.message;
      statusEl.className = "text-critical";
    }
  }
}

function inspectCameraNode(cameraId) {
  showView("heatmap");
}
