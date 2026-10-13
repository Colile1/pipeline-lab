# Pipeline Lab

A web UI that lets a non-technical user configure, run, and review the
ITRI671 preprocessing-effects experiments without touching the command
line  -  for both research series:

- **B1**  -  `preprocessing-effects-framework/` ("prepfx")
- **B2**  -  `Artefact/Research_Impact_of_Preprocess/`

This project does not change either research codebase's experimental
design. It is a control surface: it builds YAML configs those codebases
already accept, shells out to their existing `run_experiment.py`, and
reads back their existing output CSVs. It never implements its own
statistics, scaling, or imputation logic.

## Where results live, and how to see them

Every run - whether launched from the Compose page or from the engine's
`run_experiment.py` on the command line - writes one row to a single
SQLite file in the engine's `outputs/lab.db`, with 86 typed fields.

The dashboard reads that file **directly and read-only**. There is no
import step, no second copy and no sync job, so:

- a sweep run at the command line appears in the UI immediately;
- restarting the web server loses nothing;
- the UI cannot corrupt a record while a sweep is writing to it.

Four pages read it:

| Page | For |
|---|---|
| `/dashboard` | How much has been run, by whom, at what cost. Auto-refreshes while a sweep is in progress |
| `/findings` | What each sweep actually found: Friedman, then Wilcoxon against the baseline with Holm correction, effect sizes always, and an explicit warning when the test could not have found anything |
| `/explorer` | Any recorded field against any other, with presets and CSV export |
| `/guide` | What the project is and how to read a result, written for readers with no machine learning background |

From code, it is an ordinary SQLite database with one `runs` table, so
any SQL tool can read it. The engine's `analyse.py` runs the same
statistical framework from the command line, and a test asserts the two
agree on the real record.


## What it does

1. **Datasets**  -  browse each engine's registered dataset catalogue, or
   upload a new CSV (validated, characterised, and registered into that
   engine's catalogue  -  never silently reshaped).
2. **New experiment**  -  a wizard: pick engine (B1/B2), pick factor
   (scaling or imputation), pick datasets, pick models, set k-fold CV and
   seed, and for the imputation factor set missingness rate(s) and
   mechanism(s). Every choice is constrained to that engine's fixed
   design list (see each engine's own design notes)  -  the UI cannot express
   a technique, model, or metric the research design does not already
   allow.
3. **Run**  -  writes the YAML config, launches `run_experiment.py` as a
   background process, and streams its progress.
4. **Run validation summary**  -  after completion: config used, folds
   completed vs expected, any failed folds/errors, and sanity flags
   (e.g. achieved missingness rate vs requested, class balance) before
   the user is shown results.
5. **Results**  -  renders the engine's own summary/verdict tables as
   sortable tables and simple charts.

## Layout

| Folder | Role |
|---|---|
| `backend/app/api/` | FastAPI routes (datasets, experiments, runs, results) |
| `backend/app/core/` | Pure logic: config building, run launching, run-status parsing  -  the only I/O exceptions are writing a config file and launching a subprocess, both documented where they happen |
| `backend/app/engines/` | One adapter per research codebase (prepfx, b2): path to repo, config schema, fixed technique/model/mechanism lists, subprocess invocation under that engine's own `.venv`, output-table/results-extraction locations |
| `backend/app/uploads/` | Dataset upload handling: schema validation, characteristic computation, catalogue registration |
| `frontend/` | Static HTML/CSS/JS, plain Material/Google styling (white surfaces, one blue accent, text-only nav, no icons or emoji) - no build step, no Node |
| `data/uploads/` | Staging area for uploaded CSVs before they're registered into an engine's own dataset cache |
| `data/runs/<run-id>/` | Everything one dashboard-launched run writes: its config, its log, and (for prepfx) its isolated output directory  -  never the target engine's own `configs/`/`outputs/` |
| `docs/build-order.md` | Numbered build steps with verification |
| `start.bat` | Windows double-click launcher  -  installs dependencies, checks engine prerequisites, opens the browser, starts the server |

## Prerequisites

This app shells out to the two target repos' own `run_experiment.py`
**under each repo's own virtual environment**  -  it never installs their
dependencies (scikit-learn, mlflow, pandas pinned to *their* versions,
etc.) into its own. Before running the dashboard, set up each target
repo exactly as that repo's own README says:

```bash
cd preprocessing-effects-framework
python -m venv .venv && .venv\Scripts\activate   # Windows; see that repo's README for macOS/Linux
pip install -r requirements.txt

cd ..\Artefact\Research_Impact_of_Preprocess
python -m venv .venv && .venv\Scripts\activate
pip install -r requirements.txt
```

If a repo's `.venv` does not exist, a run launched through the dashboard
will still start, but fails almost immediately with that repo's own
import error (e.g. `ModuleNotFoundError: No module named 'sklearn'`),
surfaced verbatim in the run's validation summary  -  the dashboard falls
back to its own interpreter rather than refusing to launch, so this
looks like a run failure, not a setup error. If a run fails immediately
with an import error naming a package the dashboard itself never uses,
check that repo's `.venv` first.

## Quick start

**Windows:** double-click `start.bat` in this folder. It installs this
app's own dependencies, warns if either target engine's own `.venv` is
missing  -  all three, including the Pipeline Lab engine (see
Prerequisites above)  -  opens your browser, and starts the server. Close
its console window (or Ctrl+C) to stop it.

**Manually, any OS:**

```bash
cd backend
pip install -r ../requirements.txt
uvicorn app.main:app --reload
# open http://127.0.0.1:8000
```

Verified end to end (see `docs/build-order.md` step 13): a fresh
`python -m venv`, `pip install -r requirements.txt` from this exact
`requirements.txt`, and `uvicorn app.main:app` render all four pages and
reach the real engine adapters, on a machine that had never run this
dashboard before.

## Reproducibility contract

This app never invents or edits a result. It only ever:
- writes a config file in the exact schema the target engine already reads,
- invokes that engine's own `run_experiment.py` unmodified,
- displays files that engine itself wrote.

If a run fails or a table is missing, the UI shows that plainly  -  it does
not synthesize placeholder numbers.

## Author

Colile Sibanda, NWU Honours (ITRI671), 2026.
