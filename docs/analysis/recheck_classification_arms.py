"""Re-test the classification arms now that they hold 16 datasets, not 11.

The classification side was never blocked by the Wilcoxon discreteness
floor: at n = 11 with k = 3 the floor is 0.0029, well under alpha. It
was limited by stability. The seed replication (PROCESS-LOG 5b) showed
that at eleven datasets two sign changes move a contrast across the
significance boundary while the underlying effect barely moves, so five
datasets were added to make the win counts less fragile.

This script reports what changed, and reports exact ties alongside each
contrast. Wilcoxon discards tied pairs, so a contrast's effective
sample size can be well below the number of datasets, which is the
mechanism behind the logreg result in PROCESS-LOG 5e.
"""
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

# The five datasets registered on 2026-10-17 (PROCESS-LOG 5d).
ADDED = {"banknote", "blood_transfusion", "climate_sim", "phoneme", "steel_plates"}

METRIC = "accuracy_mean"


def arm(conn, config, vary, baseline, restrict=None):
    """Run one arm. restrict limits the datasets, for the n=11 comparison."""
    rows = conn.execute(
        f"select dataset, model, {vary}, {METRIC} from runs "
        f"where config_name = ? and status = 'succeeded' "
        f"and task_type = 'classification' and {METRIC} is not null",
        (config,),
    ).fetchall()
    out = []
    for model in sorted({r[1] for r in rows}):
        table = {}
        for dataset, m, level, score in rows:
            if m != model:
                continue
            if restrict is not None and dataset not in restrict:
                continue
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
            res = compare_levels(scores, baseline, higher_is_better=True)
        except StatisticsError:
            continue
        # Exact ties per contrast: Wilcoxon drops these, so they cost
        # effective sample size without reducing the Holm multiplier.
        ties = {
            l: sum(1 for d in datasets if complete[d][l] == complete[d][baseline])
            for l in levels
            if l != baseline
        }
        out.append((model, len(datasets), len(levels), res, ties))
    return out


def report(conn, restrict, heading):
    print("\n" + "=" * 74)
    print(heading)
    print("=" * 74)
    rejected = []
    for config, vary, baseline in ARMS:
        print(f"\n--- {config} ({vary}, baseline {baseline}) ---")
        got = arm(conn, config, vary, baseline, restrict)
        if not got:
            print("  no testable cells")
        for model, n, k, res, ties in got:
            floor = (2 / 2 ** n) * (k - 1)
            flag = "testable" if floor < 0.05 else f"FLOOR {floor:.4f} blocks rejection"
            print(f"  {model:18} n={n} k={k - 1}  "
                  f"Friedman p={res.friedman.p_value:.4f}  {flag}")
            for c in res.comparisons:
                mark = "REJECTED" if c.rejected else "not rejected"
                t = ties.get(c.level, 0)
                eff = n - t
                print(f"      {c.level:12} Holm={c.p_adjusted:.4f} "
                      f"median={c.effect.median_difference:+.4f} "
                      f"CI[{c.effect.ci_low:+.4f},{c.effect.ci_high:+.4f}] "
                      f"{c.effect.n_improved}/{c.effect.n_pairs} "
                      f"ties={t} eff_n={eff}  {mark}")
                if c.rejected:
                    rejected.append((config, model, c.level, c.p_adjusted))
    print(f"\nrejected contrasts: {len(rejected)}")
    for r in rejected:
        print("  ", r)
    return {(c, m, l) for c, m, l, _ in rejected}


with sqlite3.connect(f"file:{DB}?mode=ro", uri=True) as conn:
    everything = {
        r[0] for r in conn.execute(
            "select distinct dataset from runs where task_type = 'classification'"
        )
    }
    old = everything - ADDED

    before = report(conn, old, f"BEFORE: the original {len(old)} classification datasets")
    after = report(conn, None, f"AFTER: all {len(everything)} classification datasets")

    print("\n" + "=" * 74)
    print("WHAT THE FIVE DATASETS CHANGED")
    print("=" * 74)
    gained = sorted(after - before)
    lost = sorted(before - after)
    print(f"gained {len(gained)} contrasts:")
    for g in gained:
        print("   +", g)
    print(f"lost {len(lost)} contrasts:")
    for l in lost:
        print("   -", l)
