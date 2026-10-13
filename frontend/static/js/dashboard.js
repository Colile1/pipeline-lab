// dashboard.js - headline numbers, the sweep list and a cost chart.
//
// Reads /api/analysis, which reads the engine's lab.db directly, so a
// sweep launched from the command line appears here without anything
// being imported or synced. The page re-renders itself whenever the
// record changes.

const STAT_NOTES = {
  "Runs recorded": "One run is one combination: a dataset, a model and "
    + "one setting of the thing being tested, scored by cross-validation.",
  "Succeeded": "Finished and produced a score.",
  "Skipped": "Refused before running, with a reason stored. A sweep that "
    + "skips is behaving correctly: it declined to produce a number it "
    + "could not stand behind.",
  "Datasets": "Distinct datasets appearing in the record.",
  "Sweeps": "Distinct experiments, each changing one thing at a time.",
  "Compute spent": "Total wall-clock time across every recorded run.",
};

function statTile(label, value, note) {
  const tile = document.createElement("div");
  tile.className = "stat-tile";
  const v = document.createElement("div");
  v.className = "stat-value";
  v.textContent = value;
  const l = document.createElement("div");
  l.className = "stat-label";
  l.textContent = label;
  tile.appendChild(v);
  tile.appendChild(l);
  if (note) tile.title = note;
  return tile;
}

async function renderOverview() {
  const target = document.getElementById("overview");
  const banner = document.getElementById("dash-banner");
  clearChildren(banner);
  let data;
  try {
    data = await apiCall("/api/analysis/overview");
  } catch (err) {
    clearChildren(target);
    showBanner(banner, err.message, "info");
    return;
  }
  clearChildren(target);
  const tiles = [
    ["Runs recorded", data.total_runs.toLocaleString()],
    ["Succeeded", data.succeeded.toLocaleString()],
    ["Skipped", data.skipped.toLocaleString()],
    ["Datasets", data.datasets],
    ["Sweeps", data.sweeps],
    ["Compute spent", fmtDuration(data.compute_seconds)],
  ];
  tiles.forEach(([label, value]) =>
    target.appendChild(statTile(label, value, STAT_NOTES[label])));

  target.appendChild(explainer(
    "What am I looking at?",
    [
      "This project tests how much ordinary data-preparation choices "
      + "change how well a model predicts. Before any model sees data, "
      + "someone has to decide how to put the numbers on a comparable "
      + "scale, what to do about missing values, how to turn words into "
      + "numbers, which columns to keep, and how hard to search for the "
      + "model's settings. Those five decisions are usually made by "
      + "habit. This measures whether they matter.",
      "Each experiment changes exactly one of those five decisions and "
      + "holds the other four fixed. That is what lets a difference in "
      + "the result be attributed to the decision rather than to "
      + "something else moving at the same time.",
      `The full record lives at ${data.record_path}. Nothing on this `
      + "page is computed from anywhere else, and nothing is cached.",
    ],
  ));
}

function sweepRow(sweep) {
  const row = document.createElement("div");
  row.className = "sweep-row";

  const head = document.createElement("div");
  head.className = "sweep-head";
  const name = document.createElement("span");
  name.className = "sweep-name";
  name.textContent = sweep.config_name;
  head.appendChild(name);

  const chip = document.createElement("span");
  chip.className = "tech-card is-baseline";
  chip.textContent = `varies ${sweep.vary}`;
  head.appendChild(chip);
  row.appendChild(head);

  const facts = document.createElement("div");
  facts.className = "sweep-facts";
  const bits = [
    `${sweep.runs} runs`,
    `${sweep.succeeded} succeeded`,
    sweep.skipped ? `${sweep.skipped} skipped` : null,
    sweep.failed ? `${sweep.failed} failed` : null,
    `${sweep.datasets} datasets`,
    `${sweep.models} models`,
    sweep.tasks,
    fmtDuration(sweep.wall_seconds),
  ].filter(Boolean);
  facts.textContent = bits.join("  |  ");
  row.appendChild(facts);

  const actions = document.createElement("div");
  actions.className = "sweep-actions";
  const findings = document.createElement("a");
  findings.className = "btn-secondary";
  findings.href = `/findings?sweep=${encodeURIComponent(sweep.config_name)}`;
  findings.textContent = "What did it find?";
  actions.appendChild(findings);

  const explore = document.createElement("a");
  explore.className = "btn-link";
  explore.href = `/explorer?sweep=${encodeURIComponent(sweep.config_name)}`;
  explore.textContent = "Explore the numbers";
  actions.appendChild(explore);
  row.appendChild(actions);

  if (sweep.skipped) {
    row.appendChild(explainer(
      `Why were ${sweep.skipped} runs skipped?`,
      "A run is skipped when the engine cannot produce an honest score. "
      + "The most common cause here is row deletion: when the baseline "
      + "way of handling missing values is to drop any row that has one, "
      + "a dataset with a lot of missing values can lose almost all of "
      + "its rows, leaving too few to split into folds. The engine "
      + "records the reason instead of inventing a number. Open the "
      + "Explorer and filter by status to read each one.",
    ));
  }
  return row;
}

async function renderSweeps() {
  const target = document.getElementById("sweeps");
  let data;
  try {
    data = await apiCall("/api/analysis/sweeps");
  } catch (err) {
    clearChildren(target);
    target.appendChild(paragraph(err.message, "muted"));
    return;
  }
  clearChildren(target);
  if (!data.sweeps.length) {
    target.appendChild(paragraph(
      "No sweeps recorded yet. Build one on the Compose page.", "muted"));
    return;
  }
  data.sweeps.forEach((s) => target.appendChild(sweepRow(s)));
}

async function renderCost() {
  const target = document.getElementById("cost-chart");
  clearChildren(target);
  let data;
  try {
    data = await apiCall(
      "/api/analysis/aggregate?x=scaling&y=wall_seconds&group=model");
  } catch (err) {
    target.appendChild(paragraph(err.message, "muted"));
    return;
  }
  if (!Object.keys(data.series).length) {
    target.appendChild(paragraph(data.empty_reason || "Nothing to plot yet.", "muted"));
    return;
  }
  target.appendChild(barChart(data.series, {
    xLabel: "scaling method applied",
    yLabel: "seconds per run",
    higherIsBetter: false,
    caption: "Figure: average wall-clock time for one run, by scaling "
      + "method and model. Each bar averages every recorded run with that "
      + "combination; hover a bar for the exact figure and how many runs "
      + "it covers.",
  }));
  target.appendChild(explainer(
    "How should I read this?",
    [
      "Taller means slower. If two options reach the same accuracy and "
      + "one is much shorter, the shorter one is the better default.",
      "Time here is wall-clock time on one ordinary laptop, so treat it "
      + "as a comparison between the bars rather than a number that "
      + "would transfer to other hardware. The exact machine, its "
      + "processor, memory and every library version are stored with "
      + "each run, which is what makes the comparison fair.",
      "Scaling itself is cheap. Where you see a large difference, it is "
      + "usually the model reacting to the rescaled data rather than the "
      + "cost of rescaling: an unscaled support vector machine can take "
      + "far longer to converge, which is a real cost of skipping the "
      + "step.",
    ],
  ));
}

async function refreshAll(pulse) {
  renderPulse(document.getElementById("pulse"), pulse);
  await Promise.all([renderOverview(), renderSweeps(), renderCost()]);
}

document.addEventListener("DOMContentLoaded", () => {
  watchRecord(refreshAll);
});
