"""Does effect size predict whether an imputation finding reproduces?

The scaling replication established that a scaling difference of at
least one percentage point reproduces its direction across seeds in 93
per cent of cases, and one below that in 29 per cent (PROCESS-LOG 5c).
The imputation replication reproduces only 35 per cent of its rejected
contrasts, so the same question applies with more force here: is the
instability concentrated in the small effects?

Unit of analysis is one (sweep, task, metric, model, dataset, level)
comparison against the mean-imputation baseline. For each, the signed
difference from baseline is taken under each seed and the two are
asked whether they agree in direction.

Cells where both seeds return exactly zero are excluded. Those are
true no-ops, not disagreements, and counting them as agreement would
inflate the result. This matches the treatment in 5c.
"""
import sqlite3
from collections import defaultdict

from scipy import stats

DB = r"C:/Users/Colile/Documents/School/NWU/S1/ITRI671 Project/pipeline-lab-engine/outputs/lab.db"

SWEEPS = ["mcar05", "mcar15", "mcar30", "mar05", "mar15", "mar30"]
METRICS = {
    "classification": [("accuracy_mean", True)],
    "regression": [("rmse_mean", False)],
}
BASELINE = "mean"
EXCLUDE = ("drop_rows",)
THRESHOLD = 0.01  # one percentage point, as in 5c


def differences(conn, config):
    """Signed improvement over baseline, per comparison.

    Sign convention: positive always means the level beat the baseline,
    so RMSE differences are negated. Without that, regression and
    classification would disagree about what "the same direction" means.
    """
    out = {}
    for task, metrics in METRICS.items():
        for metric, higher in metrics:
            rows = conn.execute(
                f"select dataset, model, imputation, {metric} from runs "
                f"where config_name = ? and status = 'succeeded' "
                f"and task_type = ? and {metric} is not null",
                (config, task),
            ).fetchall()
            table = defaultdict(dict)
            for dataset, model, level, score in rows:
                if level not in EXCLUDE:
                    table[(task, metric, model, dataset)][level] = score
            for key, levels in table.items():
                if BASELINE not in levels:
                    continue
                base = levels[BASELINE]
                for level, score in levels.items():
                    if level == BASELINE:
                        continue
                    diff = (score - base) if higher else (base - score)
                    out[key + (level,)] = diff
    return out


pairs = []
with sqlite3.connect(f"file:{DB}?mode=ro", uri=True) as conn:
    for tag in SWEEPS:
        a = differences(conn, f"ofat_imputation_{tag}")
        b = differences(conn, f"seed_check_imputation_{tag}")
        for key in sorted(set(a) & set(b)):
            pairs.append((tag, key, a[key], b[key]))

# Relative size, so RMSE and accuracy are on one scale. The baseline
# score is needed for that, which differences() does not carry, so the
# comparison is made on the absolute mean of the two seeds instead.
small_agree = small_total = big_agree = big_total = 0
for tag, key, d1, d2 in pairs:
    size = (abs(d1) + abs(d2)) / 2.0
    if size == 0.0:
        continue  # true no-op under both seeds
    agree = (d1 > 0) == (d2 > 0)
    if size >= THRESHOLD:
        big_total += 1
        big_agree += agree
    else:
        small_total += 1
        small_agree += agree

print("=" * 70)
print("DOES EFFECT SIZE PREDICT REPRODUCIBILITY IN THE IMPUTATION ARM?")
print("=" * 70)
print(f"  comparisons measured under both seeds   {len(pairs)}")
print(f"  excluded as no-ops under both seeds     "
      f"{len(pairs) - small_total - big_total}")
print()
print(f"  effect below {THRESHOLD:.0%}: {small_agree} of {small_total} agree "
      f"({100.0 * small_agree / small_total:.0f} per cent)" if small_total else "")
print(f"  effect {THRESHOLD:.0%} or more: {big_agree} of {big_total} agree "
      f"({100.0 * big_agree / big_total:.0f} per cent)" if big_total else "")

if small_total and big_total:
    table = [[big_agree, big_total - big_agree],
             [small_agree, small_total - small_agree]]
    odds, p = stats.fisher_exact(table)
    print()
    print(f"  Fisher exact test: odds ratio {odds:.1f}, p = {p:.3g}")
    print(f"  contingency table (agree, disagree): {table}")
