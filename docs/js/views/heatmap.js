/**
 * views/heatmap.js — Camera Sighting Density Heatmap view
 * Stage 7: calls dataSource.getHeatmap() and getZones().
 * Circle markers sized/coloured by sighting count.
 * Restricted zones drawn as dashed circles in the critical accent colour.
 */

let heatmapMap = null;
let heatmapLayerGroup = null;

function initHeatmapView() {
  if (heatmapMap) return;
  heatmapMap = L.map("heatmap-map").setView(MAP_DEFAULT_CENTER, MAP_DEFAULT_ZOOM);
  createTileLayer().addTo(heatmapMap);
  heatmapLayerGroup = L.layerGroup().addTo(heatmapMap);
}

async function loadHeatmap() {
  const statusEl = document.getElementById("heatmap-status");
  statusEl.textContent = "Loading...";
  heatmapLayerGroup.clearLayers();

  try {
    const [cams, zones] = await Promise.all([getHeatmap(), getZones()]);

    if (!cams || cams.length === 0) {
      statusEl.textContent = "No sighting data available.";
      return;
    }

    const maxCount = Math.max(...cams.map(c => c.sighting_count), 1);

    cams.forEach(cam => {
      const ratio = cam.sighting_count / maxCount;
      // Colour: interpolate between background (#FAFAF8) and dark forest green (#2F5233)
      // expressed as opacity so we don't do gradients — just vary opacity on the accent fill
      const radius = 8 + Math.round(ratio * 20);
      const opacity = 0.15 + ratio * 0.80;

      const marker = L.circleMarker([cam.lat, cam.lon], {
        radius,
        fillColor: "#2F5233",
        color: "#1F1F1F",
        weight: 1,
        fillOpacity: opacity,
      });

      marker.bindTooltip(
        `<span class="mono">${escHtml(cam.camera_id)}</span><br>` +
        `${escHtml(cam.name)}<br>` +
        `${cam.sighting_count} sighting(s)`,
        { sticky: true }
      );
      marker.addTo(heatmapLayerGroup);
    });

    // Draw restricted zones as dashed circles in critical accent colour
    zones.forEach(zone => {
      const circle = L.circle([zone.center_lat, zone.center_lon], {
        radius: zone.radius_meters,
        color: "#B3262A",
        weight: 1.5,
        dashArray: "5, 5",
        fill: false,
      });
      circle.bindTooltip(
        `<strong>${escHtml(zone.name)}</strong><br>` +
        `Restricted: ${escHtml(zone.reason)}`,
        { sticky: true }
      );
      circle.addTo(heatmapLayerGroup);
    });

    // Fit map to camera bounds
    const latlngs = cams.map(c => [c.lat, c.lon]);
    if (latlngs.length > 1) heatmapMap.fitBounds(L.latLngBounds(latlngs).pad(0.1));
    statusEl.textContent = `${cams.length} camera(s) shown. ${zones.length} restricted zone(s) outlined.`;

  } catch (err) {
    statusEl.textContent = "Error loading data: " + err.message;
    statusEl.className = "text-critical";
  }
}
