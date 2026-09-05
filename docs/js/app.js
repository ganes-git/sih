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
      if (typeof heatmapMap !== "undefined" && heatmapMap) heatmapMap.invalidateSize();
    }, 150);
  } else if (viewName === "alerts") {
    loadAlerts();
  } else if (viewName === "traffic") {
    loadTrafficTrends();
  } else if (viewName === "blacklist") {
    initBlacklistView();
  }
}

// --- Quick-select chips ---
function setupQuickSelect() {
  document.querySelectorAll(".plate-chip, .quick-chip").forEach(chip => {
    chip.addEventListener("click", () => {
      const plate = chip.dataset.plate;
      const input = document.getElementById("traj-query") || document.getElementById("trajectory-query");
      const selectEl = document.getElementById("traj-plate-select");
      if (input) input.value = plate;
      if (selectEl) selectEl.value = plate;
      doTrajectorySearch(plate);
    });
  });
}

// --- Trajectory search trigger ---
async function doTrajectorySearch(queryOverride) {
  const input = document.getElementById("traj-query") || document.getElementById("trajectory-query");
  const selectEl = document.getElementById("traj-plate-select");
  const dateFrom = (document.getElementById("traj-date-from") || document.getElementById("trajectory-from")) ? (document.getElementById("traj-date-from") || document.getElementById("trajectory-from")).value : "";
  const dateTo = (document.getElementById("traj-date-to") || document.getElementById("trajectory-to")) ? (document.getElementById("traj-date-to") || document.getElementById("trajectory-to")).value : "";

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
  const trajBtn = document.getElementById("traj-search-btn") || document.getElementById("btn-trajectory-search");
  const trajInput = document.getElementById("traj-query") || document.getElementById("trajectory-query");
  if (trajBtn) {
    trajBtn.addEventListener("click", (e) => {
      e.preventDefault();
      const curInput = document.getElementById("traj-query") || document.getElementById("trajectory-query");
      const val = curInput ? curInput.value.trim() : "";
      doTrajectorySearch(val);
    });
  }
  if (trajInput) {
    trajInput.addEventListener("keydown", e => {
      if (e.key === "Enter") {
        e.preventDefault();
        const val = trajInput.value.trim();
        doTrajectorySearch(val);
      }
    });
  }

  // Auto-init initial view
  showView("trajectory");
  setTimeout(() => {
    const initialInput = document.getElementById("traj-query") || document.getElementById("trajectory-query");
    if (initialInput && initialInput.value) {
      doTrajectorySearch(initialInput.value.trim());
    }
  }, 200);
});
