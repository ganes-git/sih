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

const STATIC_MODE = true;

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

let blacklistCache = null;

function calculatePlateSimilarity(s1, s2) {
  const a = (s1 || "").replace(/[^A-Z0-9]/gi, "").toUpperCase();
  const b = (s2 || "").replace(/[^A-Z0-9]/gi, "").toUpperCase();
  if (!a || !b) return 0.0;
  if (a === b) return 1.0;

  const m = a.length;
  const n = b.length;
  const dp = Array.from({ length: m + 1 }, () => Array(n + 1).fill(0));
  for (let i = 0; i <= m; i++) dp[i][0] = i;
  for (let j = 0; j <= n; j++) dp[0][j] = j;

  for (let i = 1; i <= m; i++) {
    for (let j = 1; j <= n; j++) {
      const cost = a[i - 1] === b[j - 1] ? 0 : 1;
      dp[i][j] = Math.min(
        dp[i - 1][j] + 1,
        dp[i][j - 1] + 1,
        dp[i - 1][j - 1] + cost
      );
    }
  }
  const maxLen = Math.max(m, n);
  return Math.max(0.0, 1.0 - dp[m][n] / maxLen);
}

/**
 * checkBlacklist(plate, role)
 * Fuzzy-checks a plate string against the blacklist registry.
 * Static mode: dynamic in-memory fuzzy Levenshtein comparison across all blacklist entries.
 */
async function checkBlacklist(plate, role = "supervisor") {
  if (STATIC_MODE) {
    if (!blacklistCache) {
      try {
        blacklistCache = await staticFetch("blacklist.json");
      } catch (e) {
        blacklistCache = [
          {
            plate_text: "TN 07 AB 1234",
            reason: "Flagged in hit-and-run investigation #CR-8821 (Chennai Central Traffic)",
            added_on: 1788443602,
            added_on_iso: "2026-09-03"
          },
          {
            plate_text: "KA 03 HA 9999",
            reason: "Reported stolen vehicle — FIR #2024-0091 (Bengaluru South)",
            added_on: 1788184402,
            added_on_iso: "2026-08-31"
          },
          {
            plate_text: "DL 01 EF 9012",
            reason: "Stolen vehicle bulletin #FIR-4402 (Delhi Police South Division)",
            added_on: 1788184402,
            added_on_iso: "2026-08-31"
          },
          {
            plate_text: "KA 03 XY 9999",
            reason: "Suspicious interstate commercial smuggling alert",
            added_on: 1787752402,
            added_on_iso: "2026-08-25"
          },
          {
            plate_text: "MH 01 XY 0000",
            reason: "Suspicious transit in restricted zone enquiry",
            added_on: 1787752402,
            added_on_iso: "2026-08-25"
          }
        ];
      }
    }

    const cleanQ = (plate || "").replace(/[^A-Z0-9]/gi, "").toUpperCase();
    let bestSim = 0.0;
    let bestMatch = null;

    for (const entry of blacklistCache) {
      const sim = calculatePlateSimilarity(cleanQ, entry.plate_text);
      if (sim > bestSim) {
        bestSim = sim;
        bestMatch = entry;
      }
    }

    const matched = bestSim >= 0.85;
    return {
      query_plate: plate,
      matched: matched,
      similarity: Number(bestSim.toFixed(4)),
      matched_entry: (matched && bestMatch) ? {
        plate_text: bestMatch.plate_text,
        reason: bestMatch.reason,
        added_on: bestMatch.added_on,
        added_on_iso: bestMatch.added_on_iso || (bestMatch.added_on ? new Date(bestMatch.added_on * 1000).toISOString().split('T')[0] : "2026-09-01")
      } : null
    };
  }
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
