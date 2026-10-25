"""Assemble the Colab bundle that main_colab.ipynb runs from.

Output: 671 Research June/Colab/PipelineLab_Colab/ (upload this folder to
Google Drive as MyDrive/PipelineLab_Colab) and a zip of the same folder.

Contents
  main_colab.ipynb          the notebook, run top to bottom
  pipelab_colab.py          orchestration used by the notebook
  plan.json                 every sweep, the config files that reproduce it,
                            its original cost, and the run profiles
  pipeline-lab-engine.zip   the engine at git tag iteration-v5-2026-10-19,
                            including outputs/lab.db, the original record
  analysis/                 the analysis scripts that produce Chapter 4
  sklearn_data.zip          the OpenML downloads, so the re-run uses the
                            same dataset files without depending on OpenML
  README_COLAB.md           how to run it

The plan is derived from the run record rather than written by hand: for
each recorded sweep it selects the config files whose cells reproduce the
recorded cells exactly, with no cell scored twice, and it refuses to
build if any sweep cannot be reproduced that way.
"""
import collections
import json
import pathlib
import shutil
import sqlite3
import subprocess
import zipfile

import yaml

ROOT = pathlib.Path(r"C:/Users/Colile/Documents/School/NWU/S1/ITRI671 Project")
ENGINE = ROOT / "pipeline-lab-engine"
LAB = ROOT / "671 Research June" / "pipeline-lab"
HERE = LAB / "docs" / "colab"
OUT = ROOT / "671 Research June" / "Colab" / "PipelineLab_Colab"
TAG = "iteration-v5-2026-10-19"
SKLEARN_DATA = pathlib.Path.home() / "scikit_learn_data"

# Sweeps the Chapter 4 analyses read (master_analysis.py ARMS).
MAIN = [
    "ofat_scaling_v2", "ofat_encoding_v2", "ofat_selection_v2", "ofat_tuning_v3",
    "ofat_imputation_v2", "ofat_imputation_mcar05", "ofat_imputation_mcar15",
    "ofat_imputation_mcar30", "ofat_imputation_mar05", "ofat_imputation_mar15",
    "ofat_imputation_mar30", "ofat_selection_k25", "ofat_selection_k75",
    "ofat_scaling_large", "ofat_scaling_large_svm", "ofat_encoding_large",
    "ofat_selection_large", "ofat_tuning_large", "holdout_large",
]
# An early sweep that stopped at 97 of its 112 cells and is superseded by
# ofat_scaling_v2. No analysis reads it, and re-running it would add 15
# adult-dataset cells the original never scored.
EXCLUDED = {"ofat_scaling_full": "stopped at 97 of 112 cells; superseded by ofat_scaling_v2"}
HEAVY_HOURS = 4.0


def cells(cfg):
    return {(d, t, m) for d in cfg["datasets"] for t in cfg["techniques"] for m in cfg["models"]}


def build_plan():
    files = collections.defaultdict(list)
    for f in sorted((ENGINE / "configs").glob("*.yaml")):
        cfg = yaml.safe_load(f.read_text(encoding="utf-8"))
        files[cfg["name"]].append((f, cfg))
    con = sqlite3.connect(f"file:{ENGINE / 'outputs' / 'lab.db'}?mode=ro", uri=True)
    rows = con.execute("""select config_name, count(*), sum(wall_seconds)/3600.0, min(started_at)
                          from runs group by 1 order by 4""").fetchall()
    sweeps = []
    for name, n, hours, first in rows:
        if name in EXCLUDED:
            continue
        vary = files[name][0][1]["vary"]
        recorded = set(con.execute(f"select dataset, {vary}, model from runs where config_name=?",
                                   (name,)).fetchall())
        chosen = [(f, c) for f, c in files[name] if f.stem == name]
        covered = set().union(*(cells(c) for _, c in chosen)) if chosen else set()
        for f, c in files[name]:
            if f.stem == name or f.stem.startswith(("rerun_", "repair_")):
                continue
            if cells(c) - covered:
                chosen.append((f, c))
                covered |= cells(c)
        assert covered == recorded, f"{name}: config files do not reproduce the recorded cells"
        if name in MAIN:
            group = "main"
        elif name.startswith(("seed_check", "third_seed")):
            group = "seed replication"
        elif name.startswith("wide_"):
            group = "widened registry"
        elif name.startswith("heldout"):
            group = "held-out test"
        else:
            group = "exploratory"
        sweeps.append({"config_name": name, "files": [f.name for f, _ in chosen], "group": group,
                       "cells": len(recorded), "local_hours": round(hours, 3),
                       "heavy": hours > HEAVY_HOURS, "first_run": first[:10]})
    names = [s["config_name"] for s in sweeps]
    profiles = {
        "smoke": ["ofat_scaling_offline", "heldout_scaling_confirmation"],
        "headline": ["ofat_scaling_v2"] + [n for n in names if n.startswith(
            ("ofat_imputation_m", "seed_check_", "third_seed_", "heldout_"))],
        "widened": [n for n in names if n.startswith("wide_")],
        "core": [n for n in names if n in MAIN],
        "full": names,
    }
    return {"tag": TAG, "excluded": EXCLUDED, "sweeps": sweeps, "profiles": profiles}


def main():
    if OUT.exists():
        shutil.rmtree(OUT)
    (OUT / "analysis").mkdir(parents=True)

    plan = build_plan()
    (OUT / "plan.json").write_text(json.dumps(plan, indent=1), encoding="utf-8")

    subprocess.run(["git", "-C", str(ENGINE), "archive", "--format=zip",
                    "--prefix=pipeline-lab-engine/", "-o", str(OUT / "pipeline-lab-engine.zip"), TAG],
                   check=True)

    # The internal grading report is a private self-assessment, not part of the
    # research, and is never packaged.
    for script in sorted((LAB / "docs" / "analysis").glob("*.py")):
        if script.name in ("grading_content.py", "build_grading.py"):
            continue
        shutil.copy2(script, OUT / "analysis" / script.name)

    with zipfile.ZipFile(OUT / "sklearn_data.zip", "w", zipfile.ZIP_DEFLATED) as z:
        for f in SKLEARN_DATA.rglob("*"):
            if f.is_file():
                z.write(f, "scikit_learn_data/" + f.relative_to(SKLEARN_DATA).as_posix())

    for name in ("pipelab_colab.py", "main_colab.ipynb", "README_COLAB.md"):
        if (HERE / name).exists():
            shutil.copy2(HERE / name, OUT / name)

    archive = OUT.parent / "PipelineLab_Colab.zip"
    if archive.exists():
        archive.unlink()
    with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as z:
        for f in OUT.rglob("*"):
            if f.is_file():
                z.write(f, "PipelineLab_Colab/" + f.relative_to(OUT).as_posix())

    print(f"bundle: {OUT}")
    for f in sorted(OUT.iterdir()):
        size = sum(p.stat().st_size for p in f.rglob("*")) if f.is_dir() else f.stat().st_size
        print(f"  {f.name:28s} {size / 1e6:7.2f} MB")
    print(f"zip:    {archive.name}  {archive.stat().st_size / 1e6:.1f} MB")
    print("\nprofiles:")
    for name, members in plan["profiles"].items():
        hrs = sum(s["local_hours"] for s in plan["sweeps"] if s["config_name"] in members)
        print(f"  {name:9s} {len(members):3d} sweeps  {hrs:6.1f} h on the original machine")
    print("heavy sweeps (split per dataset and model):",
          [s["config_name"] for s in plan["sweeps"] if s["heavy"]])


if __name__ == "__main__":
    main()
