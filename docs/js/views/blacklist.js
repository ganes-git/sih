/**
 * views/blacklist.js — Blacklist Plate Check view
 * Stage 7: calls dataSource.checkBlacklist(), shows match/no-match result.
 * Critical accent colour used only when there is an actual match.
 */

async function doBlacklistCheck() {
  const plate = document.getElementById("bl-plate-input").value.trim();
  if (!plate) { alert("Enter a plate number to check."); return; }

  const resultEl = document.getElementById("bl-result");
  resultEl.className = "bl-result";
  resultEl.innerHTML = "Checking...";

  try {
    const data = await checkBlacklist(plate, currentRole);

    if (data.matched) {
      const entry = data.matched_entry;
      const addedOn = entry.added_on_iso || new Date(entry.added_on * 1000).toISOString();
      resultEl.className = "bl-result match";
      resultEl.innerHTML = `
        <div><strong>Match found</strong></div>
        <table class="data-table" style="margin-top:8px;">
          <tr><th>Plate</th><td class="mono">${escHtml(entry.plate_text)}</td></tr>
          <tr><th>Reason</th><td>${escHtml(entry.reason)}</td></tr>
          <tr><th>Added on</th><td class="mono">${escHtml(addedOn)}</td></tr>
          <tr><th>Similarity</th><td class="mono">${data.similarity.toFixed(4)}</td></tr>
        </table>
      `;
    } else {
      resultEl.className = "bl-result no-match";
      resultEl.innerHTML =
        `No match for <span class="mono">${escHtml(plate)}</span> in the blacklist.` +
        (data.similarity > 0
          ? ` Closest match similarity: <span class="mono">${data.similarity.toFixed(4)}</span>.`
          : "");
    }
  } catch (err) {
    resultEl.className = "bl-result";
    resultEl.innerHTML = `<span class="text-critical">Error: ${escHtml(err.message)}</span>`;
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
      chip.addEventListener("click", () => {
        const plate = chip.dataset.blPlate || chip.getAttribute("data-bl-plate");
        if (blInput && plate) {
          blInput.value = plate;
          doBlacklistCheck();
        }
      });
    }
  });
}

document.addEventListener("DOMContentLoaded", initBlacklistView);
