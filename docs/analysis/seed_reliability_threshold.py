"""When can a single-seed result be trusted?

The seed replication showed that the scaling contrast reaches
significance under one seed of three. This asks a more useful question
of the same data: does the instability fall evenly across datasets, or
does it concentrate where the effect is small?

If it concentrates, the study can offer a threshold: an effect below
some size should not be trusted from a single fold assignment at this
sample size. That is a statement other researchers can act on, and it
comes out of data already collected.
"""
import os
import pathlib
import sqlite3
import statistics
import sys

sys.path.insert(0, os.environ.get("PIPELAB_ENGINE_SRC", r"C:/Users/Colile/Documents/School/NWU/S1/ITRI671 Project/pipeline-lab-engine/src"))

DB = os.environ.get("PIPELAB_DB", r"C:/Users/Colile/Documents/School/NWU/S1/ITRI671 Project/pipeline-lab-engine/outputs/lab.db")
SEEDS = [("ofat_scaling_v2", 671),
         ("seed_check_scaling_1337", 1337),
         ("seed_check_scaling_20260702", 20260702)]
MODELS = ["logreg", "svm", "random_forest", "gradient_boosting"]


def per_dataset_effects(conn, model, level, baseline="none"):
    """Effect of `level` against `baseline` on each dataset, for each seed."""
    out = {}
    for config, seed in SEEDS:
        rows = conn.execute(
            "select dataset, scaling, accuracy_mean from runs "
            "where config_name = ? and model = ? and task_type = 'classification' "
            "and status = 'succeeded' and accuracy_mean is not null",
            (config, model),
        ).fetchall()
        table = {}
        for dataset, lvl, score in rows:
            table.setdefault(dataset, {})[lvl] = score
        for dataset, v in table.items():
            if level in v and baseline in v:
                out.setdefault(dataset, {})[seed] = v[level] - v[baseline]
    return {d: v for d, v in out.items() if len(v) == len(SEEDS)}


print("=" * 74)
print("DOES SEED INSTABILITY CONCENTRATE WHERE THE EFFECT IS SMALL?")
print("=" * 74)

all_rows = []
with sqlite3.connect(f"file:{DB}?mode=ro", uri=True) as conn:
    for model in MODELS:
        for level in ("standard", "minmax", "robust"):
            eff = per_dataset_effects(conn, model, level)
            for dataset, by_seed in eff.items():
                vals = list(by_seed.values())
                mean = statistics.mean(vals)
                agree = all(v > 0 for v in vals) or all(v < 0 for v in vals)
                all_rows.append({
                    "model": model, "level": level, "dataset": dataset,
                    "mean": mean, "abs": abs(mean),
                    "spread": max(vals) - min(vals), "agree": agree, "vals": vals,
                })

print(f"\n{len(all_rows)} (model, scaler, dataset) cells measured under all three seeds\n")

BANDS = [(0.000, 0.0025, "under 0.25 pp"),
         (0.0025, 0.005, "0.25 to 0.5 pp"),
         (0.005, 0.010, "0.5 to 1 pp"),
         (0.010, 0.020, "1 to 2 pp"),
         (0.020, 1.000, "over 2 pp")]

print(f"{'mean effect size':>18} {'cells':>7} {'agree on direction':>20} {'rate':>7}")
print("-" * 58)
for lo, hi, label in BANDS:
    band = [r for r in all_rows if lo <= r["abs"] < hi]
    if not band:
        continue
    agree = sum(r["agree"] for r in band)
    print(f"{label:>18} {len(band):>7} {agree:>20} {100 * agree / len(band):>6.0f}%")

# Cells where all three seeds return exactly zero are true no-ops (a
# tree ensemble under a scaler it ignores), not instability. Counting
# them as "disagree" would inflate the contrast, so they are excluded
# from the test and the conservative figures are the ones reported.
live = [r for r in all_rows
        if not all(abs(v) < 1e-12 for v in r["vals"])]
print()
print(f"  cells excluding true no-ops: {len(live)} of {len(all_rows)}")
small = [r for r in live if r["abs"] < 0.01]
large = [r for r in live if r["abs"] >= 0.01]
print()
print(f"  effect below 1 pp : {sum(r['agree'] for r in small)}/{len(small)} agree "
      f"({100 * sum(r['agree'] for r in small) / len(small):.0f}%)")
print(f"  effect at or above 1 pp: {sum(r['agree'] for r in large)}/{len(large)} agree "
      f"({100 * sum(r['agree'] for r in large) / len(large):.0f}%)")

# a formal test of the association
try:
    from scipy.stats import fisher_exact
    table = [[sum(r["agree"] for r in large), len(large) - sum(r["agree"] for r in large)],
             [sum(r["agree"] for r in small), len(small) - sum(r["agree"] for r in small)]]
    odds, p = fisher_exact(table)
    print(f"\n  Fisher exact test on (effect >= 1pp) x (seeds agree): "
          f"odds ratio {odds:.2f}, p = {p:.4f}")
except Exception as exc:  # pragma: no cover
    print("  (scipy unavailable:", exc, ")")

print()
print("=" * 74)
print("THE LEAST STABLE AND MOST STABLE CELLS")
print("=" * 74)
all_rows.sort(key=lambda r: r["spread"], reverse=True)
print("\nlargest disagreement between seeds:")
for r in all_rows[:5]:
    print(f"  {r['dataset']:16} {r['model']:18} {r['level']:9} "
          f"mean {r['mean']:+.4f}  spread {r['spread']:.4f}  agree={r['agree']}")
print("\nsmallest disagreement between seeds:")
for r in all_rows[-5:]:
    print(f"  {r['dataset']:16} {r['model']:18} {r['level']:9} "
          f"mean {r['mean']:+.4f}  spread {r['spread']:.4f}  agree={r['agree']}")
