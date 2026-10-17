"""Compare the scaling arm across three independent random seeds.

Every run recorded before 2026-10-17 used seed 671, so the headline
scaling result rested on one fold assignment. This repeats the analysis
for seeds 1337 and 20260702 and reports whether the finding holds.

The three seeds are treated as independent estimates of the same
quantity and are never pooled: pooling would triple the apparent sample
while the datasets stay the same, which would misrepresent the design.
"""
import pathlib
import sqlite3
import sys

sys.path.insert(0, r"C:/Users/Colile/Documents/School/NWU/S1/ITRI671 Project/pipeline-lab-engine/src")
from piplab.statistics.tests import StatisticsError, compare_levels

DB = r"C:/Users/Colile/Documents/School/NWU/S1/ITRI671 Project/pipeline-lab-engine/outputs/lab.db"

SWEEPS = [
    ("ofat_scaling_v2", 671),
    ("seed_check_scaling_1337", 1337),
    ("seed_check_scaling_20260702", 20260702),
]
MODELS = ["logreg", "svm", "random_forest", "gradient_boosting"]


def analyse(conn, config, task, metric):
    rows = conn.execute(
        f"select dataset, model, scaling, {metric} from runs "
        f"where config_name = ? and status = 'succeeded' "
        f"and task_type = ? and {metric} is not null",
        (config, task),
    ).fetchall()
    out = {}
    for model in MODELS:
        table = {}
        for dataset, m, level, score in rows:
            if m == model:
                table.setdefault(dataset, {})[level] = score
        levels = sorted({l for v in table.values() for l in v})
        if "none" not in levels or len(levels) < 2:
            continue
        complete = {d: v for d, v in table.items() if len(v) == len(levels)}
        if len(complete) < 2:
            continue
        ds = sorted(complete)
        scores = {l: [complete[d][l] for d in ds] for l in levels}
        try:
            res = compare_levels(scores, "none", higher_is_better=(metric != "rmse_mean"))
        except StatisticsError:
            continue
        out[model] = (len(ds), res)
    return out


with sqlite3.connect(f"file:{DB}?mode=ro", uri=True) as conn:
    present = {c for (c,) in conn.execute("select distinct config_name from runs")}
    available = [(c, s) for c, s in SWEEPS if c in present]
    print(f"seeds available in the record: {[s for _, s in available]}")
    if len(available) < 2:
        print("\nThe replication sweeps have not finished yet; rerun when they have.")
        sys.exit(0)

    print()
    print("=" * 78)
    print("SCALING ARM ACROSS SEEDS, classification accuracy")
    print("=" * 78)
    for model in MODELS:
        print(f"\n{model}")
        for config, seed in available:
            got = analyse(conn, config, "classification", "accuracy_mean")
            if model not in got:
                print(f"   seed {seed:<9} no complete cell")
                continue
            n, res = got[model]
            line = (f"   seed {seed:<9} n={n:2}  Friedman p={res.friedman.p_value:.4f}")
            if res.comparisons:
                best = [c for c in res.comparisons if c.rejected]
                if best:
                    for c in best:
                        line += (f"\n        REJECTED {c.level} Holm={c.p_adjusted:.4f} "
                                 f"{c.effect.n_improved}/{c.effect.n_pairs}")
                else:
                    line += "   global test significant, no contrast survived"
            print(line)

    print()
    print("=" * 78)
    print("VERDICT")
    print("=" * 78)
    headline = {}
    for config, seed in available:
        got = analyse(conn, config, "classification", "accuracy_mean")
        if "logreg" in got:
            _, res = got["logreg"]
            std = next((c for c in res.comparisons if c.level == "standard"), None)
            headline[seed] = (res.friedman.p_value,
                              std.p_adjusted if std else None,
                              std.rejected if std else False,
                              f"{std.effect.n_improved}/{std.effect.n_pairs}" if std else "-")
    for seed, (fp, holm, rej, win) in headline.items():
        state = "holds" if rej else "does not reach significance"
        h = f"{holm:.4f}" if holm is not None else "n/a"
        print(f"  seed {seed:<9} Friedman {fp:.4f}  standard-vs-none Holm {h:>7}  "
              f"{win:>6}  {state}")
    n_hold = sum(1 for v in headline.values() if v[2])
    print(f"\n  standard scaling beats none for logistic regression in "
          f"{n_hold} of {len(headline)} seeds")
