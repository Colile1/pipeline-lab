"""Generate main_colab.ipynb.

The notebook is written from this script so that its cells can be
regenerated and tested, rather than hand-edited as JSON. Every code cell
also runs outside Colab (set PIPELAB_LOCAL=1 and PIPELAB_BUNDLE), which
is how the notebook was tested before it was handed over.
"""
import json
import pathlib

HERE = pathlib.Path(__file__).resolve().parent

CELLS = []


def md(text):
    CELLS.append({"cell_type": "markdown", "metadata": {}, "source": text.strip("\n")})


def code(text):
    CELLS.append({"cell_type": "code", "metadata": {}, "execution_count": None,
                  "outputs": [], "source": text.strip("\n")})


md("""
# Pipeline Lab: full re-run of the experiments on Google Colab

This notebook re-executes the Pipeline Lab experiments in a fresh environment and checks the
new results against the original run record, cell by cell. It then re-runs every analysis
behind Chapter 4, draws the figures, and packages the results.

**How to run it**

1. Upload the `PipelineLab_Colab` folder to Google Drive, so that it sits at
   `MyDrive/PipelineLab_Colab` (uploading `PipelineLab_Colab.zip` there instead also works).
2. Choose a profile in the first code cell.
3. *Runtime > Run all*, then approve the Google Drive prompt.

**If the session drops**, reconnect and *Run all* again. Every finished piece of work is
saved to Drive the moment it completes and is skipped on the next run, so nothing is lost
except the chunk that was in progress.

| profile | what it re-runs | time on the original machine |
|---|---|---|
| `smoke` | two small sweeps, to check the set-up | 0.2 h |
| `headline` | the scaling arm, the imputation arm under three seeds, the held-out test | 13.1 h |
| `widened` | the widened imputation arm under two seeds | 24.5 h |
| `core` | the main experimental programme (the 19 sweeps Chapter 4 analyses) | 79.1 h |
| `full` | everything in the run record | 119.2 h |

Colab hardware differs from the original machine, so the notebook measures the speed
difference on the first chunks and projects the time for each profile. Start with `smoke`.
""")

code('''
# ---- settings: the only cell you need to edit -------------------------
PROFILE = "smoke"        # smoke | headline | widened | core | full
BUDGET_HOURS = 11.0      # stop cleanly before Colab ends the session
RUN_ENGINE_TESTS = True  # run the engine's 350 tests before experimenting
DRIVE_FOLDER = "/content/drive/MyDrive/PipelineLab_Colab"
''')

md("## 1. Connect Google Drive and find the bundle")

code('''
import os, pathlib, sys, zipfile, json, subprocess, shutil, time, datetime

IN_COLAB = "google.colab" in sys.modules and not os.environ.get("PIPELAB_LOCAL")
if IN_COLAB:
    from google.colab import drive
    drive.mount("/content/drive")
    WORK = pathlib.Path("/content/work")
    BUNDLE = pathlib.Path(DRIVE_FOLDER)
else:                                   # local test mode
    BUNDLE = pathlib.Path(os.environ["PIPELAB_BUNDLE"])
    WORK = pathlib.Path(os.environ.get("PIPELAB_WORK", BUNDLE.parent / "work"))
    PROFILE = os.environ.get("PIPELAB_PROFILE", PROFILE)

if not BUNDLE.exists() and BUNDLE.with_suffix(".zip").exists():
    zipfile.ZipFile(BUNDLE.with_suffix(".zip")).extractall(BUNDLE.parent)
assert (BUNDLE / "plan.json").exists(), f"bundle not found at {BUNDLE}; see the first markdown cell"

RESULTS = BUNDLE / f"results_{PROFILE}"
RESULTS.mkdir(parents=True, exist_ok=True)
WORK.mkdir(parents=True, exist_ok=True)
sys.path.insert(0, str(BUNDLE))
import pipelab_colab as pc
print("bundle :", BUNDLE)
print("results:", RESULTS)
print("profile:", PROFILE)
''')

md("## 2. Unpack the engine and the datasets onto the local disk")

code('''
ENGINE = WORK / "pipeline-lab-engine"
if not (ENGINE / "run_experiment.py").exists():
    zipfile.ZipFile(BUNDLE / "pipeline-lab-engine.zip").extractall(WORK)
if not (WORK / "scikit_learn_data").exists():
    zipfile.ZipFile(BUNDLE / "sklearn_data.zip").extractall(WORK)
# The engine fetches datasets by fixed OpenML id; pointing scikit-learn at
# the bundled downloads means the re-run reads the same files as the
# original, without depending on OpenML being reachable.
os.environ["SCIKIT_LEARN_DATA"] = str(WORK / "scikit_learn_data")
ORIGINAL_DB = ENGINE / "outputs" / "lab.db"
print("engine      :", ENGINE)
print("original run record:", ORIGINAL_DB, f"({ORIGINAL_DB.stat().st_size / 1e6:.1f} MB)")
''')

md("""
## 3. Install the pinned library versions

The original runs used exact versions (scikit-learn 1.9.0, numpy 2.4.6, pandas 3.0.6,
scipy 1.17.1). Identical scores depend on identical versions, so they are installed as pinned
and then checked. All computation runs in separate processes, so the notebook does not need a
restart after this cell.
""")

code('''
if IN_COLAB:
    r = subprocess.run([sys.executable, "-m", "pip", "install", "-q", "-r",
                        str(ENGINE / "requirements.txt")], capture_output=True, text=True)
    print(r.stdout[-2000:], r.stderr[-2000:])
    if r.returncode != 0:
        raise RuntimeError("pip could not install the pinned versions; see the message above")

pins = {}
for line in (ENGINE / "requirements.txt").read_text().splitlines():
    line = line.split("#")[0].strip()
    if "==" in line:
        name, ver = line.split("==")
        pins[name.split("[")[0].lower()] = ver
probe = subprocess.run([sys.executable, "-c", """
import json, sys, platform, os
from importlib import metadata
names = %r
out = {n: metadata.version(n) for n in names}
out['python'] = sys.version.split()[0]
out['platform'] = platform.platform()
out['cpus'] = os.cpu_count()
print(json.dumps(out))
""" % list(pins)], capture_output=True, text=True)
ENV = json.loads(probe.stdout)
mismatch = {n: (ENV[n], v) for n, v in pins.items() if ENV.get(n) != v}
for n, v in pins.items():
    print(f"  {n:22s} pinned {v:10s} installed {ENV.get(n)}")
print(f"  python {ENV['python']}, {ENV['cpus']} CPUs, {ENV['platform']}")
if mismatch:
    print("\\nWARNING: versions differ from the pins; scores may not reproduce exactly:", mismatch)
(RESULTS / "environment.json").write_text(json.dumps({"env": ENV, "pins": pins,
    "mismatch": mismatch, "profile": PROFILE}, indent=1))
''')

md("## 4. Engine self-test")

code('''
if RUN_ENGINE_TESTS:
    t = subprocess.run([sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider"],
                       cwd=ENGINE, capture_output=True, text=True)
    summary = [l for l in t.stdout.splitlines() if "passed" in l or "failed" in l or "error" in l]
    print(summary[-1] if summary else t.stdout[-1500:])
    (RESULTS / "engine_tests.txt").write_text(t.stdout + t.stderr)
    if t.returncode != 0:
        print("WARNING: some engine tests failed; read engine_tests.txt before trusting a re-run")
else:
    print("skipped")
''')

md("## 5. The run plan")

code('''
PLAN = pc.load_plan(BUNDLE / "plan.json")
print("Profiles:")
print(pc.profile_table(PLAN))
SWEEPS = pc.select(PLAN, PROFILE)
CHUNKS = [c for e in SWEEPS for c in pc.chunks_for(e, ENGINE)]
print(f"\\nProfile '{PROFILE}': {len(SWEEPS)} sweeps in {len(CHUNKS)} chunks")
for e in SWEEPS:
    split = "per dataset and model" if e["heavy"] else "per dataset"
    print(f"  {e['config_name']:34s} {e['group']:18s} {e['local_hours']:6.2f} h originally, split {split}")
if PLAN["excluded"]:
    print("\\nNot re-run:", PLAN["excluded"])
''')

md("""
## 6. Run the experiments

Resumable. Each chunk is saved to Drive when it finishes. The cell stops cleanly when
`BUDGET_HOURS` is reached; run it again (or *Run all*) to continue where it stopped.
""")

code('''
COMPLETE = pc.run_chunks(CHUNKS, ENGINE, RESULTS, WORK / "tmp", budget_hours=BUDGET_HOURS)
SPEED = pc.speed_factor(RESULTS, ORIGINAL_DB)
if SPEED:
    print(f"\\nThis machine takes {SPEED:.2f}x the original time per run.")
    print(pc.profile_table(PLAN, SPEED))
''')

md("## 7. Record the results")

code('''
NEW_DB = RESULTS / "lab_colab.db"
m = pc.merge(RESULTS, NEW_DB)
print(f"merged {m['chunks']} chunks into {NEW_DB.name}: {m['runs']:,} runs")
import sqlite3
con = sqlite3.connect(NEW_DB)
for status, n in con.execute("select status, count(*) from runs group by 1"):
    print(f"  {status:10s} {n:,}")
print()
for name, n, h in con.execute("select config_name, count(*), sum(wall_seconds)/3600.0 "
                              "from runs group by 1 order by min(started_at)"):
    print(f"  {name:34s} {n:5d} runs  {h:6.2f} h")
con.close()
if not COMPLETE:
    print("\\nNOTE: the profile is not finished; the results below cover the chunks done so far.")
''')

md("""
## 8. Reproduction check: the re-run against the original record

Each cell (one sweep, dataset, model and technique) is compared with the original. *Identical*
means the per-fold scores match to the last digit. Cells the original recorded more than once
are compared on their most recent row, as the analyses do.
""")

code('''
RAN = sorted({c["config_name"] for c in CHUNKS})
CMP = pc.compare(ORIGINAL_DB, NEW_DB, RESULTS / "comparison.csv", configs=set(RAN))
print(pc.describe_comparison(CMP))
(RESULTS / "comparison_summary.json").write_text(json.dumps(CMP, indent=1, default=str))
if CMP["mismatches"]:
    print("\\nFirst mismatching cells:")
    for mm in CMP["mismatches"][:20]:
        print("  ", mm)
''')

md("""
## 9. Re-run the analyses

Every analysis behind Chapter 4 is run twice: once on the re-run record and once on the
original record restricted to the same sweeps. Identical outputs mean the conclusions
reproduce, not only the raw scores. Analyses whose sweeps are not in this profile report
that they have too little data; that is expected for the smaller profiles.
""")

code('''
ANALYSIS = BUNDLE / "analysis"
ORIG_SCOPE = WORK / "original_scope.db"
pc.filtered_copy(ORIGINAL_DB, ORIG_SCOPE, RAN)
print("On the re-run record:")
st_new = pc.run_analyses(ANALYSIS, NEW_DB, ENGINE / "src", RESULTS / "figures",
                         RESULTS / "analysis_out", RESULTS / "analysis_rerun")
print("\\nOn the original record (same sweeps):")
st_old = pc.run_analyses(ANALYSIS, ORIG_SCOPE, ENGINE / "src", WORK / "figures_original",
                         WORK / "analysis_out_original", RESULTS / "analysis_original")
DIFF = pc.diff_analyses(RESULTS / "analysis_original", RESULTS / "analysis_rerun", st_old, st_new)
print("\\nDo the analyses reproduce?")
for k, v in DIFF.items():
    print(f"  {k:32s} {v}")
''')

code('''
for name in ["report_figures", "imputation_three_seeds", "wide_imputation_check", "heldout_test"]:
    print("=" * 78, "\\n", name, "\\n" + "=" * 78)
    if st_new.get(name + ".py") == "ok":
        print((RESULTS / "analysis_rerun" / f"{name}.txt").read_text()[-3500:])
    else:
        print(st_new.get(name + ".py"), "for this profile")
''')

md("## 10. Figures from the re-run")

code('''
from IPython.display import Image, display, Markdown
figs = sorted((RESULTS / "figures").glob("*.png"))
if not figs:
    print("no figures yet; the smaller profiles do not contain the sweeps the figures need")
for f in figs:
    display(Markdown(f"**{f.stem}**"))
    display(Image(filename=str(f), width=900))
''')

md("## 11. Package the results for the report")

code('''
tests_file = RESULTS / "engine_tests.txt"
TESTS = "not run"
if tests_file.exists():
    hits = [l for l in tests_file.read_text().splitlines() if " passed" in l]
    TESTS = hits[-1].strip() if hits else "see engine_tests.txt"
lines = [
    "# Pipeline Lab: Colab re-run results",
    "",
    f"Profile: {PROFILE}  ",
    f"Finished: {datetime.datetime.now().isoformat(timespec='minutes')}  ",
    f"Profile complete: {'yes' if COMPLETE else 'no, partial'}  ",
    f"Environment: Python {ENV['python']}, {ENV['cpus']} CPUs, {ENV['platform']}  ",
    f"Library versions match the pins: {'yes' if not mismatch else 'NO ' + str(mismatch)}  ",
    f"Speed relative to the original machine: {SPEED}x  ",
    f"Engine self-test: {TESTS} (the 6 skips compare the injector with the earlier B2 "
    "artefact, which is not part of the bundle)  ",
    "",
    "## Reproduction",
    "",
    "```",
    pc.describe_comparison(CMP),
    "```",
    "",
    "## Analyses",
    "",
    "| analysis | original vs re-run |",
    "|---|---|",
] + [f"| {k} | {v} |" for k, v in DIFF.items()]
(RESULTS / "COLAB_RESULTS.md").write_text("\\n".join(lines) + "\\n")
print("\\n".join(lines))

archive = BUNDLE / f"PipelineLab_Colab_Results_{PROFILE}"
shutil.make_archive(str(archive), "zip", RESULTS)
print(f"\\nresults packaged: {archive}.zip")
if IN_COLAB:
    from google.colab import files
    files.download(f"{archive}.zip")
''')

nb = {"cells": CELLS,
      "metadata": {"kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"},
                   "language_info": {"name": "python"}, "colab": {"provenance": []}},
      "nbformat": 4, "nbformat_minor": 5}
for c in nb["cells"]:
    c["source"] = c["source"].splitlines(keepends=True)
(HERE / "main_colab.ipynb").write_text(json.dumps(nb, indent=1), encoding="utf-8")
print(f"written main_colab.ipynb: {len(CELLS)} cells "
      f"({sum(c['cell_type'] == 'code' for c in CELLS)} code)")
