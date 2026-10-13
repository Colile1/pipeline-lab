# findings.py: turn recorded runs into stated findings.
#
# The dashboard shows means, which answer "what happened". This module
# answers "is it real", by running the same framework the engine's own
# analyse.py uses: Friedman across a component's levels, then
# baseline-referenced Wilcoxon with Holm, effect sizes always.
#
# Two guards matter more than the arithmetic, because both were found by
# running real sweeps rather than by reasoning:
#
# 1. PAIRED COMPLETENESS. Friedman and Wilcoxon pair across datasets. A
#    level missing one dataset must drop out, or the test silently
#    compares different dataset sets to each other.
#
# 2. THE DISCRETENESS FLOOR. Wilcoxon's smallest attainable two-sided p
#    is 2/2**n. Holm then tests the smallest of k comparisons at
#    alpha/k. With 6 datasets and 3 contrasts the floor is 0.03125 and
#    the bar is 0.0167, so a perfect 6-of-6 result cannot be rejected
#    however large the effect. Reporting that as "no difference" would
#    present an arithmetic limit as evidence. Every result therefore
#    carries a power verdict, and the UI shows it.
from __future__ import annotations

import sys

from . import catalogue

# scipy lives in the engine's venv, not the dashboard's. Importing the
# engine's statistics module would drag numpy and sklearn in with it, so
# the dashboard asks the engine's interpreter instead when it must.
# Friedman and Wilcoxon on a handful of datasets are cheap enough to run
# in-process IF scipy is importable; when it is not, the UI says so
# rather than inventing a p-value.
try:  # pragma: no cover - environment-dependent
    from scipy import stats as _scipy_stats
except ImportError:  # pragma: no cover
    _scipy_stats = None

ALPHA = 0.05


def scipy_available() -> bool:
    return _scipy_stats is not None


def wilcoxon_floor(n_pairs: int) -> float:
    """Smallest two-sided Wilcoxon p attainable with n pairs."""
    if n_pairs < 1:
        return 1.0
    return min(1.0, 2.0 / (2 ** n_pairs))


def datasets_needed(threshold: float) -> int | None:
    """Smallest n whose floor clears a threshold."""
    for n in range(2, 64):
        if wilcoxon_floor(n) <= threshold:
            return n
    return None


def holm_adjust(p_values: list[float]) -> list[float]:
    """Holm step-down adjustment, preserving input order.

    Holm over Bonferroni per the methodology: same family-wise error
    guarantee, uniformly more power.
    """
    indexed = sorted(enumerate(p_values), key=lambda pair: pair[1])
    k = len(p_values)
    adjusted = [0.0] * k
    running = 0.0
    for rank, (position, p) in enumerate(indexed):
        value = min(1.0, (k - rank) * p)
        running = max(running, value)  # enforce monotonicity
        adjusted[position] = running
    return adjusted


def _paired_scores(rows, component, levels, metric, datasets):
    """{level: [score per dataset]} for levels complete on every dataset."""
    scores = {}
    for level in levels:
        column = []
        for dataset in datasets:
            match = [
                r for r in rows
                if r[component] == level and r["dataset"] == dataset
                and r[metric] is not None
            ]
            if not match:
                column = None
                break
            column.append(match[0][metric])
        if column is not None:
            scores[level] = column
    return scores


def _complete_datasets(rows, component, levels, metric, datasets):
    keep = []
    for dataset in datasets:
        have = {
            r[component] for r in rows
            if r["dataset"] == dataset and r[metric] is not None
        }
        if all(level in have for level in levels):
            keep.append(dataset)
    return keep


def _effect(baseline_scores, level_scores, higher_is_better):
    """Median paired difference, in the direction that means better."""
    diffs = [
        (b - a) if not higher_is_better else (a - b)
        for a, b in zip(level_scores, baseline_scores)
    ]
    ordered = sorted(diffs)
    n = len(ordered)
    median = (ordered[n // 2] if n % 2
              else (ordered[n // 2 - 1] + ordered[n // 2]) / 2)
    return {
        "median_difference": median,
        "n_pairs": n,
        "n_improved": sum(1 for d in diffs if d > 0),
        "n_worsened": sum(1 for d in diffs if d < 0),
        "n_tied": sum(1 for d in diffs if d == 0),
        "differences": diffs,
    }


# Under injected missingness the Chapter 1 imputation baseline cannot be
# the reference level. drop_rows is skipped on most datasets once a
# meaningful share of cells is blank, and where it does run it is trained
# and tested on complete rows only, so its score is not comparable with an
# imputer's score on the full data. The engine's analyse.py reads these
# sweeps with mean as the reference and drop_rows left out; the dashboard
# must do the same or it would show the misleading comparison.
INJECTED_REFERENCE = "mean"
INJECTED_EXCLUDE = ("drop_rows",)
INJECTED_NOTE = (
    "Compared against mean imputation, not against deleting rows. In this "
    "experiment gaps were blanked on purpose, and row deletion is left out "
    "because it is scored on a different, smaller set of rows: it keeps "
    "only complete rows, so its result cannot be set beside an imputer's "
    "on equal terms. This departs from the study's usual baseline and is "
    "reported as such."
)


def reference_for(component: str, rows: list[dict]) -> tuple[str | None, tuple, str]:
    """Decide the reference level for a sweep.

    Output: (reference or None for the declared baseline, levels to
    exclude, a reader-facing note that is empty when nothing changed).
    """
    injected = any(r.get("injected_rate") is not None for r in rows)
    if component == "imputation" and injected:
        return INJECTED_REFERENCE, INJECTED_EXCLUDE, INJECTED_NOTE
    return None, (), ""


def analyse(config_name: str, metric: str, task_type: str,
            model: str | None = None, alpha: float = ALPHA) -> dict:
    """Run the full framework over one sweep and return a stated finding."""
    if not scipy_available():
        return {
            "available": False,
            "reason": "scipy is not installed in the dashboard's environment, "
                      "so no test can be run here. The numbers shown elsewhere "
                      "are recorded measurements and are unaffected.",
        }

    data = catalogue.runs(config_name=config_name, status="succeeded", limit=2000)
    rows = [r for r in data["rows"] if r["task_type"] == task_type]
    if model:
        rows = [r for r in rows if r["model"] == model]
    if not rows:
        return {"available": False, "reason": "no succeeded runs match."}

    component = rows[0]["vary"]
    levels_present = sorted({r[component] for r in rows if r[component]})
    # The baseline is the level the engine declares first for this
    # component, never guessed from the data.
    catalogue.engine_src_on_path()
    from piplab.config import TECHNIQUES

    reference, excluded, reference_note = reference_for(component, rows)
    declared_baseline = TECHNIQUES[component][0]
    ordered = [lv for lv in TECHNIQUES[component]
               if lv in levels_present and lv not in excluded]
    if len(ordered) < 2:
        return {"available": False,
                "reason": f"only one {component} level was run; nothing to compare."}
    baseline = reference if reference in ordered else ordered[0]
    # Keep the reference first: the contrasts are everything after it.
    ordered = [baseline] + [lv for lv in ordered if lv != baseline]

    all_datasets = sorted({r["dataset"] for r in rows})
    datasets = _complete_datasets(rows, component, ordered, metric, all_datasets)
    dropped = sorted(set(all_datasets) - set(datasets))
    if len(datasets) < 2:
        return {"available": False,
                "reason": f"fewer than two datasets have a score at every "
                          f"{component} level, so nothing can be paired."}

    scores = _paired_scores(rows, component, ordered, metric, datasets)
    higher_is_better = catalogue.METRICS[metric]

    columns = [scores[lv] for lv in ordered]
    friedman_stat, friedman_p = _scipy_stats.friedmanchisquare(*columns)

    result = {
        "available": True,
        "config_name": config_name,
        "component": component,
        "baseline": baseline,
        "declared_baseline": declared_baseline,
        "uses_declared_baseline": baseline == declared_baseline,
        "excluded_levels": list(excluded),
        "reference_note": reference_note,
        "metric": metric,
        "task_type": task_type,
        "model": model,
        "datasets": datasets,
        "dropped_datasets": dropped,
        "n_datasets": len(datasets),
        "higher_is_better": higher_is_better,
        "friedman": {
            "statistic": friedman_stat,
            "p_value": friedman_p,
            "significant": bool(friedman_p < alpha),
        },
        "alpha": alpha,
        "comparisons": [],
        "skipped_reason": "",
        "power": {},
    }

    if friedman_p >= alpha:
        result["skipped_reason"] = (
            f"The overall test found no difference between the "
            f"{component} options (p = {friedman_p:.4g}). Comparing them "
            f"one by one now would inflate the chance of a false positive, "
            f"so the framework stops here."
        )
        return result

    contrasts = [lv for lv in ordered if lv != baseline]
    raw, effects = [], []
    for level in contrasts:
        pairs = [
            (a, b) for a, b in zip(scores[level], scores[baseline]) if a != b
        ]
        if not pairs:
            raw.append(1.0)
            effects.append(_effect(scores[baseline], scores[level], higher_is_better))
            continue
        _, p = _scipy_stats.wilcoxon(
            [a for a, _ in pairs], [b for _, b in pairs]
        )
        raw.append(float(p))
        effects.append(_effect(scores[baseline], scores[level], higher_is_better))

    adjusted = holm_adjust(raw)
    for level, p, p_adj, effect in zip(contrasts, raw, adjusted, effects):
        result["comparisons"].append({
            "level": level,
            "baseline": baseline,
            "p_value": p,
            "p_adjusted": p_adj,
            "rejected": bool(p_adj < alpha),
            "effect": effect,
        })
    result["comparisons"].sort(key=lambda c: c["p_adjusted"])

    # The power verdict: can ANY comparison be rejected at this n?
    k = len(contrasts)
    floor = wilcoxon_floor(len(datasets))
    bar = alpha / k if k else alpha
    result["power"] = {
        "n_datasets": len(datasets),
        "n_comparisons": k,
        "wilcoxon_floor": floor,
        "holm_bar": bar,
        "underpowered": floor > bar,
        "datasets_needed": datasets_needed(bar),
    }
    return result


def headline(config_name: str) -> list[dict]:
    """Every testable finding in one sweep, for the dashboard."""
    data = catalogue.runs(config_name=config_name, status="succeeded", limit=2000)
    rows = data["rows"]
    out = []
    for task in sorted({r["task_type"] for r in rows if r["task_type"]}):
        metrics = (["accuracy_mean", "f1_mean"] if task == "classification"
                   else ["rmse_mean"])
        models = sorted({r["model"] for r in rows if r["task_type"] == task})
        for model in models:
            for metric in metrics:
                found = analyse(config_name, metric, task, model)
                if found.get("available"):
                    out.append(found)
    return out
