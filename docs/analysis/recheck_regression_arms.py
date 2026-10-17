"""Re-test the regression arms now that they hold 8 datasets rather than 7.

At n = 7 with k = 4 compared levels the smallest attainable
Holm-adjusted p is (2 / 2^7) * 4 = 0.0625, which exceeds alpha, so no
contrast in those cells could be rejected whatever the size of the real
effect. Adding forest_fires takes the arms to n = 8, where the floor is
0.03125. This script reports what changed.
"""
import pathlib
import sqlite3
import sys

sys.path.insert(0, r"C:/Users/Colile/Documents/School/NWU/S1/ITRI671 Project/pipeline-lab-engine/src")
from piplab.statistics.tests import StatisticsError, compare_levels

DB = r"C:/Users/Colile/Documents/School/NWU/S1/ITRI671 Project/pipeline-lab-engine/outputs/lab.db"

ARMS = [
    ("ofat_scaling_v2", "scaling", "none"),
    ("ofat_encoding_v2", "encoding", "onehot"),
    ("ofat_selection_v2", "selection", "none"),
    ("ofat_tuning_v3", "tuning", "none"),
]


def arm(conn, config, vary, baseline):
    rows = conn.execute(
        f"select dataset, model, {vary}, rmse_mean from runs "
        f"where config_name = ? and status = 'succeeded' "
        f"and task_type = 'regression' and rmse_mean is not null",
        (config,),
    ).fetchall()
    out = []
    for model in sorted({r[1] for r in rows}):
        table = {}
        for dataset, m, level, score in rows:
            if m == model:
                table.setdefault(dataset, {})[level] = score
        levels = sorted({l for v in table.values() for l in v})
        if baseline not in levels or len(levels) < 2:
            continue
        complete = {d: v for d, v in table.items() if len(v) == len(levels)}
        if len(complete) < 2:
            continue
        datasets = sorted(complete)
        scores = {l: [complete[d][l] for d in datasets] for l in levels}
        try:
            res = compare_levels(scores, baseline, higher_is_better=False)
        except StatisticsError:
            continue
        out.append((model, len(datasets), len(levels), res))
    return out


print("REGRESSION ARMS AFTER ADDING forest_fires")
print("=" * 72)
newly = []
with sqlite3.connect(f"file:{DB}?mode=ro", uri=True) as conn:
    for config, vary, baseline in ARMS:
        print(f"\n--- {config} ({vary}, baseline {baseline}) ---")
        for model, n, k, res in arm(conn, config, vary, baseline):
            floor = (2 / 2 ** n) * (k - 1)
            flag = "testable" if floor < 0.05 else f"FLOOR {floor:.4f} blocks rejection"
            print(f"  {model:18} n={n} k={k - 1}  Friedman p={res.friedman.p_value:.4f}  {flag}")
            for c in res.comparisons:
                mark = "REJECTED" if c.rejected else "not rejected"
                print(f"      {c.level:12} Holm={c.p_adjusted:.4f} "
                      f"median={c.effect.median_difference:+.4f} "
                      f"CI[{c.effect.ci_low:+.4f},{c.effect.ci_high:+.4f}] "
                      f"{c.effect.n_improved}/{c.effect.n_pairs}  {mark}")
                if c.rejected:
                    newly.append((config, model, c.level, c.p_adjusted))

print("\n" + "=" * 72)
print(f"rejected contrasts in the regression arms: {len(newly)}")
for n in newly:
    print("  ", n)
