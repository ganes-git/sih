/**
 * app.js — Main application controller
 * Unified Single Console Mode:
 * - Direct access to all features (Trajectory Search, Live Feeds, Density Heatmap, Alerts & Audit Trail, Traffic Trends, Blacklist)
 * - Quick-select plate chips and vehicle dropdown selector
 * - Live Camera Feeds grid integration
 * - Auto-initialization and responsive map invalidation
 */

// Single Unified Mode with Full System Access
let currentRole = "supervisor";

// --- Utility ---
function escHtml(str) {
  if (str === null || str === undefined) return "";
  return String(str)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

// --- Navigation ---
let activeView = "trajectory";

function showView(viewName) {
  activeView = viewName;

  // Toggle nav buttons
  document.querySelectorAll(".nav-item").forEach(btn => {
    btn.classList.toggle("active", btn.dataset.view === viewName);
  });

  // Toggle view sections
  document.querySelectorAll(".view").forEach(el => {
    el.classList.toggle("active", el.id === `view-${viewName}`);
  });

  // View-specific lazy initialization
  if (viewName === "trajectory") {
    initTrajectoryView();
  } else if (viewName === "feeds") {
    loadCameraFeeds();
  } else if (viewName === "heatmap") {
    initHeatmapView();
    loadHeatmap();
    setTimeout(() => {
      if (heatmapMap) heatmapMap.invalidateSize();
    }, 150);
  } else if (viewName === "alerts") {
    loadAlerts();
  } else if (viewName === "traffic") {
    loadTrafficTrends();
  }
}

// --- Quick-select chips ---
function setupQuickSelect() {
  document.querySelectorAll(".quick-chip").forEach(chip => {
    chip.addEventListener("click", () => {
      const plate = chip.dataset.plate;
      const input = document.getElementById("trajectory-query");
      const selectEl = document.getElementById("traj-plate-select");
      if (input) input.value = plate;
      if (selectEl) selectEl.value = plate;
      doTrajectorySearch();
    });
  });
}

// --- Trajectory search trigger ---
async function doTrajectorySearch(queryOverride) {
  const input = document.getElementById("trajectory-query");
  const selectEl = document.getElementById("traj-plate-select");
  const dateFrom = document.getElementById("trajectory-from") ? document.getElementById("trajectory-from").value : "";
  const dateTo = document.getElementById("trajectory-to") ? document.getElementById("trajectory-to").value : "";

  const query = (queryOverride !== undefined && queryOverride !== null && queryOverride !== "")
    ? queryOverride
    : ((input && input.value.trim()) ? input.value.trim() : (selectEl ? selectEl.value : ""));

  if (!query) return;

  if (input && input.value !== query) input.value = query;
  if (selectEl && selectEl.value !== query) selectEl.value = query;

  const resultInfo = document.getElementById("trajectory-result-info");
  if (resultInfo) {
    resultInfo.textContent = `Reconstructing multi-hop trajectory for ${query}...`;
    resultInfo.className = "text-muted";
  }

  try {
    const data = await getTrajectory(query, dateFrom, dateTo, currentRole);
    renderTrajectory(data);
  } catch (err) {
    if (resultInfo) {
      resultInfo.textContent = "Error: " + err.message;
      resultInfo.className = "text-critical";
    }
  }
}

// --- Global DOM Init ---
document.addEventListener("DOMContentLoaded", () => {
  // Navigation tabs
  document.querySelectorAll(".nav-item").forEach(btn => {
    btn.addEventListener("click", () => {
      showView(btn.dataset.view);
    });
  });

  // Setup quick select chips
  setupQuickSelect();

  // Tracked Vehicles Dropdown Listener
  const selectEl = document.getElementById("traj-plate-select");
  if (selectEl) {
    selectEl.addEventListener("change", (e) => {
      const selectedPlate = e.target.value;
      if (selectedPlate) {
        doTrajectorySearch(selectedPlate);
      }
    });
  }

  // Trajectory search button & enter key
  const trajBtn = document.getElementById("btn-trajectory-search");
  const trajInput = document.getElementById("trajectory-query");
  if (trajBtn) trajBtn.addEventListener("click", doTrajectorySearch);
  if (trajInput) {
    trajInput.addEventListener("keydown", e => {
      if (e.key === "Enter") doTrajectorySearch();
    });
  }

  // Auto-init initial view
  showView("trajectory");
  setTimeout(() => {
    if (document.getElementById("trajectory-query") && document.getElementById("trajectory-query").value) {
      doTrajectorySearch();
    }
  }, 200);
});

