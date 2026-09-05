/**
 * views/traffic.js — Traffic Trends view
 * Stage 7:
 * - Calls dataSource.getTrafficTrend() → renders an inline SVG bar chart.
 *   No charting library. Bars are DOM elements sized proportionally to counts.
 * - Calls dataSource.getCorridorBaseline() → renders a plain HTML table.
 *   Seed rows displayed in muted text colour to indicate they are not real observations.
 */

async function loadTrafficTrends() {
  const chartEl = document.getElementById("traffic-chart");
  const labelsEl = document.getElementById("traffic-chart-labels");
  const statusEl = document.getElementById("traffic-status");
  const corridorTbody = document.getElementById("corridor-table-body");

  statusEl.textContent = "Loading...";
  chartEl.innerHTML = "";
  labelsEl.innerHTML = "";
  corridorTbody.innerHTML = "";

  try {
    const [trend, corridors] = await Promise.all([getTrafficTrend(), getCorridorBaseline()]);

    // --- Bar chart ---
    if (!trend || trend.length === 0) {
      statusEl.textContent = "No traffic trend data available.";
    } else {
      const maxCount = Math.max(...trend.map(t => t.sighting_count), 1);

      trend.forEach(bucket => {
        const pct = (bucket.sighting_count / maxCount) * 100;

        const bar = document.createElement("div");
        bar.className = "chart-bar";
        bar.style.height = Math.max(pct, 2) + "%";
        bar.title = `${bucket.hour_bucket}: ${bucket.sighting_count} sighting(s)`;
        chartEl.appendChild(bar);

        const lbl = document.createElement("div");
        lbl.className = "chart-label";
        // Show every 3rd label to avoid overlap
        lbl.textContent = bucket.hour % 3 === 0 ? bucket.hour_bucket : "";
        labelsEl.appendChild(lbl);
      });

      const total = trend.reduce((s, t) => s + t.sighting_count, 0);
      statusEl.textContent = `${total} total sighting(s) across 24-hour window.`;
    }

    // --- Corridor baseline table ---
    if (!corridors || corridors.length === 0) {
      corridorTbody.innerHTML = `<tr><td colspan="6" class="empty-state">No corridor baseline data.</td></tr>`;
    } else {
      corridors.forEach(c => {
        const row = document.createElement("tr");
        if (c.source === "seed") row.className = "row-seed";
        row.innerHTML = `
          <td class="mono">${escHtml(c.camera_from)}</td>
          <td class="mono">${escHtml(c.camera_to)}</td>
          <td class="mono">${escHtml(String(c.distance_km))}</td>
          <td class="mono">${escHtml(String(c.mean_transit_seconds))} s</td>
          <td class="mono">${escHtml(String(c.avg_speed_kmh))} km/h</td>
          <td class="mono">${escHtml(String(c.sample_count))}</td>
          <td>${escHtml(c.source)}</td>
        `;
        corridorTbody.appendChild(row);
      });
    }

  } catch (err) {
    statusEl.textContent = "Error: " + err.message;
    statusEl.className = "text-critical";
  }
}
