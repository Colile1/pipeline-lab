"""Compare the widened imputation arm across two seeds.

The nine-dataset arm reproduced only 8 of 23 contrasts under a second
seed (PROCESS-LOG 5l), and the diagnosis was the sample size. This
arm adds seven datasets, taking classification from 9 to 14 and
regression from 9 to 11, and runs both seeds so the comparison is
like for like.

The question this answers: does a larger sample fix the instability,
or is the instability deeper than sample size? Either answer is worth
reporting, and they say different things about the study's
conclusions.

DEDUPLICATION. One sweep was briefly run twice by mistake
(PROCESS-LOG 5o), so a few cells have two rows under different
batch_ids. The record is append-only and nothing was deleted, so this
script keeps the most recent row per (dataset, model, level) and says
how many it dropped. The duplicated rows were verified to be scored
identically, so the choice of which to keep does not affect any
result; the deduplication exists to stop double counting.
"""
import os
import sqlite3
import sys

sys.path.insert(0, os.environ.get("PIPELAB_ENGINE_SRC", r"C:/Users/Colile/Documents/School/NWU/S1/ITRI671 Project/pipeline-lab-engine/src"))
from piplab.statistics.tests import StatisticsError, compare_levels

DB = os.environ.get("PIPELAB_DB", r"C:/Users/Colile/Documents/School/NWU/S1/ITRI671 Project/pipeline-lab-engine/outputs/lab.db")

SWEEPS = ["mcar05", "mcar15", "mcar30", "mar05", "mar15", "mar30"]
METRICS = {
    "classification": [("accuracy_mean", True), ("f1_mean", True)],
    "regression": [("rmse_mean", False)],
}
BASELINE = "mean"
EXCLUDE = ("drop_rows",)

dropped_total = 0


def contrasts(conn, config):
    """Return {(task, metric, model, level): (rejected, p, wins, pairs, n, friedman)}.

    Cells where the global test did not pass are recorded as not
    rejected rather than omitted. Omitting them was the bug in the
    first version of imputation_seed_check.py, and it hid the most
    important class of disagreement.
    """
    global dropped_total
    out = {}
    for task, metrics in METRICS.items():
        for metric, higher in metrics:
            # rowid descending keeps the most recently written row when
            # a cell was recorded twice.
            rows = conn.execute(
                f"select dataset, model, imputation, {metric} from runs "
                f"where config_name = ? and status = 'succeeded' "
                f"and task_type = ? and {metric} is not null "
                f"order by rowid desc",
                (config, task),
            ).fetchall()
            table = {}
            seen = set()
            for dataset, model, level, score in rows:
                if level in EXCLUDE:
                    continue
                key = (dataset, model, level)
                if key in seen:
                    dropped_total += 1
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
                    out[(t, metric, model, c.level)] = (
                        c.rejected, c.p_adjusted, c.effect.n_improved,
                        c.effect.n_pairs, len(datasets), res.friedman.p_value,
                    )
                    reached.add(c.level)
                for level in levels:
                    if level != BASELINE and level not in reached:
                        out[(t, metric, model, level)] = (
                            False, None, None, None, len(datasets),
                            res.friedman.p_value,
                        )
    return out


def describe(v):
    if v is None:
        return "absent".ljust(34)
    rejected, p, wins, pairs, n, fried = v
    if p is None:
        return f"no global test (Friedman {fried:.4f})".ljust(34)
    return f"p={p:.4f} {wins}/{pairs} (n={n})".ljust(34)


agree = lost = gained = 0
gate_same = gate_diff = 0

with sqlite3.connect(f"file:{DB}?mode=ro", uri=True) as conn:
    ready = []
    for tag in SWEEPS:
        a = conn.execute("select count(*) from runs where config_name = ?",
                         (f"wide_imputation_{tag}_s671",)).fetchone()[0]
        b = conn.execute("select count(*) from runs where config_name = ?",
                         (f"wide_imputation_{tag}_s1337",)).fetchone()[0]
        if a >= 400 and b >= 400:
            ready.append(tag)
        else:
            print(f"  (skipping {tag}: s671 at {a}/400, s1337 at {b}/400)")

    print(f"\ncomparing {len(ready)} complete sweep pairs: {', '.join(ready) or 'none yet'}\n")

    for tag in ready:
        orig = contrasts(conn, f"wide_imputation_{tag}_s671")
        repl = contrasts(conn, f"wide_imputation_{tag}_s1337")
        print("=" * 78)
        print(tag)
        print("=" * 78)
        for k in sorted(set(orig) | set(repl)):
            o, r = orig.get(k), repl.get(k)
            o_rej, r_rej = bool(o and o[0]), bool(r and r[0])
            if not o_rej and not r_rej:
                continue
            mark = {(True, True): "HOLDS", (True, False): "LOST",
                    (False, True): "GAINED"}[(o_rej, r_rej)]
            if mark == "HOLDS":
                agree += 1
            elif mark == "LOST":
                lost += 1
            else:
                gained += 1
            print(f"  {'/'.join(k):52s} {mark:7s} 671: {describe(o)} 1337: {describe(r)}")

        cells = set()
        for k in sorted(set(orig) & set(repl)):
            cell = k[:3]
            if cell in cells:
                continue
            cells.add(cell)
            if (orig[k][5] < 0.05) == (repl[k][5] < 0.05):
                gate_same += 1
            else:
                gate_diff += 1

print("\n" + "=" * 78)
print("SUMMARY: WIDENED ARM (14 classification / 11 regression datasets)")
print("=" * 78)
print(f"  duplicate rows skipped          {dropped_total}")
print(f"  rejected under 671, reproduced  {agree}")
print(f"  rejected under 671, lost        {lost}")
print(f"  rejected under 1337 only        {gained}")
if agree + lost:
    print(f"\n  reproduction rate: {agree} of {agree + lost} "
          f"({100.0 * agree / (agree + lost):.0f} per cent)")
    print(f"  the nine-dataset arm gave:  8 of 23 (35 per cent)")
if gate_same + gate_diff:
    tot = gate_same + gate_diff
    print(f"\n  global-test agreement: {gate_same} of {tot} "
          f"({100.0 * gate_same / tot:.0f} per cent)")
    print(f"  the nine-dataset arm gave: 50 of 72 (69 per cent)")
