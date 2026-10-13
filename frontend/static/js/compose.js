// compose.js - the card grid: columns are configurations, rows are the
// five pipeline components, cards drag between cells.
//
// The live cost estimate is the point. A run count badly understates
// the work (nested CV turns 18 runs into 2,880 model fits), so every
// change re-costs the column via POST /api/lab/estimate and shows both
// numbers plus an estimated duration BEFORE anything launches.
//
// Every technique, baseline and model comes from GET /api/lab/choices,
// i.e. from the engine itself. Nothing here hardcodes a design.

let CHOICES = null;
let columns = [];
let nextColumnId = 1;

function datasetList() {
  return document.getElementById("shared-datasets").value
    .split(",").map((s) => s.trim()).filter(Boolean);
}

function sharedK() {
  return Number(document.getElementById("shared-k").value) || 10;
}

function sharedSeed() {
  return Number(document.getElementById("shared-seed").value) || 671;
}

/**
 * Create a configuration column.
 * Inputs: name - its label; baseline - true for the fixed reference
 * column, which holds every component at its Chapter 1 baseline.
 * Output: the column object (component -> chosen techniques).
 */
function makeColumn(name, baseline = false) {
  const levels = {};
  CHOICES.components.forEach((component) => {
    levels[component] = [CHOICES.baselines[component]];
  });
  return {
    id: nextColumnId++,
    name,
    baseline,
    levels,
    models: baseline ? ["logreg"] : ["logreg"],
    estimate: null,
  };
}

/** Return the components a column varies (more than one technique). */
function variedComponents(column) {
  return CHOICES.components.filter((c) => column.levels[c].length > 1);
}

/**
 * Turn a column into the wizard form the API expects.
 * Inputs: column.
 * Output: the form, or null when the column varies no component (the
 * baseline column is a reference, not a runnable sweep on its own).
 */
function columnToForm(column) {
  const varied = variedComponents(column);
  const factor = varied[0] || null;
  if (!factor) return null;
  return {
    name: column.name.replace(/[^a-z0-9]+/gi, "_").toLowerCase() || `config_${column.id}`,
    factor,
    techniques: column.levels[factor],
    datasets: datasetList(),
    models: column.models,
    k: sharedK(),
    seed: sharedSeed(),
  };
}

function renderPalette() {
  const palette = document.getElementById("palette");
  clearChildren(palette);
  CHOICES.components.forEach((component) => {
    const row = document.createElement("div");
    row.className = "palette-row";
    const label = document.createElement("span");
    label.className = "palette-label";
    label.textContent = component;
    row.appendChild(label);
    CHOICES.techniques[component].forEach((technique) => {
      const card = document.createElement("span");
      card.className = "tech-card";
      card.draggable = true;
      card.textContent = technique;
      if (technique === CHOICES.baselines[component]) {
        card.classList.add("is-baseline");
        card.title = "Chapter 1 baseline for this component";
      }
      card.addEventListener("dragstart", (event) => {
        event.dataTransfer.setData("text/plain", JSON.stringify({ component, technique }));
      });
      row.appendChild(card);
    });
    palette.appendChild(row);
  });
}

function renderGrid() {
  const table = document.getElementById("compose-grid");
  clearChildren(table);

  const head = document.createElement("thead");
  const headRow = document.createElement("tr");
  headRow.appendChild(th(""));
  columns.forEach((column) => {
    const cell = document.createElement("th");
    const varied = variedComponents(column);
    cell.className = varied.length > 1 ? "col-head not-ofat" : "col-head";
    const title = document.createElement("input");
    title.type = "text";
    title.value = column.name;
    title.className = "col-name";
    title.addEventListener("change", () => { column.name = title.value; refresh(); });
    cell.appendChild(title);
    const sub = document.createElement("div");
    sub.className = "col-sub";
    sub.textContent = column.baseline ? "baseline reference"
      : varied.length === 0 ? "varies nothing yet"
      : varied.length === 1 ? `varies ${varied[0]}`
      : `varies ${varied.length} components - not OFAT`;
    cell.appendChild(sub);
    if (!column.baseline) {
      const remove = document.createElement("button");
      remove.className = "btn-link";
      remove.textContent = "remove";
      remove.addEventListener("click", () => {
        columns = columns.filter((c) => c.id !== column.id);
        refresh();
      });
      cell.appendChild(remove);
    }
    headRow.appendChild(cell);
  });
  head.appendChild(headRow);
  table.appendChild(head);

  const body = document.createElement("tbody");
  CHOICES.components.forEach((component) => {
    const row = document.createElement("tr");
    const label = document.createElement("td");
    label.className = "row-label";
    label.textContent = component;
    row.appendChild(label);
    columns.forEach((column) => row.appendChild(cellFor(column, component)));
    body.appendChild(row);
  });

  // Models row: not an OFAT component, compared throughout.
  const modelRow = document.createElement("tr");
  const modelLabel = document.createElement("td");
  modelLabel.className = "row-label";
  modelLabel.innerHTML = 'models<br><span class="row-note">compared, not varied</span>';
  modelRow.appendChild(modelLabel);
  columns.forEach((column) => modelRow.appendChild(modelCell(column)));
  body.appendChild(modelRow);

  // The start row: cost, then launch.
  const startRow = document.createElement("tr");
  const startLabel = document.createElement("td");
  startLabel.className = "row-label start-label";
  startLabel.textContent = "start training";
  startRow.appendChild(startLabel);
  columns.forEach((column) => startRow.appendChild(startCell(column)));
  body.appendChild(startRow);

  table.appendChild(body);
}

function th(text) {
  const cell = document.createElement("th");
  cell.textContent = text;
  return cell;
}

function cellFor(column, component) {
  const cell = document.createElement("td");
  cell.className = "grid-cell";
  cell.addEventListener("dragover", (event) => {
    event.preventDefault();
    cell.classList.add("drop-target");
  });
  cell.addEventListener("dragleave", () => cell.classList.remove("drop-target"));
  cell.addEventListener("drop", (event) => {
    event.preventDefault();
    cell.classList.remove("drop-target");
    const payload = JSON.parse(event.dataTransfer.getData("text/plain"));
    if (payload.component !== component) {
      showBanner(document.getElementById("compose-banner"),
        `'${payload.technique}' is a ${payload.component} technique; it cannot go in the ${component} row.`);
      return;
    }
    if (column.baseline) {
      showBanner(document.getElementById("compose-banner"),
        "The baseline column is the fixed reference every other column is compared against. Add a configuration and vary it there.", "info");
      return;
    }
    if (!column.levels[component].includes(payload.technique)) {
      column.levels[component].push(payload.technique);
      refresh();
    }
  });

  column.levels[component].forEach((technique) => {
    const card = document.createElement("span");
    card.className = "tech-card in-cell";
    if (technique === CHOICES.baselines[component]) card.classList.add("is-baseline");
    card.textContent = technique;
    if (!column.baseline && column.levels[component].length > 1) {
      const drop = document.createElement("button");
      drop.className = "card-remove";
      drop.textContent = "x";
      drop.title = "remove this technique";
      drop.addEventListener("click", () => {
        column.levels[component] = column.levels[component].filter((t) => t !== technique);
        refresh();
      });
      card.appendChild(drop);
    }
    cell.appendChild(card);
  });
  return cell;
}

function modelCell(column) {
  const cell = document.createElement("td");
  cell.className = "grid-cell";
  CHOICES.models.forEach((model) => {
    const label = document.createElement("label");
    label.className = "checkbox-item";
    const box = document.createElement("input");
    box.type = "checkbox";
    box.checked = column.models.includes(model);
    box.addEventListener("change", () => {
      column.models = box.checked
        ? [...column.models, model]
        : column.models.filter((m) => m !== model);
      refresh();
    });
    label.appendChild(box);
    label.appendChild(document.createTextNode(" " + model));
    cell.appendChild(label);
  });
  return cell;
}

function startCell(column) {
  const cell = document.createElement("td");
  cell.className = "grid-cell start-cell";
  const estimate = column.estimate;

  if (column.baseline) {
    cell.innerHTML = '<span class="muted">reference only</span>';
    return cell;
  }
  const varied = variedComponents(column);
  if (varied.length === 0) {
    cell.innerHTML = '<span class="muted">add a technique to vary</span>';
    return cell;
  }
  if (varied.length > 1) {
    cell.innerHTML = `<span class="status-failed">varies ${varied.join(", ")}</span>`
      + '<div class="row-note">An effect could not be attributed to one component. '
      + 'Split these into separate configurations.</div>';
    return cell;
  }

  const cost = document.createElement("div");
  cost.className = "cost";
  if (estimate && estimate.error) {
    cost.innerHTML = `<span class="status-failed">${estimate.error}</span>`;
  } else if (estimate) {
    cost.innerHTML =
      `<strong>${estimate.runs.toLocaleString()}</strong> runs<br>`
      + `<strong>${estimate.model_fits.toLocaleString()}</strong> model fits<br>`
      + `<span class="muted">~${estimate.estimated_minutes} min estimated</span>`;
    estimate.warnings.forEach((warning) => {
      const note = document.createElement("div");
      note.className = "row-note warn";
      note.textContent = warning;
      cost.appendChild(note);
    });
  } else {
    cost.innerHTML = '<span class="muted">costing...</span>';
  }
  cell.appendChild(cost);

  const button = document.createElement("button");
  button.className = "btn-primary";
  button.textContent = "Run";
  button.disabled = !estimate || Boolean(estimate.error) || estimate.blocked;
  if (estimate && estimate.blocked) button.title = estimate.blocked_reason;
  button.addEventListener("click", () => launch(column));
  cell.appendChild(button);
  return cell;
}

/** Re-cost every column against the API, then redraw. */
async function refresh() {
  renderGrid();
  await Promise.all(columns.map(async (column) => {
    const form = columnToForm(column);
    if (!form || variedComponents(column).length !== 1) {
      column.estimate = null;
      return;
    }
    try {
      column.estimate = await apiCall("/api/lab/estimate", { method: "POST", body: form });
    } catch (err) {
      column.estimate = { error: err.message };
    }
  }));
  renderGrid();
}

async function launch(column) {
  const banner = document.getElementById("compose-banner");
  clearChildren(banner);
  const form = columnToForm(column);
  const needsConfirm = column.estimate
    && column.estimate.warnings.some((w) => w.includes("roughly"));
  if (needsConfirm && !window.confirm(
      `This sweep is ${column.estimate.runs} runs and `
      + `${column.estimate.model_fits.toLocaleString()} model fits `
      + `(~${column.estimate.estimated_minutes} minutes). Launch anyway?`)) {
    return;
  }
  try {
    const result = await apiCall("/api/lab/runs", {
      method: "POST",
      body: { ...form, confirm_cost: true },
    });
    showBanner(banner,
      `Launched ${result.run_id} (${result.estimate.runs} runs). See the Runs page.`, "info");
  } catch (err) {
    showBanner(banner, err.message);
  }
}

document.addEventListener("DOMContentLoaded", async () => {
  const banner = document.getElementById("compose-banner");
  try {
    CHOICES = await apiCall("/api/lab/choices");
  } catch (err) {
    showBanner(banner, err.message);
    return;
  }
  renderPalette();
  columns = [makeColumn("baseline", true), makeColumn("vary scaling")];
  // Pre-fill the second column with a scaling sweep, so the grid opens
  // on a working example rather than an empty shell.
  columns[1].levels.scaling = CHOICES.techniques.scaling.slice(0, 3);
  ["shared-datasets", "shared-k", "shared-seed"].forEach((id) =>
    document.getElementById(id).addEventListener("change", refresh));
  document.getElementById("add-column").addEventListener("click", () => {
    columns.push(makeColumn(`config ${columns.length}`));
    refresh();
  });
  refresh();
});
