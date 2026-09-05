/**
 * dataSource.js — Stage 7 Data Layer
 *
 * This is the ONLY module permitted to make network or file requests.
 * No view file may call fetch() directly.
 *
 * STATIC_MODE controls the data source:
 *   false  → calls the Stage 6 FastAPI server at http://127.0.0.1:8000 (default for local dev and localhost demo)
 *   true   → reads precomputed JSON files from ./static-data/ (used ONLY by Stage 9 GitHub Pages export)
 *
 * Stage 9 is responsible for setting STATIC_MODE = true in the exported copy.
 * Never change it here.
 */

const STATIC_MODE = false;

const API_BASE = "http://127.0.0.1:8000";

/** Internal helper — live API fetch */
async function apiFetch(path) {
  const res = await fetch(API_BASE + path);
  if (!res.ok) throw new Error(`API error ${res.status} on ${path}`);
  return res.json();
}

/** Internal helper — static JSON file fetch */
async function staticFetch(filename) {
  const res = await fetch("./static-data/" + filename);
  if (!res.ok) throw new Error(`Static data error ${res.status} on ./static-data/${filename}`);
  return res.json();
}

let trajectoriesCache = null;

/**
 * getTrajectory(query, dateFrom, dateTo, role)
 * Returns trajectory sightings for a plate text or sighting_id.
 * Static mode: instant in-memory lookup from trajectories.json
 */
async function getTrajectory(query, dateFrom, dateTo, role = "supervisor") {
  if (STATIC_MODE) {
    if (!trajectoriesCache) {
      try {
        trajectoriesCache = await staticFetch("trajectories.json");
      } catch (e) {
        trajectoriesCache = {};
      }
    }
    const cleanQ = (query || "").trim().toUpperCase();
    const noSpaceQ = cleanQ.replace(/\s+/g, "");

    if (cleanQ && trajectoriesCache[cleanQ]) return trajectoriesCache[cleanQ];
    if (noSpaceQ && trajectoriesCache[noSpaceQ]) return trajectoriesCache[noSpaceQ];

    if (noSpaceQ.length >= 3) {
      for (const [k, traj] of Object.entries(trajectoriesCache)) {
        const cleanK = k.replace(/\s+/g, "").toUpperCase();
        if (cleanK.includes(noSpaceQ) || noSpaceQ.includes(cleanK)) {
          return traj;
        }
      }
    }
    return {
      query: query,
      role: role,
      match_count: 0,
      sightings: []
    };
  }
  const params = new URLSearchParams({ query, role });
  if (dateFrom) params.set("date_from", dateFrom);
  if (dateTo) params.set("date_to", dateTo);
  return apiFetch("/api/trajectory?" + params.toString());
}

/**
 * getHeatmap(dateFrom, dateTo)
 * Returns camera locations with sighting counts.
 * Static file: heatmap.json
 */
async function getHeatmap(dateFrom, dateTo) {
  if (STATIC_MODE) return staticFetch("heatmap.json");
  const params = new URLSearchParams();
  if (dateFrom) params.set("date_from", dateFrom);
  if (dateTo) params.set("date_to", dateTo);
  const qs = params.toString();
  return apiFetch("/api/heatmap" + (qs ? "?" + qs : ""));
}

/**
 * getZones()
 * Returns all restricted zones with center coordinates and radius.
 * Static file: zones.json
 */
async function getZones() {
  if (STATIC_MODE) return staticFetch("zones.json");
  return apiFetch("/api/zones");
}

/**
 * getCorridorBaseline()
 * Returns statistical corridor transit profiles for all camera pairs.
 * Static file: corridor-baseline.json
 */
async function getCorridorBaseline() {
  if (STATIC_MODE) return staticFetch("corridor-baseline.json");
  return apiFetch("/api/corridor-baseline");
}

/**
 * getTrafficTrend(dateFrom, dateTo)
 * Returns hourly sighting counts (24 buckets) for the traffic trend chart.
 * Static file: traffic-trend.json
 */
async function getTrafficTrend(dateFrom, dateTo) {
  if (STATIC_MODE) return staticFetch("traffic-trend.json");
  const params = new URLSearchParams();
  if (dateFrom) params.set("date_from", dateFrom);
  if (dateTo) params.set("date_to", dateTo);
  const qs = params.toString();
  return apiFetch("/api/traffic-trend" + (qs ? "?" + qs : ""));
}

/**
 * checkBlacklist(plate, role)
 * Fuzzy-checks a plate string against the blacklist.
 * Static file: blacklist-check.json
 */
async function checkBlacklist(plate, role = "supervisor") {
  if (STATIC_MODE) return staticFetch("blacklist-check.json");
  const params = new URLSearchParams({ plate, role });
  return apiFetch("/api/blacklist/check?" + params.toString());
}

/**
 * getAlerts()
 * Returns all system alerts most recent first.
 * Static file: alerts.json
 */
async function getAlerts() {
  if (STATIC_MODE) return staticFetch("alerts.json");
  return apiFetch("/api/alerts");
}

/**
 * getAuditLog()
 * Returns all operator/supervisor search audit log entries.
 * Static file: audit-log.json
 */
async function getAuditLog() {
  if (STATIC_MODE) return staticFetch("audit-log.json");
  return apiFetch("/api/audit-log");
}

/**
 * getVehicles()
 * Returns all distinct registered and detected vehicle plates.
 * Static file: vehicles.json
 */
async function getVehicles() {
  if (STATIC_MODE) return staticFetch("vehicles.json");
  return apiFetch("/api/vehicles");
}

/**
 * getCameras()
 * Returns all 8 camera node metadata and live video feed URLs.
 * Static file: cameras.json
 */
async function getCameras() {
  if (STATIC_MODE) return staticFetch("cameras.json");
  return apiFetch("/api/cameras");
}
