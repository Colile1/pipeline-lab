"""Recompute every headline number the report quotes, from the record.

The report states run totals, dataset counts, cell counts, significant
global tests and surviving contrasts in fifteen places. The registry
grew twice during the study, so those figures have to be regenerated
together rather than patched individually, or they drift out of
agreement with each other and with the database.

This script is the single source for them. It prints a block that can
be checked against the report line by line.

The seed replication sweeps are excluded from the experimental totals
and reported separately, because they repeat existing work rather than
adding coverage.
"""
import sqlite3
import sys

sys.path.insert(0, r"C:/Users/Colile/Documents/School/NWU/S1/ITRI671 Project/pipeline-lab-engine/src")
from piplab.statistics.tests import StatisticsError, compare_levels

DB = r"C:/Users/Colile/Documents/School/NWU/S1/ITRI671 Project/pipeline-lab-engine/outputs/lab.db"

# The arms, matching master_analysis.py exactly so the two agree.
# Each is (config, varied column, baseline level, excluded levels).
#
# drop_rows is excluded from the six injected sweeps. This is the
# correction made after the bodyfat artefact: listwise deletion scores
# the model on whatever rows survive, so its result is not comparable
# with imputers that keep every row. Including it manufactures
# contrasts that were withdrawn from the study. The uninjected
# ofat_imputation_v2 sweep keeps it as the baseline, where the
# comparison is sound because no rows are deleted.
ARMS = [
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

METRICS = {
    "classification": [("accuracy_mean", True), ("f1_mean", True)],
    "regression": [("rmse_mean", False)],
}

# The record stores a model slot name, not the estimator class. On a
# regression target the engine substitutes the counterpart estimator
# (see MODEL_SUBSTITUTIONS in piplab.components.models), so a row
# labelled "logreg" against an RMSE was produced by LinearRegression.
# Spelled out here because the slot name invites a real misreading.
ESTIMATORS = {
    ("logreg", "regression"): "LinearRegression",
    ("svm", "regression"): "SVR",
    ("random_forest", "regression"): "RandomForestRegressor",
    ("gradient_boosting", "regression"): "GradientBoostingRegressor",
    ("logreg", "classification"): "LogisticRegression",
    ("svm", "classification"): "SVC",
    ("random_forest", "classification"): "RandomForestClassifier",
    ("gradient_boosting", "classification"): "GradientBoostingClassifier",
}


def cells(conn):
    """Yield one tested cell per (arm, task, metric, model)."""
    for config, vary, baseline, exclude in ARMS:
        for task, metrics in METRICS.items():
            for metric, higher in metrics:
                rows = conn.execute(
                    f"select dataset, model, {vary}, {metric} from runs "
                    f"where config_name = ? and status = 'succeeded' "
                    f"and task_type = ? and {metric} is not null",
                    (config, task),
                ).fetchall()
                if not rows:
                    continue
                for model in sorted({r[1] for r in rows}):
                    table = {}
                    for dataset, m, level, score in rows:
                        if m == model and level not in exclude:
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
                        res = compare_levels(scores, baseline, higher_is_better=higher)
                    except StatisticsError:
                        continue
                    yield config, task, metric, model, len(datasets), res


with sqlite3.connect(f"file:{DB}?mode=ro", uri=True) as conn:
    real = "config_name not like 'seed_check%'"

    runs = conn.execute(f"select count(*) from runs where {real}").fetchone()[0]
    datasets = conn.execute(f"select count(distinct dataset) from runs where {real}").fetchone()[0]
    sweeps = conn.execute(f"select count(distinct config_name) from runs where {real}").fetchone()[0]
    hours = conn.execute(
        f"select sum(wall_seconds) from runs where {real} and wall_seconds is not null"
    ).fetchone()[0] / 3600.0

    seed_runs = conn.execute(
        "select count(*) from runs where config_name like 'seed_check%'"
    ).fetchone()[0]
    seed_sweeps = conn.execute(
        "select count(distinct config_name) from runs where config_name like 'seed_check%'"
    ).fetchone()[0]
    seed_hours = conn.execute(
        "select sum(wall_seconds) from runs where config_name like 'seed_check%' "
        "and wall_seconds is not null"
    ).fetchone()[0] / 3600.0

    n_cells = n_sig = n_rejected = 0
    rejected = []
    for config, task, metric, model, n, res in cells(conn):
        n_cells += 1
        if res.friedman.p_value < 0.05:
            n_sig += 1
        for c in res.comparisons:
            if c.rejected:
                n_rejected += 1
                rejected.append((config, task, metric, model, c.level, c.p_adjusted))

    by_arm = {}
    for config, task, metric, model, level, p in rejected:
        key = config.split("_")[1]
        by_arm[key] = by_arm.get(key, 0) + 1

    print("=" * 70)
    print("HEADLINE FIGURES FOR THE REPORT")
    print("=" * 70)
    print(f"  experimental runs (excl. seed checks)  {runs:,}")
    print(f"  datasets in the registry               {datasets}")
    print(f"  sweeps                                 {sweeps}")
    print(f"  measured wall-clock hours              {hours:.1f}")
    print()
    print(f"  seed-replication runs                  {seed_runs:,}")
    print(f"  seed-replication sweeps                {seed_sweeps}")
    print(f"  seed-replication hours                 {seed_hours:.1f}")
    print()
    print(f"  TOTAL runs including replication       {runs + seed_runs:,}")
    print(f"  TOTAL hours including replication      {hours + seed_hours:.1f}")
    print()
    print(f"  statistical cells tested               {n_cells}")
    print(f"  cells with significant global test     {n_sig}")
    print(f"  contrasts surviving Holm               {n_rejected}")
    print()
    print("  surviving contrasts by arm:")
    for k in sorted(by_arm):
        print(f"    {k:14s} {by_arm[k]}")
    print()
    print("=" * 70)
    print("EVERY SURVIVING CONTRAST")
    print("=" * 70)
    print("  Model names are the record's slot names. On a regression")
    print("  target the engine substitutes the counterpart estimator, so")
    print("  'logreg' there is LinearRegression and 'svm' is SVR. The")
    print("  estimator actually fitted is printed below to avoid the")
    print("  misreading that a classifier produced an RMSE.")
    print()
    for r in sorted(rejected):
        shown = ESTIMATORS[(r[3], r[1])] if (r[3], r[1]) in ESTIMATORS else r[3]
        print(f"  {r[0]:26s} {r[1][:5]} {r[2]:14s} {shown:26s} {r[4]:10s} Holm={r[5]:.4f}")
