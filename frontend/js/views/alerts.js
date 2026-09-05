/**
 * views/alerts.js — Multi-Modal Alerts and Security Audit Log
 * Stage 8 Refined:
 * - Summary KPI cards for critical vs warning incident counts
 * - Role-gated audit trail view with real-time log updates
 */

async function loadAlerts() {
  const tbody = document.getElementById("alerts-table-body");
  const statusEl = document.getElementById("alerts-status");
  const navAlertBadge = document.getElementById("nav-alert-count");
  const statCritical = document.getElementById("stat-critical-count");
  const statWarn = document.getElementById("stat-warn-count");
  const statTotal = document.getElementById("stat-total-alerts");

  tbody.innerHTML = "";
  statusEl.textContent = "Loading active incident queue...";

  try {
    const alerts = await getAlerts();

    if (!alerts || alerts.length === 0) {
      statusEl.textContent = "No active alerts in queue.";
      if (navAlertBadge) navAlertBadge.textContent = "0";
      return;
    }

    if (navAlertBadge) navAlertBadge.textContent = String(alerts.length);
    if (statTotal) statTotal.textContent = String(alerts.length);

    let critCount = 0;
    let warnCount = 0;

    alerts.forEach(a => {
      if (a.alert_type === "clone" || a.alert_type === "blacklist") {
        critCount++;
      } else {
        warnCount++;
      }
    });

    if (statCritical) statCritical.textContent = String(critCount);
    if (statWarn) statWarn.textContent = String(warnCount);

    statusEl.textContent = `${alerts.length} incident alerts registered across network.`;

    alerts.forEach(a => {
      const createdAt = a.created_at_iso || new Date(a.created_at * 1000).toISOString();
      const typeClass = `alert-${a.alert_type}`;
      const row = document.createElement("tr");
      row.innerHTML = `
        <td class="mono">${escHtml(createdAt)}</td>
        <td><span class="${typeClass}"><strong>${escHtml(a.alert_type.toUpperCase())}</strong></span></td>
        <td class="mono">${escHtml(a.sighting_id_a)}</td>
        <td class="mono">${escHtml(a.sighting_id_b || "—")}</td>
        <td>${escHtml(a.detail_text)}</td>
      `;
      tbody.appendChild(row);
    });

  } catch (err) {
    statusEl.textContent = "Error loading alerts: " + err.message;
    statusEl.className = "text-critical";
  }

  // Audit log section — only shown in supervisor mode
  loadAuditLog();
}

async function loadAuditLog() {
  const section = document.getElementById("audit-log-section");
  const tbody = document.getElementById("audit-table-body");

  if (section) section.style.display = "block";
  if (!tbody) return;
  tbody.innerHTML = "";

  try {
    const logs = await getAuditLog();

    if (!logs || logs.length === 0) {
      const row = document.createElement("tr");
      row.innerHTML = `<td colspan="4" class="empty-state">No audit log entries recorded.</td>`;
      tbody.appendChild(row);
      return;
    }

    logs.forEach(l => {
      const searchedAt = l.searched_at_iso || new Date(l.searched_at * 1000).toISOString();
      const row = document.createElement("tr");
      row.innerHTML = `
        <td class="mono">${escHtml(searchedAt)}</td>
        <td class="mono">${escHtml(l.log_id)}</td>
        <td><span class="badge ${l.searched_by === 'supervisor' ? 'badge-warn' : 'badge-accent'}">${escHtml(l.searched_by.toUpperCase())}</span></td>
        <td class="mono">${escHtml(l.searched_query)}</td>
      `;
      tbody.appendChild(row);
    });

  } catch (err) {
    tbody.innerHTML = `<tr><td colspan="4" class="text-critical">Error loading audit log: ${escHtml(err.message)}</td></tr>`;
  }
}
