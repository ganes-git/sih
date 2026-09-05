/**
 * views/blacklist.js — Blacklist Plate Check view
 * Dynamic fuzzy checking against registry with active report updates.
 */

async function doBlacklistCheck() {
  const input = document.getElementById("bl-plate-input");
  const plate = input ? input.value.trim() : "";
  if (!plate) { alert("Enter a plate number to check."); return; }

  const resultEl = document.getElementById("bl-result");
  if (!resultEl) return;
  resultEl.className = "bl-result";
  resultEl.innerHTML = `<span class="text-muted">Querying law enforcement security registry for <strong>${escHtml(plate)}</strong>...</span>`;

  try {
    const data = await checkBlacklist(plate, currentRole);

    if (data.matched) {
      const entry = data.matched_entry;
      const addedOn = entry.added_on_iso || (entry.added_on ? new Date(entry.added_on * 1000).toISOString().split('T')[0] : "2026-09-01");
      resultEl.className = "bl-result match";
      resultEl.innerHTML = `
        <div style="display:flex; align-items:center; justify-content:space-between; margin-bottom:10px;">
          <div>
            <strong style="color:var(--critical); font-size:14px; text-transform:uppercase; letter-spacing:0.04em;">
              CRITICAL WATCHLIST HIT DETECTED
            </strong>
            <div style="font-size:12px; color:var(--text); margin-top:2px;">
              Registration number matches an active law enforcement flagged vehicle bulletin.
            </div>
          </div>
          <span class="badge badge-critical" style="font-size:12px; padding:4px 10px;">Active Hit</span>
        </div>
        <table class="data-table" style="margin-top:8px;">
          <tr>
            <th style="width:180px;">Queried Registration</th>
            <td class="mono font-bold" style="font-size:13px;">${escHtml(data.query_plate || plate)}</td>
          </tr>
          <tr>
            <th>Blacklisted Plate</th>
            <td class="mono font-bold" style="color:var(--critical); font-size:13px;">${escHtml(entry.plate_text)}</td>
          </tr>
          <tr>
            <th>Violation / Case Reason</th>
            <td style="color:var(--text);">${escHtml(entry.reason)}</td>
          </tr>
          <tr>
            <th>Registered Date</th>
            <td class="mono">${escHtml(addedOn)}</td>
          </tr>
          <tr>
            <th>Fuzzy Similarity Score</th>
            <td class="mono" style="font-weight:600;">${(data.similarity * 100).toFixed(1)}% match ratio (${data.similarity.toFixed(4)})</td>
          </tr>
        </table>
      `;
    } else {
      resultEl.className = "bl-result no-match";
      resultEl.innerHTML = `
        <div style="display:flex; align-items:center; justify-content:space-between; margin-bottom:8px;">
          <div>
            <strong style="color:var(--accent); font-size:14px; text-transform:uppercase; letter-spacing:0.04em;">
              CLEAN VEHICLE — NO ACTIVE WATCHLIST RECORD
            </strong>
            <div style="font-size:12px; color:var(--text); margin-top:2px;">
              Registration number <span class="mono font-bold">${escHtml(plate)}</span> does not match any flagged case records.
            </div>
          </div>
          <span class="badge badge-accent" style="font-size:12px; padding:4px 10px;">Verified Clean</span>
        </div>
        <div style="font-size:12px; color:var(--muted); margin-top:6px;">
          Registry Status: 0 records flagged across hit-and-run, stolen vehicle, and smuggling databases.
          ${data.similarity > 0 ? ` Closest database similarity: <span class="mono">${(data.similarity * 100).toFixed(1)}%</span>.` : ""}
        </div>
      `;
    }
  } catch (err) {
    resultEl.className = "bl-result";
    resultEl.innerHTML = `<span class="text-critical">Error: ${escHtml(err.message)}</span>`;
  }
}

function selectBlacklistPlate(plate) {
  const blInput = document.getElementById("bl-plate-input");
  if (blInput && plate) {
    blInput.value = plate;
    doBlacklistCheck();
  }
}

function initBlacklistView() {
  const blBtn = document.getElementById("bl-search-btn");
  const blInput = document.getElementById("bl-plate-input");
  if (blBtn && !blBtn.dataset.bound) {
    blBtn.dataset.bound = "true";
    blBtn.addEventListener("click", doBlacklistCheck);
  }
  if (blInput && !blInput.dataset.bound) {
    blInput.dataset.bound = "true";
    blInput.addEventListener("keydown", e => {
      if (e.key === "Enter") doBlacklistCheck();
    });
  }

  document.querySelectorAll("[data-bl-plate]").forEach(chip => {
    if (!chip.dataset.bound) {
      chip.dataset.bound = "true";
      chip.addEventListener("click", (e) => {
        e.preventDefault();
        const plate = chip.dataset.blPlate || chip.getAttribute("data-bl-plate");
        selectBlacklistPlate(plate);
      });
    }
  });

  // Auto-run on first load if input has value
  if (blInput && blInput.value && !document.getElementById("bl-result")?.innerHTML) {
    doBlacklistCheck();
  }
}

window.doBlacklistCheck = doBlacklistCheck;
window.selectBlacklistPlate = selectBlacklistPlate;
window.initBlacklistView = initBlacklistView;

document.addEventListener("DOMContentLoaded", initBlacklistView);
