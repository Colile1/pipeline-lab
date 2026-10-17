"""Compare the imputation arm under two random seeds.

The imputation arm carries most of the study's rejected contrasts and
all of them rest on seed 671. The scaling replication (PROCESS-LOG 5b)
showed that a contrast at this sample size can cross the significance
boundary when the fold assignment changes, so the arm carrying the
findings has to face the same test.

Seed 1337 changes both the fold assignment and the injected
missingness pattern, which asks whether a finding survives a different
draw rather than merely a different split of the same gaps.

The script runs whichever sweeps have finished, so it can be used
while the replication is still going. drop_rows is excluded from the
injected sweeps, matching master_analysis.py: listwise deletion scores
the model on a reduced sample, so its contrast is not comparable.
Sample sizes are printed per seed because the two seeds skip different
runs (PROCESS-LOG 5f).
"""
import sqlite3
import sys

sys.path.insert(0, r"C:/Users/Colile/Documents/School/NWU/S1/ITRI671 Project/pipeline-lab-engine/src")
from piplab.statistics.tests import StatisticsError, compare_levels

DB = r"C:/Users/Colile/Documents/School/NWU/S1/ITRI671 Project/pipeline-lab-engine/outputs/lab.db"

SWEEPS = ["mcar05", "mcar15", "mcar30", "mar05", "mar15", "mar30"]
METRICS = {
    "classification": [("accuracy_mean", True), ("f1_mean", True)],
    "regression": [("rmse_mean", False)],
}
BASELINE = "mean"
EXCLUDE = ("drop_rows",)


def contrasts(conn, config):
    """Return {(task, metric, model, level): (rejected, p, wins, pairs, n)}.

    Every candidate contrast gets an entry, including the ones where
    the Friedman gate was not passed. compare_levels returns no
    comparisons in that case, and an earlier version of this script
    treated the resulting absent key as "present in only one seed" and
    dropped the row from the reproduction rate. That silently excluded
    the most important class of disagreement, namely a cell that shows
    an effect under one seed and none under the other. Those rows are
    now recorded as not rejected, which is what they are.
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
            if not rows:
                continue
            for model in sorted({r[1] for r in rows}):
                table = {}
                for dataset, m, level, score in rows:
                    if m == model and level not in EXCLUDE:
                        table.setdefault(dataset, {})[level] = score
                levels = sorted({l for v in table.values() for l in v})
                if BASELINE not in levels or len(levels) < 2:
                    continue
                complete = {d: v for d, v in table.items() if len(v) == len(levels)}
                if len(complete) < 2:
                    continue
                datasets = sorted(complete)
                scores = {l: [complete[d][l] for d in datasets] for l in levels}
                try:
                    res = compare_levels(scores, BASELINE, higher_is_better=higher)
                except StatisticsError:
                    continue
                seen = set()
                for c in res.comparisons:
                    out[(task, metric, model, c.level)] = (
                        c.rejected, c.p_adjusted, c.effect.n_improved,
                        c.effect.n_pairs, len(datasets), res.friedman.p_value,
                    )
                    seen.add(c.level)
                # Levels with no comparison: the global test did not pass,
                # so the contrast was never reached. Recorded explicitly.
                for level in levels:
                    if level != BASELINE and level not in seen:
                        out[(task, metric, model, level)] = (
                            False, None, None, None, len(datasets),
                            res.friedman.p_value,
                        )
    return out


agree = disagree_lost = disagree_gained = 0
rows_out = []

with sqlite3.connect(f"file:{DB}?mode=ro", uri=True) as conn:
    done = {
        r[0].replace("seed_check_imputation_", "")
        for r in conn.execute(
            "select distinct config_name from runs "
            "where config_name like 'seed_check_imputation%'"
        )
    }
    # Only compare a sweep whose replication has all its runs.
    complete_sweeps = []
    for tag in SWEEPS:
        if tag not in done:
            continue
        a = conn.execute(
            "select count(*) from runs where config_name = ?",
            (f"ofat_imputation_{tag}",),
        ).fetchone()[0]
        b = conn.execute(
            "select count(*) from runs where config_name = ?",
            (f"seed_check_imputation_{tag}",),
        ).fetchone()[0]
        if b >= a:
            complete_sweeps.append(tag)
        else:
            print(f"  (skipping {tag}: replication at {b} of {a} runs)")

    print(f"\ncomparing {len(complete_sweeps)} complete sweeps: "
          f"{', '.join(complete_sweeps) or 'none yet'}\n")

    for tag in complete_sweeps:
        orig = contrasts(conn, f"ofat_imputation_{tag}")
        repl = contrasts(conn, f"seed_check_imputation_{tag}")
        keys = sorted(set(orig) | set(repl))
        print("=" * 78)
        print(f"{tag}")
        print("=" * 78)
        def describe(v):
            """One seed's verdict on a contrast, in a fixed-width field."""
            if v is None:
                return "absent".ljust(34)
            rejected, p, wins, pairs, n, fried = v
            if p is None:
                return f"no global test (Friedman {fried:.4f})".ljust(34)
            return f"p={p:.4f} {wins}/{pairs} (n={n})".ljust(34)

        for k in keys:
            o = orig.get(k)
            r = repl.get(k)
            o_rej = bool(o and o[0])
            r_rej = bool(r and r[0])
            if not o_rej and not r_rej:
                continue  # not rejected under either seed, nothing to report
            mark = {
                (True, True): "HOLDS",
                (True, False): "LOST",
                (False, True): "GAINED",
            }[(o_rej, r_rej)]
            if mark == "HOLDS":
                agree += 1
            elif mark == "LOST":
                disagree_lost += 1
            else:
                disagree_gained += 1
            print(f"  {'/'.join(k):52s} {mark:7s} "
                  f"671: {describe(o)} 1337: {describe(r)}")
            rows_out.append((tag, k, mark, o, r))

print("\n" + "=" * 78)
print("SUMMARY")
print("=" * 78)
print(f"  rejected under seed 671 and reproduced under 1337   {agree}")
print(f"  rejected under 671 but NOT under 1337 (lost)        {disagree_lost}")
print(f"  rejected under 1337 but NOT under 671 (gained)      {disagree_gained}")
if agree + disagree_lost:
    rate = 100.0 * agree / (agree + disagree_lost)
    print(f"\n  reproduction rate of the original findings: "
          f"{agree} of {agree + disagree_lost} ({rate:.0f} per cent)")

# Agreement on the global test is the broader question. A contrast can
# only be reached if the Friedman gate passes, so two seeds disagreeing
# about the gate is a disagreement about whether the cell shows any
# effect at all, which the contrast-level count above cannot show.
print()
print("  Agreement on the global test (Friedman at alpha = 0.05):")
gate_same = gate_diff = 0
flips = []
with sqlite3.connect(f"file:{DB}?mode=ro", uri=True) as conn:
    for tag in complete_sweeps:
        orig = contrasts(conn, f"ofat_imputation_{tag}")
        repl = contrasts(conn, f"seed_check_imputation_{tag}")
        cells_seen = set()
        for k in sorted(set(orig) & set(repl)):
            cell = (tag,) + k[:3]
            if cell in cells_seen:
                continue
            cells_seen.add(cell)
            a = orig[k][5] < 0.05
            b = repl[k][5] < 0.05
            if a == b:
                gate_same += 1
            else:
                gate_diff += 1
                flips.append((cell, orig[k][5], repl[k][5]))
tot_cells = gate_same + gate_diff
if tot_cells:
    print(f"    same verdict  {gate_same} of {tot_cells} "
          f"({100.0 * gate_same / tot_cells:.0f} per cent)")
    print(f"    disagreed     {gate_diff}")
for cell, a, b in flips:
    print(f"      {'/'.join(cell):50s} 671 p={a:.4f}  1337 p={b:.4f}")
