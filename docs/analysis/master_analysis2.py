"""The injected sweeps read the OTHER way: against drop_rows.

4k asked "does imputing beat deleting?" (baseline drop_rows, all four
levels). 4n/4x asked "which imputer is best?" (baseline mean, drop_rows
excluded). Both are legitimate and answer different questions; the
report needs both, so this computes the first, which master_analysis.py
deliberately left out.
"""
import os
import json
import pathlib
import sqlite3
import sys

sys.path.insert(0, os.environ.get("PIPELAB_ENGINE_SRC", r"C:/Users/Colile/Documents/School/NWU/S1/ITRI671 Project/pipeline-lab-engine/src"))
from piplab.statistics.tests import compare_levels, StatisticsError

DB = os.environ.get("PIPELAB_DB", r"C:/Users/Colile/Documents/School/NWU/S1/ITRI671 Project/pipeline-lab-engine/outputs/lab.db")
OUT = pathlib.Path(os.environ.get("PIPELAB_OUT", pathlib.Path(__file__).resolve().parent / "out"))
OUT.mkdir(parents=True, exist_ok=True)
METRIC = {"classification": ["accuracy_mean", "f1_mean"], "regression": ["rmse_mean"]}
COL = {"accuracy_mean": 4, "f1_mean": 5, "rmse_mean": 6}

SWEEPS = ["ofat_imputation_mcar05", "ofat_imputation_mcar15", "ofat_imputation_mcar30",
          "ofat_imputation_mar05", "ofat_imputation_mar15", "ofat_imputation_mar30"]

results = []
with sqlite3.connect(f"file:{DB}?mode=ro", uri=True) as conn:
    for config in SWEEPS:
        rows = conn.execute(
            "select dataset, model, imputation, task_type, accuracy_mean, f1_mean, rmse_mean "
            "from runs where config_name = ? and status = 'succeeded'", (config,)).fetchall()
        for task in ("classification", "regression"):
            for metric in METRIC[task]:
                idx = COL[metric]
                higher = metric != "rmse_mean"
                for model in sorted({r[1] for r in rows if r[3] == task}):
                    table = {}
                    for r in rows:
                        if r[3] != task or r[1] != model or r[idx] is None:
                            continue
                        table.setdefault(r[0], {})[r[2]] = r[idx]
                    levels = sorted({l for d in table.values() for l in d})
                    if "drop_rows" not in levels:
                        continue
                    complete = {d: v for d, v in table.items() if len(v) == len(levels)}
                    if len(complete) < 2:
                        continue
                    ds = sorted(complete)
                    scores = {l: [complete[d][l] for d in ds] for l in levels}
                    try:
                        res = compare_levels(scores, "drop_rows", higher_is_better=higher)
                    except StatisticsError:
                        continue
                    results.append({
                        "config": config, "task": task, "metric": metric, "model": model,
                        "n_datasets": len(ds), "baseline": "drop_rows",
                        "friedman_p": res.friedman.p_value,
                        "significant": res.friedman.significant,
                        "means": {l: sum(v) / len(v) for l, v in scores.items()},
                        "comparisons": [{
                            "level": c.level, "p_adj": c.p_adjusted, "rejected": c.rejected,
                            "median_diff": c.effect.median_difference,
                            "n_improved": c.effect.n_improved, "n_pairs": c.effect.n_pairs,
                        } for c in res.comparisons],
                    })

(OUT / "master_results_droprows.json").write_text(json.dumps(results, indent=1), encoding="utf-8")
n = sum(1 for e in results for c in e["comparisons"] if c["rejected"])
print(f"{len(results)} cells, {sum(1 for e in results if e['significant'])} significant, "
      f"{n} rejected contrasts\n")
print("=== imputing vs deleting (drop_rows baseline), rejected only ===")
for e in results:
    for c in e["comparisons"]:
        if c["rejected"]:
            print(f"{e['config']:24} {e['model']:18} {e['metric']:14} {c['level']:10} "
                  f"Holm={c['p_adj']:.4f} {c['n_improved']}/{c['n_pairs']} n={e['n_datasets']}")
