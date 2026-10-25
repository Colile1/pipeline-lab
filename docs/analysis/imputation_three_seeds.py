"""The nine-dataset imputation arm under three random seeds.

Two seeds can only say whether a contrast agreed or disagreed. Three
give a rate: a contrast can be rejected under one, two or all three
draws, and the distribution of those counts says more about stability
than any single pairwise comparison. The scaling arm has been measured
this way since PROCESS-LOG 5b; this brings the imputation arm to the
same standard.

Seeds 671, 1337 and 20260702, the same three used for scaling, on the
original nine-dataset registry so the result is comparable with 5l
rather than with the widened arm (5u), which is measured separately.

drop_rows is excluded from the injected sweeps, matching
master_analysis.py and for the reason given there: listwise deletion
scores the model on a reduced sample, so its contrast is not against
the same data as the others.
"""
import os
import sqlite3
import sys
from collections import Counter

sys.path.insert(0, os.environ.get("PIPELAB_ENGINE_SRC", r"C:/Users/Colile/Documents/School/NWU/S1/ITRI671 Project/pipeline-lab-engine/src"))
from piplab.statistics.tests import StatisticsError, compare_levels

DB = os.environ.get("PIPELAB_DB", r"C:/Users/Colile/Documents/School/NWU/S1/ITRI671 Project/pipeline-lab-engine/outputs/lab.db")

SWEEPS = ["mcar05", "mcar15", "mcar30", "mar05", "mar15", "mar30"]
# (label, config prefix pattern) for the three draws of the same design.
SEEDS = [
    ("671", "ofat_imputation_{tag}"),
    ("1337", "seed_check_imputation_{tag}"),
    ("20260702", "third_seed_imputation_{tag}"),
]
METRICS = {
    "classification": [("accuracy_mean", True), ("f1_mean", True)],
    "regression": [("rmse_mean", False)],
}
BASELINE = "mean"
EXCLUDE = ("drop_rows",)


def contrasts(conn, config):
    """Return {(task, metric, model, level): rejected}, including cells
    the global test stopped, which count as not rejected rather than
    being dropped. Omitting them was the bug fixed in 5k."""
    out = {}
    for task, metrics in METRICS.items():
        for metric, higher in metrics:
            rows = conn.execute(
                f"select dataset, model, imputation, {metric} from runs "
                f"where config_name = ? and status = 'succeeded' "
                f"and task_type = ? and {metric} is not null "
                f"order by rowid desc",
                (config, task),
            ).fetchall()
            table, seen = {}, set()
            for dataset, model, level, score in rows:
                if level in EXCLUDE:
                    continue
                key = (dataset, model, level)
                if key in seen:       # keep the most recent row per cell
                    continue
                seen.add(key)
                table.setdefault((task, metric, model), {}).setdefault(dataset, {})[level] = score

            for (t, m, model), per_dataset in table.items():
                levels = sorted({l for v in per_dataset.values() for l in v})
                if BASELINE not in levels or len(levels) < 2:
                    continue
                complete = {d: v for d, v in per_dataset.items() if len(v) == len(levels)}
                if len(complete) < 2:
                    continue
                datasets = sorted(complete)
                scores = {l: [complete[d][l] for d in datasets] for l in levels}
                try:
                    res = compare_levels(scores, BASELINE, higher_is_better=higher)
                except StatisticsError:
                    continue
                reached = set()
                for c in res.comparisons:
                    out[(t, metric, model, c.level)] = c.rejected
                    reached.add(c.level)
                for level in levels:
                    if level != BASELINE and level not in reached:
                        out[(t, metric, model, level)] = False
    return out


tally = Counter()
detail = []

with sqlite3.connect(f"file:{DB}?mode=ro", uri=True) as conn:
    for tag in SWEEPS:
        per_seed = {}
        for label, pattern in SEEDS:
            per_seed[label] = contrasts(conn, pattern.format(tag=tag))
        keys = sorted(set().union(*(set(v) for v in per_seed.values())))
        for k in keys:
            votes = [label for label, v in per_seed.items() if v.get(k)]
            if not votes:
                continue      # never rejected under any seed
            tally[len(votes)] += 1
            detail.append((tag, k, len(votes), votes))

print("=" * 78)
print("IMPUTATION ARM UNDER THREE SEEDS (nine datasets)")
print("=" * 78)
print("  Seeds: 671, 1337, 20260702. A contrast is counted once per")
print("  sweep and metric, by how many seeds rejected it.\n")

total = sum(tally.values())
for n in (3, 2, 1):
    share = 100.0 * tally[n] / total if total else 0.0
    print(f"  rejected under {n} of 3 seeds   {tally[n]:3d}  ({share:.0f} per cent)")
print(f"  {'total contrasts ever rejected':31s} {total}")

if total:
    print(f"\n  unanimous rate: {tally[3]} of {total} "
          f"({100.0 * tally[3] / total:.0f} per cent)")
    print(f"  seen under one seed only: {tally[1]} of {total} "
          f"({100.0 * tally[1] / total:.0f} per cent)")

print("\n" + "=" * 78)
print("THE CONTRASTS THAT SURVIVED ALL THREE DRAWS")
print("=" * 78)
for tag, k, n, votes in sorted(detail):
    if n == 3:
        print(f"  {tag:7s} {'/'.join(k)}")

print("\n" + "=" * 78)
print("SEEN UNDER ONE SEED ONLY (would be a finding if that seed were the only one run)")
print("=" * 78)
for tag, k, n, votes in sorted(detail):
    if n == 1:
        print(f"  {tag:7s} {'/'.join(k):52s} only seed {votes[0]}")
