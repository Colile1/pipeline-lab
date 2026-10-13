// trends.js - pick any recorded column for each axis and see the trend.
//
// The server aggregates (GET /api/lab/trends), so the browser never
// holds every row and the plotted numbers are the same ones a direct
// SQL query would give. Bars are plain CSS, per the no-build-step rule.

// Columns worth grouping along, and metrics worth plotting. Populated
// from the record's own columns so a new field appears automatically.
const X_PREFERRED = ["scaling", "imputation", "selection", "tuning", "encoding",
                     "model", "dataset", "task_type"];
const Y_PREFERRED = ["accuracy_mean", "f1_mean", "rmse_mean", "accuracy_sd",
                     "wall_seconds", "peak_rss_mb", "cpu_seconds_user",
                     "n_features_selected", "parallel_efficiency"];

let COLUMNS = [];

function fillSelect(id, options, selected) {
  const select = document.getElementById(id);
  clearChildren(select);
  options.forEach((name) => {
    const option = document.createElement("option");
    option.value = name;
    option.textContent = name;
    if (name === selected) option.selected = true;
    select.appendChild(option);
  });
}

function renderChart(data) {
  const host = document.getElementById("tr-chart");
  clearChildren(host);
  const seriesNames = Object.keys(data.series);
  if (seriesNames.length === 0) {
    showBanner(host, "No numeric values recorded for that metric yet.", "info");
    return;
  }

  const all = seriesNames.flatMap((name) => data.series[name].map((p) => p.mean));
  const max = Math.max(...all, 0);

  seriesNames.forEach((name) => {
    const block = document.createElement("div");
    block.className = "bar-chart";
    const title = document.createElement("p");
    title.className = "bar-chart-title";
    title.textContent = data.group === "none" ? data.y : `${data.group} = ${name}`;
    block.appendChild(title);

    data.series[name].forEach((point) => {
      const row = document.createElement("div");
      row.className = "bar-row";
      const label = document.createElement("span");
      label.className = "bar-label";
      label.textContent = point.x;
      const track = document.createElement("span");
      track.className = "bar-track";
      const fill = document.createElement("span");
      fill.className = "bar-fill";
      fill.style.width = max > 0 ? `${(point.mean / max) * 100}%` : "0%";
      track.appendChild(fill);
      const value = document.createElement("span");
      value.className = "bar-value";
      value.textContent = `${point.mean.toPrecision(4)} (n=${point.n})`;
      row.append(label, track, value);
      block.appendChild(row);
    });
    host.appendChild(block);
  });

  // The same numbers as a table, sortable, so they can be read exactly.
  const rows = [];
  seriesNames.forEach((name) => {
    data.series[name].forEach((point) => {
      rows.push({ [data.group === "none" ? "series" : data.group]: name,
                  [data.x]: point.x, [data.y]: point.mean, runs: point.n });
    });
  });
  const tableHost = document.getElementById("tr-table");
  clearChildren(tableHost);
  const table = buildTable(rows);
  if (table) tableHost.appendChild(table);

  document.getElementById("tr-title").textContent =
    `${data.y} by ${data.x}${data.group === "none" ? "" : `, grouped by ${data.group}`}`
    + ` | ${data.n_runs} succeeded run(s)`;
  document.getElementById("tr-card").hidden = false;
}

async function loadColumns(runId) {
  const record = await apiCall(`/api/lab/record/${encodeURIComponent(runId)}`);
  COLUMNS = record.rows.length ? Object.keys(record.rows[0]) : [];
  const present = (list) => list.filter((c) => COLUMNS.includes(c));
  fillSelect("tr-x", present(X_PREFERRED).concat(
    COLUMNS.filter((c) => !X_PREFERRED.includes(c) && !Y_PREFERRED.includes(c))), "scaling");
  fillSelect("tr-y", present(Y_PREFERRED), "accuracy_mean");
  fillSelect("tr-group", ["none"].concat(present(X_PREFERRED)), "model");
}

async function load() {
  const runId = document.getElementById("tr-run-id").value.trim();
  const banner = document.getElementById("tr-banner");
  clearChildren(banner);
  if (!runId) {
    showBanner(banner, "Enter a run-id first.", "info");
    return;
  }
  showBanner(banner, "Loading...", "info");
  try {
    if (COLUMNS.length === 0) await loadColumns(runId);
    const query = new URLSearchParams({
      x: document.getElementById("tr-x").value,
      y: document.getElementById("tr-y").value,
      group: document.getElementById("tr-group").value,
    });
    const data = await apiCall(`/api/lab/trends/${encodeURIComponent(runId)}?${query}`);
    clearChildren(banner);
    if (data.n_runs === 0) {
      showBanner(banner, "This run recorded no succeeded runs yet.", "info");
      return;
    }
    renderChart(data);
  } catch (err) {
    showBanner(banner, err.message);
  }
}

document.addEventListener("DOMContentLoaded", () => {
  document.getElementById("tr-load").addEventListener("click", load);
  ["tr-x", "tr-y", "tr-group"].forEach((id) =>
    document.getElementById(id).addEventListener("change", () => {
      if (COLUMNS.length) load();
    }));
  document.querySelectorAll(".preset").forEach((button) =>
    button.addEventListener("click", async () => {
      const runId = document.getElementById("tr-run-id").value.trim();
      if (!runId) {
        showBanner(document.getElementById("tr-banner"), "Enter a run-id first.", "info");
        return;
      }
      if (COLUMNS.length === 0) await loadColumns(runId);
      document.getElementById("tr-x").value = button.dataset.x;
      document.getElementById("tr-y").value = button.dataset.y;
      document.getElementById("tr-group").value = button.dataset.group;
      load();
    }));
  const params = new URLSearchParams(window.location.search);
  const runId = params.get("run_id");
  if (runId) {
    document.getElementById("tr-run-id").value = runId;
    load();
  }
});
