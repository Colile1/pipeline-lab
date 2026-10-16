"""Dataset-characteristic meta-analysis over the existing record.

The question: which properties of a dataset predict that a preprocessing
choice will matter for a given model?

Unit of analysis is one (dataset, model, factor) cell. The response is
the SPREAD across that factor's levels -- how much the choice moved the
score at all -- expressed as a percentage of the baseline score so that
datasets on different target scales are comparable.

No new experiments: every number comes from runs already recorded.

Two corrections built in deliberately:
  * missing_pct must be read from UNINJECTED runs only, otherwise the
    injection sweeps overwrite the natural rate (iris would read 30%).
  * regression spread is normalised by the baseline RMSE, because raw
    RMSE is not comparable between datasets.
"""
import json
import pathlib
import sqlite3
import sys

sys.path.insert(0, r"C:/Users/Colile/Documents/School/NWU/S1/ITRI671 Project/pipeline-lab-engine/src")

import numpy as np
from scipy import stats

DB = r"C:/Users/Colile/Documents/School/NWU/S1/ITRI671 Project/pipeline-lab-engine/outputs/lab.db"
OUT = pathlib.Path(__file__).resolve().parent

# Only the uninjected, single-sweep-per-factor configs: these are the
# arms where a factor was varied against a common baseline on a shared
# dataset set. Injected sweeps are excluded because missingness rate is
# then a manipulated variable, not a dataset characteristic.
ARMS = {
    "scaling": ("ofat_scaling_v2", "none"),
    "encoding": ("ofat_encoding_v2", "onehot"),
    "selection": ("ofat_selection_v2", "none"),
    "tuning": ("ofat_tuning_v3", "none"),
}


def characteristics(conn):
    """Per-dataset properties, with natural missingness read correctly."""
    chars = {}
    for d, task, rows, feats, num, cat, bal, corr in conn.execute("""
        select dataset, task_type, max(n_rows_before_deletion), max(n_features_raw),
               max(n_numeric), max(n_categorical), max(class_balance),
               max(mean_abs_correlation)
        from runs where status = 'succeeded' group by dataset"""):
        chars[d] = {
            "task": task, "n_rows": rows, "n_features": feats,
            "n_numeric": num, "n_categorical": cat,
            "cat_fraction": (cat / feats) if feats else 0.0,
            "class_balance": bal, "mean_abs_correlation": corr,
        }
    # natural missingness: uninjected runs only
    for d, miss in conn.execute("""
        select dataset, max(missing_pct) from runs
        where status = 'succeeded' and injected_rate is null group by dataset"""):
        if d in chars:
            chars[d]["missing_pct"] = miss
    return chars


def spreads(conn):
    """One row per (dataset, model, factor): how much did the choice move the score?"""
    rows = []
    for factor, (config, baseline) in ARMS.items():
        recs = conn.execute(f"""
            select dataset, model, {factor}, task_type, accuracy_mean, f1_mean, rmse_mean
            from runs where config_name = ? and status = 'succeeded'""", (config,)).fetchall()
        groups = {}
        for d, m, lvl, task, acc, f1, rmse in recs:
            score = rmse if task == "regression" else acc
            if score is None:
                continue
            groups.setdefault((d, m, task), {})[lvl] = score
        for (d, m, task), levels in groups.items():
            if baseline not in levels or len(levels) < 2:
                continue
            base = levels[baseline]
            if not base:
                continue
            vals = list(levels.values())
            # spread as % of baseline: comparable across datasets and metrics
            spread_pct = 100.0 * (max(vals) - min(vals)) / abs(base)
            # signed best gain over baseline, also as % of baseline
            if task == "regression":
                best = min(vals)
                gain_pct = 100.0 * (base - best) / abs(base)
            else:
                best = max(vals)
                gain_pct = 100.0 * (best - base) / abs(base)
            rows.append({
                "dataset": d, "model": m, "factor": factor, "task": task,
                "spread_pct": spread_pct, "gain_pct": gain_pct,
                "n_levels": len(levels),
            })
    return rows


def correlate(cells, chars, factor, prop, model=None, task=None):
    """Spearman correlation between a dataset property and the factor's spread."""
    xs, ys, ds = [], [], []
    for c in cells:
        if c["factor"] != factor:
            continue
        if model and c["model"] != model:
            continue
        if task and c["task"] != task:
            continue
        ch = chars.get(c["dataset"], {})
        v = ch.get(prop)
        if v is None:
            continue
        xs.append(v); ys.append(c["spread_pct"]); ds.append(c["dataset"])
    if len(xs) < 5 or len(set(xs)) < 3:
        return None
    rho, p = stats.spearmanr(xs, ys)
    return {"factor": factor, "property": prop, "model": model, "task": task,
            "n": len(xs), "rho": float(rho), "p": float(p)}


with sqlite3.connect(f"file:{DB}?mode=ro", uri=True) as conn:
    chars = characteristics(conn)
    cells = spreads(conn)

print(f"{len(cells)} (dataset, model, factor) cells\n")

# ---- 1. How much does each factor move scores, by model? --------------
print("=== Factor sensitivity: median spread (% of baseline score) ===")
print(f"{'factor':11} {'model':19} {'n':>3} {'median':>8} {'p90':>8}  max dataset")
sens = []
for factor in ARMS:
    for model in ("logreg", "svm", "random_forest", "gradient_boosting"):
        sel = [c for c in cells if c["factor"] == factor and c["model"] == model]
        if not sel:
            continue
        sp = [c["spread_pct"] for c in sel]
        worst = max(sel, key=lambda c: c["spread_pct"])
        sens.append({"factor": factor, "model": model, "n": len(sp),
                     "median": float(np.median(sp)), "p90": float(np.percentile(sp, 90)),
                     "max_dataset": worst["dataset"], "max_spread": worst["spread_pct"]})
        print(f"{factor:11} {model:19} {len(sp):>3} {np.median(sp):>7.2f}% "
              f"{np.percentile(sp,90):>7.2f}%  {worst['dataset']} ({worst['spread_pct']:.1f}%)")

# ---- 2. Which dataset properties predict sensitivity? -----------------
PROPS = ["n_rows", "n_features", "cat_fraction", "missing_pct",
         "mean_abs_correlation", "class_balance"]
print("\n=== Does a dataset property predict how much a factor matters? ===")
print("(Spearman rho over datasets, pooled across models within a factor)")
print(f"{'factor':11} {'property':22} {'n':>3} {'rho':>7} {'p':>8}")
corrs = []
for factor in ARMS:
    for prop in PROPS:
        r = correlate(cells, chars, factor, prop)
        if r:
            corrs.append(r)
            flag = "  <-- significant" if r["p"] < 0.05 else ""
            print(f"{factor:11} {prop:22} {r['n']:>3} {r['rho']:>7.3f} {r['p']:>8.4f}{flag}")

# ---- 3. The targeted question: scaling sensitivity per model ----------
print("\n=== Scaling sensitivity vs feature-scale disparity, per model ===")
print("(the house_16H mechanism, tested across the registry)")
for model in ("logreg", "svm", "random_forest", "gradient_boosting"):
    r = correlate(cells, chars, "scaling", "mean_abs_correlation", model=model)
    if r:
        print(f"  {model:19} rho={r['rho']:>6.3f} p={r['p']:.4f} n={r['n']}")

json.dump({"cells": cells, "characteristics": chars, "sensitivity": sens,
           "correlations": corrs},
          open(OUT / "meta_analysis_results.json", "w"), indent=1)
print(f"\nwritten: {OUT / 'meta_analysis_results.json'}")
