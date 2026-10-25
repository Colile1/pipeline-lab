"""Run the pre-registered held-out test, exactly as registered.

The prediction, the datasets, the procedure and the decision rule were
fixed in docs/PREREGISTRATION-HELDOUT.md and committed to git before
any of these datasets had been scored. This script implements that
document and nothing else: one-sided Wilcoxon, alpha 0.05, two levels,
no correction, with random forest as the control.

Nothing here is tunable. If the result disappoints, the result is what
gets reported.
"""
import os
import sqlite3

import numpy as np
from scipy import stats

DB = os.environ.get("PIPELAB_DB", r"C:/Users/Colile/Documents/School/NWU/S1/ITRI671 Project/pipeline-lab-engine/outputs/lab.db")
CONFIG = "heldout_scaling_confirmation"
ALPHA = 0.05


def arm(conn, model):
    rows = conn.execute(
        "select dataset, scaling, accuracy_mean from runs "
        "where config_name = ? and model = ? and status = 'succeeded' "
        "and accuracy_mean is not null order by dataset",
        (CONFIG, model),
    ).fetchall()
    table = {}
    for dataset, level, score in rows:
        table.setdefault(dataset, {})[level] = score
    complete = {d: v for d, v in table.items() if "none" in v and "standard" in v}
    return complete


def report(model, label):
    with sqlite3.connect(f"file:{DB}?mode=ro", uri=True) as conn:
        table = arm(conn, model)
    datasets = sorted(table)
    base = np.array([table[d]["none"] for d in datasets])
    std = np.array([table[d]["standard"] for d in datasets])
    diff = std - base

    print(f"\n{'=' * 70}")
    print(f"{label}  ({model}), n = {len(datasets)}")
    print("=" * 70)
    for d, b, s in zip(datasets, base, std):
        mark = "+" if s > b else ("-" if s < b else "=")
        print(f"  {d:18s} none={b:.4f}  standard={s:.4f}  {s - b:+.4f}  {mark}")

    wins = int(np.sum(diff > 0))
    losses = int(np.sum(diff < 0))
    ties = int(np.sum(diff == 0))
    print(f"\n  standard wins on {wins} of {len(datasets)} "
          f"(losses {losses}, exact ties {ties})")

    if np.all(diff == 0):
        print("  every difference is exactly zero; no test is possible")
        return None, wins, len(datasets)

    res = stats.wilcoxon(std, base, alternative="greater")
    print(f"  Wilcoxon one-sided p = {res.pvalue:.4f}  (alpha {ALPHA})")
    print(f"  median difference    = {np.median(diff):+.4f}")

    # Bootstrap interval on the median difference, as used elsewhere.
    rng = np.random.default_rng(671)
    boots = [np.median(rng.choice(diff, len(diff), replace=True)) for _ in range(10000)]
    lo, hi = np.percentile(boots, [2.5, 97.5])
    print(f"  95% bootstrap CI     = [{lo:+.4f}, {hi:+.4f}]")
    return res.pvalue, wins, len(datasets)


print("PRE-REGISTERED HELD-OUT CONFIRMATION")
print("Registered 2026-10-18 06:54 (git 1f82653), before these datasets were scored.")

p_svm, wins_svm, n = report("svm", "PREDICTION: scaling helps the SVM")
p_rf, wins_rf, _ = report("random_forest", "CONTROL: scaling does not help a tree")

print(f"\n{'=' * 70}")
print("VERDICT AGAINST THE REGISTERED CRITERIA")
print("=" * 70)
primary = p_svm is not None and p_svm < ALPHA
secondary = wins_svm >= 4
falsified = wins_svm <= 2
print(f"  primary   (Wilcoxon p < {ALPHA}):        "
      f"{'MET' if primary else 'NOT MET'}")
print(f"  secondary (standard wins >= 4 of 5):  "
      f"{'MET' if secondary else 'NOT MET'}  [{wins_svm} of {n}]")
print(f"  falsified (standard wins <= 2 of 5):  "
      f"{'YES' if falsified else 'no'}")
control_clean = p_rf is None or p_rf >= ALPHA
print(f"  control   (no tree effect):           "
      f"{'clean' if control_clean else 'CONTROL ALSO SIGNIFICANT, suspect'}")
print()
if primary and secondary and control_clean:
    print("  CONFIRMED on data that played no part in forming the hypothesis.")
elif falsified:
    print("  FALSIFIED. The scaling result does not generalise to these datasets.")
else:
    print("  PARTIAL. The direction holds but the registered bar was not cleared;")
    print("  reported as a failure to confirm at this sample size.")
