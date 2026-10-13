// results.js - read a completed run's real result tables from
// GET /api/results/{run_id} and render them as sortable tables plus a
// simple bar chart per numeric metric column. Every value shown is read
// straight from the API response; nothing here computes a statistic.

// b2's extract_results.py names these mean_accuracy/mean_f1/mean_rmse
// (from its MLflow params/metrics); prepfx's tables/{arm}_summary.csv
// names them accuracy_mean/f1_mean/rmse_mean (confirmed against a real
// outputs/tables/scaling_summary.csv) - the two engines do not share a
// metric-column convention any more than they share a model-name one.
const METRIC_COLUMNS = [
  "mean_accuracy", "mean_f1", "mean_rmse",
  "accuracy_mean", "f1_mean", "rmse_mean",
];

function numericColumns(rows) {
  if (!rows.length) return [];
  const keys = Object.keys(rows[0]);
  return keys.filter((key) => {
    if (!METRIC_COLUMNS.includes(key)) return false;
    return rows.some((row) => row[key] !== null && row[key] !== "" && !Number.isNaN(Number(row[key])));
  });
}

/**
 * Build a minimal bar chart (no chart library - see frontend/README.md's
 * "no Node, no build step" constraint): one horizontal bar per row,
 * labelled by a label column, scaled to the column's own max value.
 * Inputs: rows - row objects; metricCol - the numeric column to chart;
 * labelCol - a column to use as each bar's label.
 * Output: a <div> containing the chart, or null if there is nothing to plot.
 */
function buildBarChart(rows, metricCol, labelCol) {
  const values = rows
    .map((row) => ({ label: row[labelCol] ?? "(row)", value: Number(row[metricCol]) }))
    .filter((entry) => !Number.isNaN(entry.value));
  if (!values.length) return null;
  const max = Math.max(...values.map((v) => Math.abs(v.value)), 1e-9);

  const chart = document.createElement("div");
  chart.className = "bar-chart";
  const title = document.createElement("p");
  title.className = "bar-chart-title";
  title.textContent = metricCol;
  chart.appendChild(title);
  values.forEach(({ label, value }) => {
    const row = document.createElement("div");
    row.className = "bar-row";
    const labelEl = document.createElement("span");
    labelEl.className = "bar-label";
    labelEl.textContent = label;
    const track = document.createElement("span");
    track.className = "bar-track";
    const fill = document.createElement("span");
    fill.className = "bar-fill";
    fill.style.width = `${(Math.abs(value) / max) * 100}%`;
    track.appendChild(fill);
    const valueEl = document.createElement("span");
    valueEl.className = "bar-value";
    valueEl.textContent = value.toPrecision(4);
    row.append(labelEl, track, valueEl);
    chart.appendChild(row);
  });
  return chart;
}

function pickLabelColumn(rows) {
  // "dataset" (b2's extract_results.py) and "dataset_id" (prepfx's own
  // tables/{arm}_summary.csv, confirmed against a real file) name the
  // same thing differently; try both, then fall back to the first column.
  const candidates = ["dataset", "dataset_id", "level", "technique", "model"];
  const keys = Object.keys(rows[0] || {});
  return candidates.find((c) => keys.includes(c)) || keys[0];
}

function renderTableSection(name, rows) {
  const card = document.createElement("div");
  card.className = "card wide";
  const title = document.createElement("p");
  title.className = "card-title";
  title.textContent = name;
  card.appendChild(title);

  const table = buildTable(rows);
  if (table) {
    card.appendChild(table);
  } else {
    const empty = document.createElement("p");
    empty.className = "card-body";
    empty.textContent = "No rows in this table.";
    card.appendChild(empty);
  }

  const metricCols = numericColumns(rows);
  if (metricCols.length && rows.length <= 50) {
    const labelCol = pickLabelColumn(rows);
    metricCols.forEach((col) => {
      const chart = buildBarChart(rows, col, labelCol);
      if (chart) card.appendChild(chart);
    });
  }
  return card;
}

async function loadResults() {
  const runId = document.getElementById("res-run-id").value.trim();
  const banner = document.getElementById("res-banner");
  const container = document.getElementById("res-tables");
  clearChildren(banner);
  clearChildren(container);
  if (!runId) {
    showBanner(banner, "Enter a run-id first.", "info");
    return;
  }
  // b2's first request for a run extracts its results from MLflow via a
  // real subprocess (see engines/b2/extract_results.py) and can take a
  // few seconds; a later request is instant (the extraction is cached).
  // Without this, the page shows nothing while that first request is
  // in flight, which looks broken rather than slow.
  showBanner(container, "Loading results...", "info");
  try {
    const result = await apiCall(`/api/results/${encodeURIComponent(runId)}`);
    clearChildren(container);
    const tableNames = Object.keys(result.tables);
    if (tableNames.length === 0) {
      showBanner(container, "This run succeeded but reported no result tables.", "info");
      return;
    }
    tableNames.forEach((name) => {
      container.appendChild(renderTableSection(name, result.tables[name]));
    });
  } catch (err) {
    clearChildren(container);
    showBanner(banner, err.message);
  }
}

document.addEventListener("DOMContentLoaded", () => {
  document.getElementById("res-load").addEventListener("click", loadResults);
  const params = new URLSearchParams(window.location.search);
  const runId = params.get("run_id");
  if (runId) {
    document.getElementById("res-run-id").value = runId;
    loadResults();
  }
});
