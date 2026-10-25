"""Compute every arm's result from the record, for the master report.

Nothing here is recalled; every number is read from lab.db and tested
with the engine's own compare_levels (Friedman -> Wilcoxon -> Holm).
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


def arm(conn, config, vary, baseline, exclude=()):
    rows = conn.execute(
        f"select dataset, model, {vary} lvl, task_type, accuracy_mean, f1_mean, rmse_mean "
        f"from runs where config_name = ? and status = 'succeeded'",
        (config,),
    ).fetchall()
    out = []
    for task in ("classification", "regression"):
        for metric in METRIC[task]:
            idx = COL[metric]
            higher = metric != "rmse_mean"
            for model in sorted({r[1] for r in rows if r[3] == task}):
                table = {}
                for r in rows:
                    if r[3] != task or r[1] != model or r[idx] is None or r[2] in exclude:
                        continue
                    table.setdefault(r[0], {})[r[2]] = r[idx]
                levels = sorted({l for d in table.values() for l in d})
                if baseline not in levels or len(levels) < 2:
                    continue
                complete = {d: v for d, v in table.items() if len(v) == len(levels)}
                if len(complete) < 2:
                    continue
                datasets = sorted(complete)
                scores = {l: [complete[d][l] for d in datasets] for l in levels}
                try:
                    res = compare_levels(scores, baseline, higher_is_better=higher)
                except StatisticsError:
                    continue
                out.append({
                    "config": config, "vary": vary, "task": task, "metric": metric,
                    "model": model, "n_datasets": len(datasets), "baseline": baseline,
                    "levels": levels,
                    "friedman_p": res.friedman.p_value,
                    "friedman_stat": res.friedman.statistic,
                    "kendalls_w": res.friedman.kendalls_w,
                    "significant": res.friedman.significant,
                    "means": {l: sum(v) / len(v) for l, v in scores.items()},
                    "comparisons": [{
                        "level": c.level, "p": c.p_value, "p_adj": c.p_adjusted,
                        "rejected": c.rejected,
                        "median_diff": c.effect.median_difference,
                        "ci_low": c.effect.ci_low, "ci_high": c.effect.ci_high,
                        "n_improved": c.effect.n_improved, "n_pairs": c.effect.n_pairs,
                    } for c in res.comparisons],
                })
    return out


ARMS = [
    # (config, vary, baseline, excluded levels)
    ("ofat_scaling_v2", "scaling", "none", ()),
    ("ofat_encoding_v2", "encoding", "onehot", ()),
    ("ofat_selection_v2", "selection", "none", ()),
    ("ofat_tuning_v3", "tuning", "none", ()),
    ("ofat_imputation_v2", "imputation", "drop_rows", ()),
    ("ofat_imputation_mcar05", "imputation", "mean", ("drop_rows",)),
    ("ofat_imputation_mcar15", "imputation", "mean", ("drop_rows",)),
    ("ofat_imputation_mcar30", "imputation", "mean", ("drop_rows",)),
    ("ofat_imputation_mar05", "imputation", "mean", ("drop_rows",)),
    ("ofat_imputation_mar15", "imputation", "mean", ("drop_rows",)),
    ("ofat_imputation_mar30", "imputation", "mean", ("drop_rows",)),
    ("ofat_selection_k25", "selection", "none", ()),
    ("ofat_selection_k75", "selection", "none", ()),
    ("ofat_scaling_large", "scaling", "none", ()),
    ("ofat_scaling_large_svm", "scaling", "none", ()),
    ("ofat_encoding_large", "encoding", "onehot", ()),
    ("ofat_selection_large", "selection", "none", ()),
    ("ofat_tuning_large", "tuning", "none", ()),
    ("holdout_large", "scaling", "none", ()),
]

with sqlite3.connect(f"file:{DB}?mode=ro", uri=True) as conn:
    results = []
    for config, vary, baseline, exclude in ARMS:
        results.extend(arm(conn, config, vary, baseline, exclude))

(OUT / "master_results.json").write_text(json.dumps(results, indent=1), encoding="utf-8")

print(f"{len(results)} (config, task, metric, model) cells computed")
print(f"{sum(1 for e in results if e['significant'])} with a significant global test\n")
print("=== EVERY REJECTED CONTRAST IN THE PROGRAMME ===")
n = 0
for e in results:
    for c in e["comparisons"]:
        if c["rejected"]:
            n += 1
            print(f"{e['config']:24} {e['model']:18} {e['metric']:14} "
                  f"{c['level']:12} vs {e['baseline']:10} "
                  f"Holm={c['p_adj']:.4f} {c['n_improved']}/{c['n_pairs']} "
                  f"n={e['n_datasets']} F_p={e['friedman_p']:.4f}")
print(f"\ntotal rejected contrasts: {n}")
