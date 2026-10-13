// findings.js - states what each experiment found, in words first.
//
// The hard part of this page is not drawing it, it is saying true things
// simply. Three rules:
//
//  1. Never report a comparison the global test did not license.
//  2. Never present a power limit as a null result. When the test
//     arithmetically cannot reject at this number of datasets, say so
//     loudly, because "no difference" and "could not tell" look
//     identical in a table and mean opposite things.
//  3. Never show a p-value without the size of the effect beside it.

const METRIC_WORDS = {
  accuracy_mean: "accuracy (how often the model is right)",
  f1_mean: "macro-F1 (accuracy that treats small classes as equally important)",
  rmse_mean: "error size (RMSE, how far predictions land from the truth)",
};

const COMPONENT_WORDS = {
  scaling: "putting features on a comparable scale",
  imputation: "filling in missing values",
  encoding: "turning categories into numbers",
  selection: "choosing which columns to keep",
  tuning: "searching for the model's settings",
};

function plainMetric(metric) {
  return METRIC_WORDS[metric] || metric;
}

/** The headline sentence: what this finding says, in one line. */
function verdictLine(finding) {
  const comp = COMPONENT_WORDS[finding.component] || finding.component;
  const model = finding.model ? `for ${finding.model}` : "";
  if (!finding.friedman.significant) {
    return `No reliable difference between the ${finding.component} options `
      + `${model}, measured on ${finding.n_datasets} datasets.`;
  }
  const won = finding.comparisons.filter((c) => c.rejected);
  if (!won.length) {
    return `The options do differ overall ${model}, but no single option `
      + `could be singled out with this many datasets.`;
  }
  const names = won.map((c) => c.level).join(" and ");
  return `${names} beat "${finding.baseline}" ${model}, `
    + `measured on ${finding.n_datasets} datasets.`;
}

function verdictClass(finding) {
  if (!finding.friedman.significant) return "verdict null";
  if (finding.comparisons.some((c) => c.rejected)) return "verdict positive";
  return "verdict unclear";
}

function comparisonTable(finding) {
  const table = document.createElement("table");
  table.className = "data-table";
  const head = document.createElement("thead");
  head.innerHTML = "<tr>"
    + "<th>Option</th><th>Verdict</th><th>Typical change</th>"
    + "<th>Datasets it helped</th><th>p (adjusted)</th></tr>";
  table.appendChild(head);
  const body = document.createElement("tbody");

  finding.comparisons.forEach((c) => {
    const tr = document.createElement("tr");
    const effect = c.effect;

    const level = document.createElement("td");
    level.textContent = `${c.level} vs ${c.baseline}`;
    tr.appendChild(level);

    const verdict = document.createElement("td");
    verdict.textContent = c.rejected ? "real difference" : "not established";
    verdict.className = c.rejected ? "status-success" : "status-unknown";
    tr.appendChild(verdict);

    const change = document.createElement("td");
    const sign = effect.median_difference >= 0 ? "+" : "";
    change.textContent = `${sign}${fmt(effect.median_difference)}`;
    change.title = finding.higher_is_better
      ? "median change in the score; positive means better"
      : "median reduction in error; positive means better";
    tr.appendChild(change);

    const wins = document.createElement("td");
    wins.appendChild(winLossBar(effect.n_improved, effect.n_worsened, effect.n_tied));
    tr.appendChild(wins);

    const p = document.createElement("td");
    p.textContent = fmt(c.p_adjusted, 4);
    p.title = `raw p = ${fmt(c.p_value, 5)}, Holm-adjusted = ${fmt(c.p_adjusted, 5)}`;
    tr.appendChild(p);

    body.appendChild(tr);
  });
  table.appendChild(body);
  return table;
}

function powerWarning(finding) {
  const power = finding.power || {};
  if (!power.underpowered) return null;
  const box = document.createElement("div");
  box.className = "banner banner-error";
  box.appendChild(paragraph(
    `Not enough datasets to decide. With ${power.n_datasets} datasets the `
    + `smallest p-value this test can possibly produce is `
    + `${fmt(power.wilcoxon_floor, 5)}, and after correcting for `
    + `${power.n_comparisons} comparisons it would need to be below `
    + `${fmt(power.holm_bar, 5)}. Nothing here can be declared real `
    + `however large the difference. Read the "typical change" and `
    + `"datasets it helped" columns instead of the verdicts, and treat `
    + `${power.datasets_needed} datasets as the minimum for a decision.`));
  return box;
}

function findingCard(finding) {
  const card = document.createElement("div");
  card.className = "card wide";

  const title = document.createElement("p");
  title.className = "card-title";
  title.textContent =
    `${finding.model || "all models"} - ${plainMetric(finding.metric)}`;
  card.appendChild(title);

  const verdict = document.createElement("p");
  verdict.className = verdictClass(finding);
  verdict.textContent = verdictLine(finding);
  card.appendChild(verdict);

  const warning = powerWarning(finding);
  if (warning) card.appendChild(warning);

  if (finding.friedman.significant && finding.comparisons.length) {
    card.appendChild(comparisonTable(finding));
  } else if (finding.skipped_reason) {
    card.appendChild(paragraph(finding.skipped_reason, "muted"));
  }

  // --- layer 2: how this was decided
  card.appendChild(explainer("How was this decided?", [
    "Two steps, in order. First one test asks whether the options differ "
    + "at all. Only if that says yes is each option compared against the "
    + "baseline individually. Checking every pair without that first "
    + "step would find 'differences' by chance alone.",
    `The overall test here gave p = ${fmt(finding.friedman.p_value, 5)}, `
    + `which is ${pInWords(finding.friedman.p_value)}.`,
    "A p-value is the chance of seeing a pattern this strong if the "
    + "options were really identical. Small means the pattern is hard to "
    + "explain as luck. It does not say how big the difference is, which "
    + "is why the size of the change is always shown next to it.",
    "Because several options are compared at once, the p-values are "
    + "adjusted upward (the Holm correction). Testing four things gives "
    + "four chances to be fooled, and the adjustment prices that in.",
  ]));

  // --- layer 3: what was measured, and what was left out
  const detail = [];
  detail.push(paragraph(
    `Datasets used: ${finding.datasets.join(", ")}.`));
  if (finding.dropped_datasets.length) {
    detail.push(paragraph(
      `Left out: ${finding.dropped_datasets.join(", ")}. A dataset is only `
      + `usable here if it has a score for every option, because the test `
      + `compares them on the same footing. A dataset missing one option `
      + `would quietly change what is being compared.`));
  }
  detail.push(paragraph(
    "Each score is the average over 10 cross-validation folds: the data "
    + "is split ten ways, and every split is used once for testing and "
    + "nine times for training. Every transformation is fitted inside "
    + "the training part only, so nothing about the test rows can leak "
    + "into the preparation."));
  detail.push(paragraph(
    finding.higher_is_better
      ? "For this measure, higher is better."
      : "For this measure, lower is better, so a positive 'typical "
        + "change' means the error went down."));
  card.appendChild(explainer("What exactly was measured?", detail));

  // --- layer 4: what it means in practice
  card.appendChild(explainer("What does this mean in practice?", [
    verdictPractical(finding),
    "One caution that applies to every result on this page: these are "
    + "public benchmark datasets, not your data. A finding here is "
    + "evidence about what usually happens, which is a good default and "
    + "a poor guarantee. The honest use of it is to choose where to "
    + "spend your attention first.",
  ]));

  return card;
}

function verdictPractical(finding) {
  const comp = COMPONENT_WORDS[finding.component] || finding.component;
  if (!finding.friedman.significant) {
    return `On this evidence, ${comp} did not reliably change the result `
      + `for this model. That is a useful finding rather than a failed `
      + `experiment: it suggests effort is better spent elsewhere, and a `
      + `null result reported honestly is worth more than a weak one `
      + `dressed up.`;
  }
  const won = finding.comparisons.filter((c) => c.rejected);
  if (!won.length) {
    return `Something in this group of options matters, but the evidence `
      + `is not yet sharp enough to say which. More datasets would settle `
      + `it.`;
  }
  const best = won[0];
  return `A sensible default for this model is "${best.level}". It was `
    + `better on ${best.effect.n_improved} of ${best.effect.n_pairs} `
    + `datasets, with a typical change of `
    + `${fmt(best.effect.median_difference)}. Whether that is worth having `
    + `depends on your setting: on a small dataset it can be inside the `
    + `noise, and on a large one it can matter a great deal.`;
}

async function loadFindings(sweep) {
  const target = document.getElementById("findings");
  const banner = document.getElementById("findings-banner");
  clearChildren(target);
  clearChildren(banner);
  if (!sweep) return;

  let data;
  try {
    data = await apiCall(
      `/api/analysis/findings?config_name=${encodeURIComponent(sweep)}`);
  } catch (err) {
    showBanner(banner, err.message);
    return;
  }
  if (!data.available) {
    showBanner(banner, data.reason, "info");
    return;
  }
  if (!data.findings.length) {
    target.appendChild(paragraph(
      "This sweep has no completed runs to test yet.", "muted"));
    return;
  }
  data.findings.forEach((f) => target.appendChild(findingCard(f)));
}

async function populateSweeps() {
  const select = document.getElementById("sweep-pick");
  const data = await apiCall("/api/analysis/sweeps");
  const wanted = new URLSearchParams(location.search).get("sweep");
  const current = select.value;
  clearChildren(select);
  data.sweeps.forEach((s) => {
    const option = document.createElement("option");
    option.value = s.config_name;
    option.textContent = `${s.config_name} (varies ${s.vary}, ${s.runs} runs)`;
    select.appendChild(option);
  });
  const pick = current || wanted || (data.sweeps[0] && data.sweeps[0].config_name);
  if (pick) select.value = pick;
  return select.value;
}

document.addEventListener("DOMContentLoaded", async () => {
  const select = document.getElementById("sweep-pick");
  select.addEventListener("change", () => loadFindings(select.value));
  watchRecord(async (pulse) => {
    renderPulse(document.getElementById("pulse"), pulse);
    const sweep = await populateSweeps();
    await loadFindings(sweep);
  });
});
