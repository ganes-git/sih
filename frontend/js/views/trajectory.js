/**
 * views/trajectory.js — Multi-Camera Vehicle Trajectory Reconstruction
 * - Vehicle Dropdown List: Lists ALL available vehicles across network
 * - Synchronized Camera Feeds: Live video feeds along vehicle's trajectory path (Camera 1 - 8)
 * - Clean Camera labels without place names
 * - High-visibility dual-layer route polylines
 * - KPI summary cards for identified vehicle, hop count, route distance, and timing anomaly status
 */

let trajectoryMap = null;
let trajectoryLayerGroup = null;

async function populateVehiclesDropdown() {
  const selectEl = document.getElementById("traj-plate-select");
  if (!selectEl) return;

  try {
    const vehicles = await getVehicles();
    if (!vehicles || vehicles.length === 0) return;

    selectEl.innerHTML = `<option value="">-- Select a Tracked Vehicle (${vehicles.length} in Network) --</option>`;

    vehicles.forEach(v => {
      const opt = document.createElement("option");
      opt.value = v.plate_text;
      const camList = v.cameras.map(c => {
        const match = c.match(/\d+/);
        return match ? `Camera ${parseInt(match[0], 10)}` : c;
      }).join(" → ");
      const label = `${v.plate_text} — ${v.sighting_count} sighting(s) [${camList}]`;
      opt.textContent = label;
      selectEl.appendChild(opt);
    });

    // Set initial selection
    selectEl.value = "KA 05 GH 3456";
  } catch (e) {
    console.error("Failed to populate vehicles dropdown", e);
  }
}

function initTrajectoryView() {
  if (trajectoryMap) {
    setTimeout(() => {
      trajectoryMap.invalidateSize();
    }, 100);
    return;
  }
  trajectoryMap = L.map("trajectory-map").setView(MAP_DEFAULT_CENTER, MAP_DEFAULT_ZOOM);
  createTileLayer().addTo(trajectoryMap);
  trajectoryLayerGroup = L.layerGroup().addTo(trajectoryMap);

  populateVehiclesDropdown();

  setTimeout(() => {
    trajectoryMap.invalidateSize();
  }, 100);
}

function renderTrajectory(data) {
  const tableBody = document.getElementById("trajectory-table-body");
  const resultInfo = document.getElementById("trajectory-result-info");
  const statsGrid = document.getElementById("trajectory-stats-grid");
  const feedsSection = document.getElementById("trajectory-feeds-section");
  const feedsGrid = document.getElementById("trajectory-feeds-grid");

  if (!trajectoryMap) {
    initTrajectoryView();
  }

  trajectoryLayerGroup.clearLayers();
  tableBody.innerHTML = "";
  if (feedsGrid) feedsGrid.innerHTML = "";

  if (!data || !data.sightings || data.sightings.length === 0) {
    resultInfo.textContent = "No sightings found for query: " + (data ? data.query : "");
    resultInfo.className = "empty-state";
    if (statsGrid) statsGrid.style.display = "none";
    if (feedsSection) feedsSection.style.display = "none";
    return;
  }

  const sightings = data.sightings;
  resultInfo.textContent = `${data.match_count} sighting(s) matched across city camera network.`;
  resultInfo.className = "text-muted";

  if (statsGrid) statsGrid.style.display = "grid";
  if (feedsSection) feedsSection.style.display = "block";

  // Calculate summary metrics
  let totalDistKm = 0.0;
  let maxZScore = 0.0;
  let hasTimingAnomaly = false;
  let camerasVisited = new Set();

  sightings.forEach(s => {
    camerasVisited.add(s.camera_id);
    if (s.hop) {
      totalDistKm += (s.hop.distance_km || 0);
      if (s.hop.timing_anomaly_score !== null) {
        if (Math.abs(s.hop.timing_anomaly_score) > Math.abs(maxZScore)) {
          maxZScore = s.hop.timing_anomaly_score;
        }
      }
      if (s.hop.is_timing_anomaly) {
        hasTimingAnomaly = true;
      }
    }
  });

  // Populate KPI cards
  const statPlate = document.getElementById("stat-plate");
  const statConfidence = document.getElementById("stat-confidence");
  const statHops = document.getElementById("stat-hops");
  const statCameras = document.getElementById("stat-cameras");
  const statRoute = document.getElementById("stat-route");
  const statDistance = document.getElementById("stat-distance");
  const statStatus = document.getElementById("stat-status");
  const statZScore = document.getElementById("stat-zscore");

  if (statPlate) statPlate.textContent = sightings[0].plate_text || "Unconfirmed Plate (Visual Re-ID)";
  if (statConfidence) {
    const conf = sightings[0].plate_confidence;
    statConfidence.textContent = conf !== null && conf !== undefined
      ? `Plate Confidence: ${(conf * 100).toFixed(1)}%`
      : "Visual Re-ID via OpenCLIP";
  }
  if (statHops) statHops.textContent = `${sightings.length} Sightings`;
  if (statCameras) statCameras.textContent = `${camerasVisited.size} Unique Cameras`;
  if (statRoute) {
    if (sightings.length >= 2) {
      const c1 = sightings[0].camera_id.match(/\d+/) ? `Camera ${parseInt(sightings[0].camera_id.match(/\d+/)[0], 10)}` : sightings[0].camera_id;
      const c2 = sightings[sightings.length - 1].camera_id.match(/\d+/) ? `Camera ${parseInt(sightings[sightings.length - 1].camera_id.match(/\d+/)[0], 10)}` : sightings[sightings.length - 1].camera_id;
      statRoute.textContent = `${c1} → ${c2}`;
    } else {
      const c = sightings[0].camera_id.match(/\d+/) ? `Camera ${parseInt(sightings[0].camera_id.match(/\d+/)[0], 10)}` : sightings[0].camera_id;
      statRoute.textContent = c;
    }
  }
  if (statDistance) statDistance.textContent = `${totalDistKm.toFixed(2)} km Total Distance`;
  if (statStatus) {
    if (hasTimingAnomaly) {
      statStatus.innerHTML = `<span class="badge badge-warn">Timing Anomaly</span>`;
    } else {
      statStatus.innerHTML = `<span class="badge badge-accent">Normal Transit</span>`;
    }
  }
  if (statZScore) {
    statZScore.textContent = `Max z-score: ${maxZScore.toFixed(2)}`;
  }

  // Build Synchronized Camera Feeds & Map Waypoints
  const latlngs = [];
  sightings.forEach((s, idx) => {
    const latlng = [s.lat, s.lon];
    latlngs.push(latlng);

    const isOrigin = (idx === 0);
    const isDest = (idx === sightings.length - 1 && sightings.length > 1);
    const labelTag = isOrigin ? " [ORIGIN]" : (isDest ? " [DEST]" : "");
    const ts = s.timestamp_iso || new Date(s.timestamp * 1000).toISOString();
    
    const camMatch = s.camera_id.match(/\d+/);
    const camNum = camMatch ? parseInt(camMatch[0], 10) : (idx + 1);
    const camTitle = `Camera ${camNum}`;
    const clipUrl = s.clip_url || `/clips/camera_${camNum}.mp4`;

    // 1. Custom numbered map waypoint
    const waypointIcon = L.divIcon({
      className: "custom-waypoint",
      html: `<div class="waypoint-icon ${hasTimingAnomaly && idx > 0 ? 'anomalous' : ''}">${idx + 1}</div>`,
      iconSize: [24, 24],
      iconAnchor: [12, 12],
    });

    const marker = L.marker(latlng, { icon: waypointIcon });

    const popupContent = `
      <div style="font-size:12px; line-height:1.4; min-width:220px;">
        <strong>Stop ${idx + 1}: ${camTitle}${labelTag}</strong><br>
        <span class="mono">${escHtml(ts)}</span><br>
        <div style="margin-top:6px; background:#000; border-radius:2px; overflow:hidden;">
          <video src="${clipUrl}" autoplay loop muted playsinline style="width:100%; height:120px; object-fit:cover; display:block;"></video>
        </div>
        <div style="margin-top:4px; font-size:11px;">
          ${s.plate_text ? `Plate: <span class="mono"><strong>${escHtml(s.plate_text)}</strong></span>` : '<em>Plate unconfirmed (Visual Re-ID)</em>'}
        </div>
      </div>
    `;

    marker.bindPopup(popupContent, { maxWidth: 280 });
    marker.bindTooltip(`Stop ${idx + 1}: ${camTitle}${labelTag}`, { direction: "top", offset: [0, -10] });
    marker.addTo(trajectoryLayerGroup);

    // 2. Trajectory Sighting Feed Card in the Synchronized Grid
    if (feedsGrid) {
      const card = document.createElement("div");
      card.className = `traj-sighting-card ${hasTimingAnomaly && idx > 0 ? 'anomalous' : ''}`;
      card.innerHTML = `
        <div class="traj-sighting-header">
          <div>
            <span class="mono" style="font-weight:700;">Stop ${idx + 1}: ${camTitle}</span>
            <span class="text-muted">${labelTag}</span>
          </div>
          <span class="badge ${isOrigin ? 'badge-accent' : (isDest ? (hasTimingAnomaly ? 'badge-warn' : 'badge-accent') : 'badge-muted')}">
            ${isOrigin ? 'ORIGIN' : (isDest ? 'DESTINATION' : 'WAYPOINT')}
          </span>
        </div>

        <div class="traj-sighting-video">
          <video src="${clipUrl}" autoplay loop muted playsinline></video>
        </div>

        <div class="traj-sighting-meta">
          <div>Node: <strong class="mono">${escHtml(s.camera_id)}</strong></div>
          <div>Time: <span class="mono">${escHtml(ts)}</span></div>
          <div>Plate: ${s.plate_text ? `<span class="mono"><strong>${escHtml(s.plate_text)}</strong></span>` : '<span class="badge badge-muted">Visual Re-ID</span>'}</div>
        </div>
      `;
      feedsGrid.appendChild(card);
    }
  });

  // Dual-layer polyline for high contrast
  if (latlngs.length > 1) {
    L.polyline(latlngs, {
      color: "#1F1F1F",
      weight: 6,
      opacity: 0.9,
    }).addTo(trajectoryLayerGroup);

    const coreColor = hasTimingAnomaly ? "#C98A1E" : "#2F5233";
    L.polyline(latlngs, {
      color: coreColor,
      weight: 3.5,
      opacity: 1.0,
      dashArray: hasTimingAnomaly ? "6, 6" : undefined,
    }).addTo(trajectoryLayerGroup);

    trajectoryMap.fitBounds(L.latLngBounds(latlngs).pad(0.25));
  } else if (latlngs.length === 1) {
    trajectoryMap.setView(latlngs[0], 14);
  }

  // Force map size refresh
  setTimeout(() => {
    if (trajectoryMap) trajectoryMap.invalidateSize();
  }, 150);

  // Build hop table
  sightings.forEach((s, idx) => {
    const inboundHop = idx > 0 ? sightings[idx - 1].hop : null;
    const ts = s.timestamp_iso || new Date(s.timestamp * 1000).toISOString();
    const camMatch = s.camera_id.match(/\d+/);
    const camNum = camMatch ? parseInt(camMatch[0], 10) : (idx + 1);
    const camTitle = `Camera ${camNum}`;

    const plateLabel = s.plate_text
      ? `<span class="mono"><strong>${escHtml(s.plate_text)}</strong></span>`
      : `<span class="badge badge-muted">Unread (Visual Re-ID)</span>`;

    const row = document.createElement("tr");

    if (idx === 0 || !inboundHop) {
      row.innerHTML = `
        <td><strong class="mono">${camTitle}</strong> <span class="badge badge-muted" style="font-size:10px; margin-left:4px;">ORIGIN</span></td>
        <td class="mono">${escHtml(ts)}</td>
        <td>${plateLabel}</td>
        <td class="mono">${s.plate_confidence !== null && s.plate_confidence !== undefined ? s.plate_confidence.toFixed(4) : "—"}</td>
        <td class="mono">—</td>
        <td class="mono">—</td>
        <td class="mono">—</td>
        <td class="mono">—</td>
      `;
    } else {
      let anomalyBadge = "";
      if (inboundHop.is_timing_anomaly) {
        anomalyBadge = ` <span class="badge badge-warn" style="font-size:10px; margin-left:4px;">TIMING ANOMALY</span>`;
      }

      const zScoreVal = inboundHop.timing_anomaly_score;
      const zScoreStr = (zScoreVal !== null && zScoreVal !== undefined)
        ? `${zScoreVal > 0 ? "+" : ""}${zScoreVal.toFixed(2)}${anomalyBadge}`
        : "—";

      const visScore = inboundHop.visual_score ?? inboundHop.visual_similarity_score;
      const transitScore = inboundHop.transit_score ?? inboundHop.transit_feasibility_score;
      const compScore = inboundHop.composite_score ?? inboundHop.composite_match_score;

      row.innerHTML = `
        <td><strong class="mono">${camTitle}</strong> <span class="badge badge-accent" style="font-size:10px; margin-left:4px;">HOP ${idx}</span></td>
        <td class="mono">${escHtml(ts)}</td>
        <td>${plateLabel}</td>
        <td class="mono">${s.plate_confidence !== null && s.plate_confidence !== undefined ? s.plate_confidence.toFixed(4) : "—"}</td>
        <td class="mono">${visScore !== null && visScore !== undefined ? Number(visScore).toFixed(4) : "—"}</td>
        <td class="mono">${transitScore !== null && transitScore !== undefined ? Number(transitScore).toFixed(4) : "—"}</td>
        <td class="mono" style="font-weight:700; color:var(--accent);">${compScore !== null && compScore !== undefined ? Number(compScore).toFixed(4) : "—"}</td>
        <td class="mono">${zScoreStr}</td>
      `;
    }

    tableBody.appendChild(row);
  });
}

