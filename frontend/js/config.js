/**
 * config.js — Shared frontend configuration
 *
 * MAP_API_KEY: Set to a MapTiler or Mapbox API key to use a muted/greyscale
 * (Positron-style) tile layer. Leave empty ("") to fall back to OpenStreetMap
 * tiles with a CSS grayscale filter applied automatically. The fallback is
 * always safe and never blocks the build.
 */
const MAP_API_KEY = "";

/**
 * Map tile configuration.
 * Used by both the Trajectory Search map and the Heatmap view.
 * Returns a Leaflet TileLayer configured for the appropriate source.
 */
function createTileLayer() {
  if (MAP_API_KEY) {
    // MapTiler Positron-style greyscale basemap
    return L.tileLayer(
      `https://api.maptiler.com/maps/positron/{z}/{x}/{y}.png?key=${MAP_API_KEY}`,
      {
        attribution: '&copy; <a href="https://www.maptiler.com/">MapTiler</a> &copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>',
        maxZoom: 19,
        tileSize: 512,
        zoomOffset: -1,
      }
    );
  }
  // OpenStreetMap fallback with grayscale CSS filter applied via className
  return L.tileLayer(
    "https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png",
    {
      attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
      maxZoom: 19,
      className: "map-tiles-muted",
    }
  );
}

// Chennai city centre — default map view
const MAP_DEFAULT_CENTER = [13.0827, 80.2707];
const MAP_DEFAULT_ZOOM = 13;
