// explorer.js - plot any recorded dimension against any recorded metric.
//
// The controls are built from the record itself, so the page can only
// ever offer a dataset, technique or metric that was actually run.
// A reader cannot construct an empty chart by picking a plausible-
// sounding option that never existed.

let DIMENSIONS = null;
let LAST_ROWS = [];

const FRIENDLY = {
  config_name: "experiment",
  vary: "the thing being tested",
  scaling: "scaling method",
  imputation: "missing-value method",
  encoding: "category encoding",
  selection: "feature selection",
  tuning: "settings search",
  model: "model",
  dataset: "dataset",
  task_type: "task type",
  protocol: "evaluation protocol",
  cv_k: "number of folds",
  status: "run status",
  machine_fingerprint: "machine",
  seed: "random seed",
  accuracy_mean: "accuracy",
  f1_mean: "macro-F1",
  rmse_mean: "error size (RMSE)",
  wall_seconds: "time taken (seconds)",
  cpu_seconds_user: "processor time (seconds)",
  peak_rss_mb: "peak memory (MB)",
};

function label(name) {
  return FRIENDLY[name] || name;
}

function fillSelect(id, values, { includeNone = false, selected = null } = {}) {
  const select = document.getElementById(id);
  const previous = selected || select.value;
  clearChildren(select);
  if (includeNone) {
    const option = document.createElement("option");
    option.value = "none";
    option.textContent = "nothing (one series)";
    select.appendChild(option);
  }
  values.forEach((value) => {
    const option = document.createElement("option");
    option.value = value;
    option.textContent = label(value);
    select.appendChild(option);
  });
  if (previous && [...select.options].some((o) => o.value === previous)) {
    select.value = previous;
  }
}

function currentQuery() {
  const sweep = document.getElementById("ex-sweep").value;
  const params = new URLSearchParams({
    x: document.getElementById("ex-x").value,
    y: document.getElementById("ex-y").value,
    group: document.getElementById("ex-group").value,
  });
  if (sweep && sweep !== "all") params.set("config_name", sweep);
  return params;
}

/** A sentence describing what the chart shows, built from the choices. */
function readingNote(data, rowCount) {
  const x = label(data.x), y = label(data.y);
  const direction = data.higher_is_better
    ? "Taller bars are better."
    : "Shorter bars are better, because this measures cost or error.";
  const split = data.group === "none"
    ? "All runs are pooled into one series."
    : `Each colour is a different ${label(data.group)}, so the bars can be `
      + `compared within a group as well as across one.`;
  return `This compares ${y} across each ${x}. ${direction} ${split} `
    + `Every bar is the average of the runs behind it (${rowCount} runs in `
    + `total); hover a bar to see its exact value and how many runs it `
    + `covers.`;
}

async function draw() {
  const banner = document.getElementById("ex-banner");
  const chart = document.getElementById("ex-chart");
  const read = document.getElementById("ex-read");
  const title = document.getElementById("chart-title");
  clearChildren(banner);
  clearChildren(chart);
  clearChildren(read);

  const params = currentQuery();
  let data;
  try {
    data = await apiCall(`/api/analysis/aggregate?${params}`);
  } catch (err) {
    showBanner(banner, err.message);
    return;
  }

  title.textContent = `${label(data.y)} by ${label(data.x)}`;

  if (!Object.keys(data.series).length) {
    chart.appendChild(paragraph(
      data.empty_reason || "No runs match this selection.", "muted"));
    return;
  }

  const total = Object.values(data.series)
    .flat().reduce((sum, p) => sum + p.n, 0);

  chart.appendChild(barChart(data.series, {
    xLabel: label(data.x),
    yLabel: label(data.y),
    higherIsBetter: data.higher_is_better,
    caption: `Figure: average ${label(data.y)} for each ${label(data.x)}`
      + (data.group === "none" ? "" : `, split by ${label(data.group)}`)
      + `, over ${total} recorded runs.`,
  }));

  read.appendChild(paragraph(readingNote(data, total)));
  read.appendChild(explainer("Why an average, and what it hides", [
    "Each bar averages every run that matches it, which can span very "
    + "different datasets. An average is the right summary for 'what "
    + "usually happens', but it can hide a technique that helps "
    + "enormously on some data and hurts on other data.",
    "To see that, set 'Compare across' to dataset: the per-dataset view "
    + "shows the spread the average smooths away. The Findings page "
    + "goes further and counts how many datasets each option actually "
    + "helped, which is often more informative than the average itself.",
    "Runs that were skipped or failed are never averaged in. A skipped "
    + "run has a recorded reason rather than a score, and including it "
    + "would bias whatever series it touched.",
  ]));

  await drawTable(params);
}

async function drawTable(params) {
  const target = document.getElementById("ex-table");
  clearChildren(target);
  const sweep = params.get("config_name");
  let data;
  try {
    data = await apiCall(
      `/api/analysis/runs?limit=500${sweep ? `&config_name=${encodeURIComponent(sweep)}` : ""}`);
  } catch (err) {
    target.appendChild(paragraph(err.message, "muted"));
    return;
  }
  LAST_ROWS = data.rows;
  if (!data.rows.length) {
    target.appendChild(paragraph("No rows match.", "muted"));
    return;
  }
  // A readable subset; the CSV carries all 86 fields.
  const columns = ["dataset", "model", "scaling", "imputation", "encoding",
    "selection", "tuning", "status", "accuracy_mean", "f1_mean",
    "rmse_mean", "wall_seconds", "peak_rss_mb"];
  const slim = data.rows.map((row) => {
    const out = {};
    columns.forEach((c) => { out[c] = row[c]; });
    return out;
  });

  // Show a readable window by default. Hundreds of rows turn the page
  // into a scroll with no end, and a reader who wants every row wants
  // the CSV anyway.
  const PAGE = 25;
  let shown = PAGE;
  const holder = document.createElement("div");
  const note = document.createElement("p");
  note.className = "muted";
  const more = document.createElement("button");
  more.type = "button";
  more.className = "btn-secondary";

  function paint() {
    clearChildren(holder);
    holder.appendChild(buildTable(slim.slice(0, shown)));
    note.textContent =
      `Showing ${Math.min(shown, slim.length)} of ${data.total} recorded runs.`
      + (data.total > slim.length
        ? ` The table loads at most ${slim.length}; the CSV has every field of every row.`
        : "");
    more.textContent = `Show ${Math.min(PAGE, slim.length - shown)} more`;
    more.hidden = shown >= slim.length;
  }

  more.addEventListener("click", () => { shown += PAGE; paint(); });
  target.appendChild(holder);
  target.appendChild(note);
  target.appendChild(more);
  paint();
}

document.addEventListener("DOMContentLoaded", async () => {
  const banner = document.getElementById("ex-banner");
  try {
    DIMENSIONS = await apiCall("/api/analysis/dimensions");
  } catch (err) {
    showBanner(banner, err.message, "info");
    return;
  }
  const dims = Object.keys(DIMENSIONS.dimensions);
  const wanted = new URLSearchParams(location.search).get("sweep");

  fillSelect("ex-x", dims, { selected: dims.includes("scaling") ? "scaling" : dims[0] });
  fillSelect("ex-y", DIMENSIONS.metrics,
    { selected: DIMENSIONS.metrics[0] });
  fillSelect("ex-group", dims, { includeNone: true, selected: "model" });

  const sweeps = await apiCall("/api/analysis/sweeps");
  const sweepSelect = document.getElementById("ex-sweep");
  clearChildren(sweepSelect);
  const all = document.createElement("option");
  all.value = "all";
  all.textContent = "every experiment";
  sweepSelect.appendChild(all);
  sweeps.sweeps.forEach((s) => {
    const option = document.createElement("option");
    option.value = s.config_name;
    option.textContent = s.config_name;
    sweepSelect.appendChild(option);
  });
  if (wanted) sweepSelect.value = wanted;

  ["ex-x", "ex-y", "ex-group", "ex-sweep"].forEach((id) =>
    document.getElementById(id).addEventListener("change", draw));

  document.querySelectorAll(".preset").forEach((button) => {
    button.addEventListener("click", () => {
      document.getElementById("ex-x").value = button.dataset.x;
      document.getElementById("ex-y").value = button.dataset.y;
      document.getElementById("ex-group").value = button.dataset.group;
      draw();
    });
  });

  document.getElementById("ex-csv").addEventListener("click", async () => {
    const sweep = document.getElementById("ex-sweep").value;
    const query = sweep && sweep !== "all"
      ? `?config_name=${encodeURIComponent(sweep)}` : "";
    const data = await apiCall(`/api/analysis/export${query}`);
    downloadCsv(data.rows, `pipeline-lab-${sweep || "all"}.csv`);
  });

  watchRecord(async (pulse) => {
    renderPulse(document.getElementById("pulse"), pulse);
    await draw();
  });
});
