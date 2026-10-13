// experiment.js - wizard form for building/launching an experiment.
//
// Technique/model/mechanism choices are always fetched from
// GET /api/experiments/choices?engine=&factor= - never hardcoded - because
// the two engines name some of the same things differently (prepfx's
// logistic-regression key is "logistic", b2's is "logreg") and the fixed
// lists are each engine's own design, not this page's to invent.
//
// prepfx has two restrictions b2 does not: it sweeps a factor's whole
// fixed technique list (no subset) and takes exactly one missingness
// rate + one mechanism. Rather than let the backend reject an invalid
// combination after the fact, this page reflects those restrictions in
// the control itself - all techniques pre-checked and disabled for
// prepfx, and a single-select instead of a free list of rates/mechanisms.

let currentChoices = null;

function isPrepfx() {
  return document.getElementById("exp-engine").value === "prepfx";
}

function renderCheckboxGroup(container, name, values, { disabledChecked = false, single = false } = {}) {
  clearChildren(container);
  values.forEach((value) => {
    const label = document.createElement("label");
    label.className = "checkbox-item";
    const input = document.createElement("input");
    input.type = single ? "radio" : "checkbox";
    input.name = name;
    input.value = value;
    if (disabledChecked) {
      input.checked = true;
      input.disabled = true;
    }
    label.appendChild(input);
    label.appendChild(document.createTextNode(" " + value));
    container.appendChild(label);
  });
}

function checkedValues(container) {
  return Array.from(container.querySelectorAll("input:checked")).map((i) => i.value);
}

async function loadChoices() {
  const engine = document.getElementById("exp-engine").value;
  const factor = document.getElementById("exp-factor").value;
  const banner = document.getElementById("exp-banner");
  clearChildren(banner);
  try {
    currentChoices = await apiCall(
      `/api/experiments/choices?engine=${encodeURIComponent(engine)}&factor=${encodeURIComponent(factor)}`
    );
  } catch (err) {
    showBanner(banner, err.message);
    return;
  }

  const prepfx = isPrepfx();
  const techniqueContainer = document.getElementById("exp-techniques");
  renderCheckboxGroup(techniqueContainer, "technique", currentChoices.techniques, {
    disabledChecked: prepfx,
  });
  document.getElementById("exp-technique-hint").textContent = prepfx
    ? "prepfx always runs this factor's whole technique list - no subset is possible."
    : "Pick one or more techniques to compare.";

  renderCheckboxGroup(document.getElementById("exp-models"), "model", currentChoices.models);

  const missingnessSection = document.getElementById("exp-missingness-section");
  const isImputation = factor === "imputation";
  missingnessSection.hidden = !isImputation;
  if (isImputation) {
    renderCheckboxGroup(
      document.getElementById("exp-mechanisms"), "mechanism", currentChoices.mechanisms,
      { single: prepfx }
    );
    document.getElementById("exp-missingness-hint").textContent = prepfx
      ? "prepfx takes exactly one rate and one mechanism per run."
      : "b2 can sweep several rates and mechanisms in one run.";
    document.getElementById("exp-rates").placeholder = prepfx ? "e.g. 0.15 (one value)" : "e.g. 0.05, 0.15, 0.30";
  }
}

function readForm() {
  const engine = document.getElementById("exp-engine").value;
  const factor = document.getElementById("exp-factor").value;
  const form = {
    engine,
    name: document.getElementById("exp-name").value.trim(),
    factor,
    techniques: checkedValues(document.getElementById("exp-techniques")),
    models: checkedValues(document.getElementById("exp-models")),
    datasets: document.getElementById("exp-datasets").value.split(",").map((s) => s.trim()).filter(Boolean),
    k: Number(document.getElementById("exp-k").value),
    seed: Number(document.getElementById("exp-seed").value),
  };
  if (factor === "imputation") {
    const rates = document.getElementById("exp-rates").value
      .split(",").map((s) => s.trim()).filter(Boolean).map(Number);
    if (rates.length) form.missingness_rates = rates;
    const mechanisms = checkedValues(document.getElementById("exp-mechanisms"));
    if (mechanisms.length) form.missingness_mechanisms = mechanisms;
  }
  return form;
}

async function launchRun(event) {
  event.preventDefault();
  const banner = document.getElementById("exp-banner");
  clearChildren(banner);
  try {
    const result = await apiCall("/api/runs", { method: "POST", body: readForm() });
    showBanner(banner, `Launched run ${result.run_id} on ${result.engine}. See the Runs page to track it.`, "info");
  } catch (err) {
    showBanner(banner, err.message);
  }
}

async function saveConfigOnly() {
  const banner = document.getElementById("exp-banner");
  clearChildren(banner);
  try {
    const result = await apiCall("/api/experiments", { method: "POST", body: readForm() });
    showBanner(banner, `Saved config for ${result.engine} at ${result.config_path}`, "info");
  } catch (err) {
    showBanner(banner, err.message);
  }
}

document.addEventListener("DOMContentLoaded", () => {
  document.getElementById("exp-engine").addEventListener("change", loadChoices);
  document.getElementById("exp-factor").addEventListener("change", loadChoices);
  document.getElementById("exp-form").addEventListener("submit", launchRun);
  document.getElementById("exp-save").addEventListener("click", saveConfigOnly);
  loadChoices();
});
