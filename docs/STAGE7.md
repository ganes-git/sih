# Stage 7: Operator Dashboard (Static Frontend)

This stage builds the plain HTML/CSS/JS frontend at `/frontend/`. It has no build step and no framework. Every design decision is constrained by the locked rules in `DESIGN.md`.

---

## 1. File Structure

```
frontend/
  index.html               HTML shell — app layout, all five view sections
  css/
    main.css               Sole stylesheet; all design tokens defined as CSS custom properties
  js/
    config.js              MAP_API_KEY constant; createTileLayer() used by both maps
    dataSource.js          Data layer — only module permitted to call fetch()
    app.js                 Navigation, role state, event wiring
    views/
      trajectory.js        Trajectory Search view
      heatmap.js           Heatmap view
      blacklist.js         Blacklist view
      alerts.js            Alerts + Audit Log view
      traffic.js           Traffic Trends view
  tools/
    slop_check.py          DESIGN.md compliance checker
```

---

## 2. Data Layer (`frontend/js/dataSource.js`)

`dataSource.js` is the only file permitted to call `fetch()`. All view modules call its exported functions:

| Function | API path | Static file |
|:---|:---|:---|
| `getTrajectory(query, dateFrom, dateTo, role)` | `GET /api/trajectory` | `trajectory.json` |
| `getHeatmap(dateFrom, dateTo)` | `GET /api/heatmap` | `heatmap.json` |
| `getZones()` | `GET /api/zones` | `zones.json` |
| `getCorridorBaseline()` | `GET /api/corridor-baseline` | `corridor-baseline.json` |
| `getTrafficTrend(dateFrom, dateTo)` | `GET /api/traffic-trend` | `traffic-trend.json` |
| `checkBlacklist(plate, role)` | `GET /api/blacklist/check` | `blacklist-check.json` |
| `getAlerts()` | `GET /api/alerts` | `alerts.json` |
| `getAuditLog()` | `GET /api/audit-log` | `audit-log.json` |

`const STATIC_MODE = false;` at the top of the file. Stage 9 sets it to `true` in the exported copy to serve GitHub Pages from the precomputed JSON files.

---

## 3. Design Contract Compliance

### Palette (exactly as specified in DESIGN.md)
```
--bg:       #FAFAF8   (background)
--text:     #1F1F1F   (primary text)
--muted:    #6B6B63   (muted text)
--border:   #E1DED6   (borders)
--accent:   #2F5233   (dark forest green — primary accent)
--warn:     #C98A1E   (amber — warning)
--critical: #B3262A   (red — critical)
```
No other colours are used. No blue, indigo, or purple anywhere.

### Typography
- UI text: `system-ui, -apple-system, "Segoe UI", sans-serif`
- Data values (plate numbers, coordinates, timestamps, scores, IDs): `ui-monospace, "SF Mono", "Cascadia Mono", Consolas, monospace`
- Inter, Roboto, and Arial are not named in any font stack.

### Shape & Motion
- `border-radius: 3px` throughout (maximum 4px per DESIGN.md)
- No `box-shadow`, no `backdrop-filter`
- Only `opacity` and `background-color` transitions at 150ms ease
- No `cubic-bezier` curves with overshoot

### Layout
- Left-hand navigation: five plain text buttons (Trajectory Search, Heatmap, Blacklist, Alerts, Traffic Trends)
- Role selector above nav: two plain text buttons "Operator" / "Supervisor"; active one underlined in `--accent`
- One content pane on the right; only the active view is visible (`display:none` / `display:block`)

### Map Tiles
- `const MAP_API_KEY = ""` in `config.js` (shared by both maps)
- If empty: OpenStreetMap tiles with CSS class `map-tiles-muted` applying `filter: grayscale(100%) contrast(0.88)` — automatically muted, never blocks the build
- If set: MapTiler Positron greyscale basemap

### Role Selector
- Demo-only UI simulation. No authentication, no session token, no real login.
- Documented in a `// DEMO-ONLY` comment in `app.js` and stated here.
- Default role on load: Operator.
- Role stored in plain JS variable `currentRole`, passed to `dataSource.js` functions that accept it.

### Tone of Copy
- Buttons: "Search", "Check" — not "Find Your Vehicle Instantly"
- Empty states: "No alerts in this range.", "No sighting data available." — not marketing copy
- Section labels are uppercase, factual, no emoji

---

## 4. View Summary

### Trajectory Search
- Search box + date range form
- Leaflet map: circle markers at each sighting location, connected by polyline in chronological order
- Table: one row per sighting with camera_id, timestamp, plate, plate_score, visual_score, transit_score, composite_score, timing_anomaly_score; anomaly badge shown when `is_timing_anomaly` or `is_path_rare` is flagged

### Heatmap
- Leaflet map with circle markers sized/filled by sighting density (dark forest green = high density)
- Restricted zones drawn as dashed red circles (`--critical` colour) with zone name as tooltip

### Blacklist
- Plate number search box
- Match result: red border + table with plate, reason, added_on, similarity when matched; muted plain text when not matched

### Alerts
- Plain HTML table: timestamp, alert_type (coloured: `--critical` for clone/blacklist; `--warn` for impossible_transit, zone_deviation, route_anomaly), sighting IDs, detail text
- Audit Log section: hidden in Operator mode; shown (loaded from `getAuditLog()`) only in Supervisor mode

### Traffic Trends
- Bar chart: 24 DOM `<div>` elements (`chart-bar`), heights proportional to hourly sighting counts; no charting library
- Corridor baseline table: camera_from, camera_to, distance_km, mean_transit_seconds, avg_speed_kmh, sample_count, source; seed rows displayed in `--muted` colour

---

## 5. DESIGN.md Compliance Check — Slop Checker Output

Checked using `frontend/tools/slop_check.py` which greps all `.html`, `.css`, and `.js` files for:
- `gradient`
- `backdrop-filter`
- `Inter` (deliberate font naming)
- `cubic-bezier` curves with overshoot values
- Hex colours in blue/indigo/purple range
- `border-radius` values above 4px
- `box-shadow`

**Command run:**
```powershell
& ".\backend\venv\Scripts\python.exe" frontend/tools/slop_check.py
```

**Output:**
```
SLOP CHECK: 0 violations. All 10 frontend files are clean.
```

Exit code: 0. All frontend files pass the compliance check.
