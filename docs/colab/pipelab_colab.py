"""Orchestration for re-running the Pipeline Lab experiments on Google Colab.

The notebook (main_colab.ipynb) calls these functions in order:

  plan -> chunks -> run (resumable) -> merge -> compare -> analyse -> package

Why chunks. Two sweeps took longer than a Colab session lasts
(ofat_tuning_large 31 h, ofat_tuning_v3 21 h on the original machine),
and a sweep that restarts from zero every session never finishes. Each
sweep is therefore split into per-dataset chunks, and heavy sweeps into
per-dataset-per-model chunks. A chunk writes its own SQLite file on the
local disk and is copied to Google Drive only once it has finished, so
a dropped session loses at most the chunk in progress and a re-run of
the notebook skips everything already done.

Splitting does not change any result: datasets are loaded, injected and
evaluated independently, and every random state in the engine is seeded
from the configuration seed, not from run order. That claim was checked
before this module was used: chunked runs were compared cell by cell
with the original record (see README_COLAB.md).

This module deliberately imports nothing beyond the standard library and
PyYAML, so the notebook kernel never needs restarting after pip installs
the pinned numpy, pandas and scikit-learn. Everything that needs those
libraries runs in a subprocess.
"""
import datetime as dt
import json
import os
import pathlib
import re
import shutil
import sqlite3
import subprocess
import sys
import time

KEY_COLUMNS = ("config_name", "dataset", "model", "encoding", "imputation",
               "scaling", "selection", "tuning")
METRIC_COLUMNS = ("accuracy_mean", "f1_mean", "rmse_mean")


# ---------------------------------------------------------------- plan
def load_plan(path):
    """Read plan.json: the sweeps, their config files, groups and cost."""
    return json.loads(pathlib.Path(path).read_text(encoding="utf-8"))


def select(plan, profile):
    """Return the plan entries a profile runs, in their original order."""
    wanted = plan["profiles"][profile]
    return [e for e in plan["sweeps"] if e["config_name"] in wanted]


def profile_table(plan, speed_factor=None):
    """One row per profile: sweeps, local hours and, if known, projected hours here."""
    rows = []
    for name, members in plan["profiles"].items():
        hours = sum(e["local_hours"] for e in plan["sweeps"] if e["config_name"] in members)
        proj = f"{hours * speed_factor:7.1f}" if speed_factor else "      ?"
        rows.append(f"  {name:10s} {len(members):3d} sweeps  {hours:7.1f} h originally  {proj} h projected here")
    return "\n".join(rows)


# -------------------------------------------------------------- chunks
def chunks_for(entry, engine_dir):
    """Split one sweep into independently runnable chunks."""
    import yaml  # PyYAML is pure Python; importing it needs no restart

    out = []
    for fname in entry["files"]:
        cfg = yaml.safe_load((pathlib.Path(engine_dir) / "configs" / fname).read_text(encoding="utf-8"))
        stem = pathlib.Path(fname).stem
        for ds in cfg["datasets"]:
            model_groups = [[m] for m in cfg["models"]] if entry["heavy"] else [cfg["models"]]
            for models in model_groups:
                cid = f"{stem}__{ds}" + (f"__{models[0]}" if entry["heavy"] else "")
                out.append({"id": cid, "config_name": entry["config_name"], "file": fname,
                            "dataset": ds, "models": models})
    return out


def write_chunk_config(chunk, engine_dir, tmp_dir):
    """Write the parent config restricted to one dataset (and model)."""
    import yaml

    src = pathlib.Path(engine_dir) / "configs" / chunk["file"]
    cfg = yaml.safe_load(src.read_text(encoding="utf-8"))
    cfg["datasets"] = [chunk["dataset"]]
    cfg["models"] = chunk["models"]
    path = pathlib.Path(tmp_dir) / f"{chunk['id']}.yaml"
    path.write_text(yaml.safe_dump(cfg, sort_keys=False), encoding="utf-8")
    return path


# ----------------------------------------------------------------- run
def run_chunks(chunks, engine_dir, results_dir, work_dir, budget_hours=None, python=None, log=print):
    """Run every chunk not already done. Resumable; stops cleanly at the budget.

    A chunk is done when results_dir/chunks/<id>.done.json exists. Its
    database is written on the local disk and copied to results_dir only
    after the engine reports 'Record written', so Drive never holds a
    half-written database.
    """
    engine_dir, results_dir, work_dir = map(pathlib.Path, (engine_dir, results_dir, work_dir))
    store = results_dir / "chunks"
    store.mkdir(parents=True, exist_ok=True)
    work_dir.mkdir(parents=True, exist_ok=True)
    python = python or sys.executable
    pending = [c for c in chunks if not (store / f"{c['id']}.done.json").exists()]
    log(f"{len(chunks)} chunks in this profile, {len(chunks) - len(pending)} already done, "
        f"{len(pending)} to run")
    started = time.time()
    for i, chunk in enumerate(pending, 1):
        if budget_hours and (time.time() - started) / 3600 > budget_hours:
            log(f"time budget of {budget_hours} h reached; stopping cleanly. "
                "Re-run this cell (or the notebook) to continue.")
            return False
        cfg = write_chunk_config(chunk, engine_dir, work_dir)
        db = work_dir / f"{chunk['id']}.db"
        if db.exists():
            db.unlink()          # a partial file from a dropped session
        t0 = time.time()
        proc = subprocess.run(
            [python, "-u", "run_experiment.py", "--config", str(cfg), "--db", str(db)],
            cwd=engine_dir, capture_output=True, text=True,
        )
        minutes = (time.time() - t0) / 60
        out = proc.stdout + proc.stderr
        counts = {k: int(v) for k, v in re.findall(r"Runs (completed|failed|skipped): (\d+)", out)}
        if "Record written" not in out or not db.exists():
            (store / f"{chunk['id']}.error.txt").write_text(out[-6000:], encoding="utf-8")
            log(f"[{i}/{len(pending)}] {chunk['id']}: ENGINE DID NOT FINISH (see chunks/{chunk['id']}.error.txt)")
            continue
        shutil.copy2(db, store / f"{chunk['id']}.db")
        (store / f"{chunk['id']}.done.json").write_text(json.dumps(
            {"chunk": chunk, "exit_code": proc.returncode, "minutes": round(minutes, 3),
             "counts": counts, "finished": dt.datetime.now().isoformat(timespec="seconds")},
            indent=1), encoding="utf-8")
        db.unlink()
        elapsed = (time.time() - started) / 3600
        log(f"[{i}/{len(pending)}] {chunk['id']}: {counts.get('completed', 0)} ok, "
            f"{counts.get('skipped', 0)} skipped, {counts.get('failed', 0)} failed, "
            f"{minutes:.1f} min  (session {elapsed:.2f} h)")
    log("all chunks in this profile are done")
    return True


# --------------------------------------------------------------- merge
def merge(results_dir, out_db):
    """Combine every finished chunk database into one run record."""
    store = pathlib.Path(results_dir) / "chunks"
    out_db = pathlib.Path(out_db)
    if out_db.exists():
        out_db.unlink()
    dbs = sorted(p for p in store.glob("*.db"))
    if not dbs:
        raise RuntimeError("no finished chunks to merge yet")
    con = sqlite3.connect(out_db)
    schema = sqlite3.connect(dbs[0]).execute(
        "select sql from sqlite_master where type='table' and name='runs'").fetchone()[0]
    con.execute(schema)
    total = 0
    for p in dbs:
        con.execute("attach database ? as c", (str(p),))
        cols = [r[1] for r in con.execute("pragma c.table_info(runs)")]
        col_sql = ", ".join(f'"{c}"' for c in cols)
        cur = con.execute(f"insert into runs ({col_sql}) select {col_sql} from c.runs")
        total += cur.rowcount
        con.commit()
        con.execute("detach database c")
    con.commit()
    con.close()
    return {"chunks": len(dbs), "runs": total}


# ------------------------------------------------------------- compare
def _latest_rows(db, configs=None):
    """{key: row} keeping the most recent row per cell, as the analyses do."""
    con = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    con.row_factory = sqlite3.Row
    cols = {r[1] for r in con.execute("pragma table_info(runs)")}
    keys = [k for k in KEY_COLUMNS if k in cols]
    want = ", ".join(keys + ["status", "fold_scores_json"] + [m for m in METRIC_COLUMNS if m in cols])
    sql = f"select rowid, {want} from runs"
    rows = con.execute(sql).fetchall()
    con.close()
    latest = {}
    for r in rows:
        if configs and r["config_name"] not in configs:
            continue
        k = tuple(r[c] for c in keys)
        if k not in latest or r["rowid"] > latest[k]["rowid"]:
            latest[k] = r
    return keys, latest


def compare(original_db, new_db, out_csv=None, configs=None):
    """Cell-by-cell comparison of the re-run against the original record.

    A cell is one (sweep, dataset, model, technique) combination. Exact
    agreement means the per-fold scores are identical to the last digit.
    """
    keys, old = _latest_rows(original_db, configs)
    _, new = _latest_rows(new_db, configs)
    shared = sorted(set(old) & set(new))
    lines = [",".join(list(keys) + ["status_original", "status_rerun", "folds_identical"]
                      + [f"{m}_diff" for m in METRIC_COLUMNS])]
    s = {"cells_original": len(old), "cells_rerun": len(new), "cells_compared": len(shared),
         "status_agree": 0, "folds_identical": 0, "both_succeeded": 0,
         "max_abs_diff": {m: 0.0 for m in METRIC_COLUMNS}, "mismatches": []}
    for k in shared:
        a, b = old[k], new[k]
        same_status = a["status"] == b["status"]
        s["status_agree"] += same_status
        identical = False
        diffs = {}
        if a["status"] == b["status"] == "succeeded":
            s["both_succeeded"] += 1
            identical = (json.loads(a["fold_scores_json"] or "{}")
                         == json.loads(b["fold_scores_json"] or "{}"))
            for m in METRIC_COLUMNS:
                if m in a.keys() and a[m] is not None and b[m] is not None:
                    d = abs(a[m] - b[m])
                    diffs[m] = d
                    s["max_abs_diff"][m] = max(s["max_abs_diff"][m], d)
        s["folds_identical"] += identical
        if not same_status or (a["status"] == "succeeded" and not identical):
            s["mismatches"].append({"cell": dict(zip(keys, k)), "status": [a["status"], b["status"]],
                                    "diffs": diffs})
        lines.append(",".join([str(x) for x in k] + [a["status"], b["status"], str(identical)]
                              + [f"{diffs[m]:.3g}" if m in diffs else "" for m in METRIC_COLUMNS]))
    s["only_in_original"] = len(set(old) - set(new))
    s["only_in_rerun"] = len(set(new) - set(old))
    if out_csv:
        pathlib.Path(out_csv).write_text("\n".join(lines) + "\n", encoding="utf-8")
    return s


def describe_comparison(s):
    """Plain-language summary of a comparison result."""
    pct = lambda a, b: f"{100.0 * a / b:.1f}%" if b else "n/a"
    out = [
        f"cells compared                {s['cells_compared']:,}",
        f"status agrees                 {s['status_agree']:,}  ({pct(s['status_agree'], s['cells_compared'])})",
        f"both succeeded                {s['both_succeeded']:,}",
        f"per-fold scores identical     {s['folds_identical']:,}  ({pct(s['folds_identical'], s['both_succeeded'])} of those)",
        "largest absolute difference   " + ", ".join(f"{m} {v:.3g}" for m, v in s["max_abs_diff"].items()),
        f"cells only in original        {s['only_in_original']:,}   (sweeps not in this profile, or superseded rows)",
        f"cells only in re-run          {s['only_in_rerun']:,}",
        f"mismatching cells             {len(s['mismatches']):,}",
    ]
    return "\n".join(out)


# --------------------------------------------------------- speed factor
def speed_factor(results_dir, original_db):
    """How much slower or faster this machine is than the original, from finished chunks."""
    store = pathlib.Path(results_dir) / "chunks"
    con = sqlite3.connect(f"file:{original_db}?mode=ro", uri=True)
    here = there = 0.0
    for f in store.glob("*.done.json"):
        d = json.loads(f.read_text(encoding="utf-8"))
        c = d["chunk"]
        q = ("select sum(wall_seconds) from runs where config_name=? and dataset=? and model in (%s)"
             % ",".join("?" * len(c["models"])))
        orig = con.execute(q, [c["config_name"], c["dataset"], *c["models"]]).fetchone()[0]
        if orig:
            here += d["minutes"] * 60
            there += orig
    con.close()
    return round(here / there, 3) if there else None


# ------------------------------------------------------------- analyse
_IMP = [f"ofat_imputation_{t}" for t in ("mcar05", "mcar15", "mcar30", "mar05", "mar15", "mar30")]
_SEED_IMP = [f"seed_check_imputation_{t}" for t in ("mcar05", "mcar15", "mcar30", "mar05", "mar15", "mar30")]
_THIRD = [f"third_seed_imputation_{t}" for t in ("mcar05", "mcar15", "mcar30", "mar05", "mar15", "mar30")]
_SCALE_SEEDS = ["ofat_scaling_v2", "seed_check_scaling_1337", "seed_check_scaling_20260702"]
_V2 = ["ofat_scaling_v2", "ofat_encoding_v2", "ofat_selection_v2", "ofat_tuning_v3"]
_MAIN = _V2 + ["ofat_imputation_v2"] + _IMP + [
    "ofat_selection_k25", "ofat_selection_k75", "ofat_scaling_large", "ofat_scaling_large_svm",
    "ofat_encoding_large", "ofat_selection_large", "ofat_tuning_large", "holdout_large"]
_WIDE = [f"wide_imputation_{t}_s{s}" for t in ("mcar05", "mcar15", "mcar30", "mar05", "mar15", "mar30")
         for s in (671, 1337)]

# (label, script, sweeps it needs). An analysis whose sweeps are not all
# in the record is reported as not applicable rather than run: several
# scripts crash on a partial record, and two crashed scripts produce the
# same traceback, which a text comparison would wrongly call identical.
ANALYSES = [
    ("headline figures", "report_figures.py", _MAIN),
    ("scaling seed replication", "seed_sensitivity.py", _SCALE_SEEDS),
    ("seed reliability threshold", "seed_reliability_threshold.py", _SCALE_SEEDS),
    ("classification arms at 16 datasets", "recheck_classification_arms.py", _V2),
    ("regression arms", "recheck_regression_arms.py", _V2),
    ("imputation, two seeds", "imputation_seed_check.py", _IMP + _SEED_IMP),
    ("imputation, three seeds", "imputation_three_seeds.py", _IMP + _SEED_IMP + _THIRD),
    ("effect-size threshold, imputation", "imputation_effect_threshold.py", _IMP + _SEED_IMP),
    ("widened imputation arm", "wide_imputation_check.py", _WIDE),
    ("pre-registered held-out test", "heldout_test.py", ["heldout_scaling_confirmation"]),
    ("master analysis", "master_analysis.py", _MAIN),
    ("master analysis, drop_rows", "master_analysis2.py", _MAIN),
    ("figures 1 to 6", "make_figures.py", _MAIN),
    ("meta-analysis", "meta_analysis.py", _V2),
    ("figures 7 to 9", "meta_figures.py", _V2),
]
NOT_APPLICABLE = "not applicable"


def run_analyses(analysis_dir, db, engine_src, figs_dir, out_dir, text_dir, python=None, log=print):
    """Run every analysis whose sweeps are in the record; save each output."""
    python = python or sys.executable
    text_dir = pathlib.Path(text_dir)
    text_dir.mkdir(parents=True, exist_ok=True)
    env = dict(os.environ, PIPELAB_DB=str(db), PIPELAB_ENGINE_SRC=str(engine_src),
               PIPELAB_FIGS=str(figs_dir), PIPELAB_OUT=str(out_dir), MPLBACKEND="Agg")
    con = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    present = {r[0] for r in con.execute("select distinct config_name from runs")}
    con.close()
    status = {}
    for label, script, needs in ANALYSES:
        missing = [n for n in needs if n not in present]
        if missing:
            status[script] = NOT_APPLICABLE
            log(f"  {label:38s} {NOT_APPLICABLE} (needs {len(missing)} sweep(s) outside this profile)")
            continue
        proc = subprocess.run([python, script], cwd=analysis_dir, env=env,
                              capture_output=True, text=True)
        text = "\n".join(l for l in (proc.stdout + proc.stderr).splitlines()
                         if "findfont" not in l)
        (text_dir / f"{pathlib.Path(script).stem}.txt").write_text(text, encoding="utf-8")
        status[script] = "ok" if proc.returncode == 0 else f"error (exit {proc.returncode})"
        log(f"  {label:38s} {status[script]}")
    return status


def filtered_copy(src_db, dst_db, configs):
    """Copy of the original record holding only the sweeps a profile ran,
    so analyses of the original and the re-run see the same scope."""
    dst_db = pathlib.Path(dst_db)
    if dst_db.exists():
        dst_db.unlink()
    shutil.copy2(src_db, dst_db)
    con = sqlite3.connect(dst_db)
    marks = ",".join("?" * len(configs))
    con.execute(f"delete from runs where config_name not in ({marks})", list(configs))
    con.commit()
    con.execute("vacuum")
    con.close()


_PATH = re.compile(r"[A-Za-z]:[\\/]|/content/|/drive/|/tmp/|/home/|written")


def _result_lines(text):
    """The lines of an analysis output that carry results, not file paths.

    Only lines naming a file location are dropped. An earlier version
    dropped every line containing a slash, which also discarded the
    win-count lines such as '10/14' that are the results being compared.
    """
    return [l.rstrip() for l in text.splitlines() if not _PATH.search(l)]


def diff_analyses(dir_a, dir_b, status_a, status_b):
    """Compare each analysis's output on the original (a) and the re-run (b).

    Only analyses that ran successfully on both sides can be called
    identical. A crash on both sides is reported as an error, never as
    agreement.
    """
    out = {}
    for _label, script, _needs in ANALYSES:
        stem = pathlib.Path(script).stem
        sa, sb = status_a.get(script), status_b.get(script)
        if NOT_APPLICABLE in (sa, sb):
            out[stem] = "not applicable to this profile"
        elif sa != "ok" or sb != "ok":
            out[stem] = f"error (original: {sa}; re-run: {sb})"
        else:
            a = _result_lines((pathlib.Path(dir_a) / f"{stem}.txt").read_text(encoding="utf-8"))
            b = _result_lines((pathlib.Path(dir_b) / f"{stem}.txt").read_text(encoding="utf-8"))
            n = sum(x != y for x, y in zip(a, b)) + abs(len(a) - len(b))
            out[stem] = "identical" if n == 0 else f"differs ({n} lines)"
    return out
