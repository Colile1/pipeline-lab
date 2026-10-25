# Pipeline Lab on Google Colab

This folder re-runs the Pipeline Lab experiments in a fresh environment, checks every new
result against the original run record, re-runs the analyses behind Chapter 4, and draws the
figures. Everything is driven by one notebook, `main_colab.ipynb`, run from top to bottom.

## What is in the folder

| file | what it is |
|---|---|
| `main_colab.ipynb` | the notebook; run it top to bottom |
| `pipelab_colab.py` | the code the notebook calls (planning, running, merging, comparing) |
| `plan.json` | every sweep, the config files that reproduce it, its original cost, the profiles |
| `pipeline-lab-engine.zip` | the engine at git tag `iteration-v5-2026-10-19`, with the original run record |
| `analysis/` | the analysis scripts that produce the Chapter 4 results and figures |
| `sklearn_data.zip` | the dataset files the original runs used |

## Running it

1. Upload the whole `PipelineLab_Colab` folder to Google Drive so that it is at
   `MyDrive/PipelineLab_Colab`. Uploading `PipelineLab_Colab.zip` to `MyDrive/` also works;
   the notebook unpacks it.
2. Open `main_colab.ipynb` in Colab (double-click it in Drive, then *Open with Colaboratory*).
3. In the first code cell, set `PROFILE`. Start with `smoke`.
4. *Runtime > Run all*. Approve the Google Drive prompt when it appears.

## Profiles and time

| profile | sweeps | time on the original machine |
|---|---|---|
| `smoke` | 2 | 0.2 h |
| `headline` | 22 | 13.1 h |
| `widened` | 12 | 24.5 h |
| `core` | 19 | 79.1 h |
| `full` | 49 | 119.2 h |

The original machine ran each sweep on many cores. A standard Colab runtime has two, so expect
Colab to be slower; after the first chunks finish, cell 6 prints the measured speed ratio and
the projected time for every profile. Use that projection to decide how far to go in the time
available. In one week, `smoke` then `headline` is realistic on a standard runtime; `full` is
only realistic with a faster runtime running most of the week.

## When the session drops

Colab ends sessions after several hours, or sooner if the browser tab is idle. This is
expected and handled:

* every sweep is split into chunks (one per dataset, or per dataset and model for the six
  heaviest sweeps), and each chunk is saved to Drive the moment it finishes;
* re-running the notebook skips every finished chunk;
* the run cell stops cleanly at `BUDGET_HOURS` (11 h by default) so a session is not killed
  in the middle of writing.

So: reconnect, and *Run all* again. Nothing finished is lost.

## What comes out

Everything is written to `MyDrive/PipelineLab_Colab/results_<profile>/`:

| output | contents |
|---|---|
| `lab_colab.db` | the new run record, same format as the original |
| `comparison.csv`, `comparison_summary.json` | the cell-by-cell check against the original |
| `analysis_rerun/`, `analysis_original/` | every analysis output, on the new and the original record |
| `figures/` | the Chapter 4 figures drawn from the new record |
| `environment.json`, `engine_tests.txt` | library versions, CPU count, and the engine self-test |
| `COLAB_RESULTS.md` | a one-page summary |

The last cell also zips the folder as `PipelineLab_Colab_Results_<profile>.zip` and downloads
it. **That zip is what goes into submission package v7.**

## Differences that are expected, not faults

* **Run times.** Colab hardware is different, so `wall_seconds` will not match. The cost
  figures in the report (85.5 h, 68 per cent for tuning) describe the original machine and
  are not re-measured here; the re-run checks the *results*, not the timings.
* **Cells only in the original.** The original record holds a few rows that were later
  superseded (for example the climate_sim cells re-run after the deleted-class guard was
  fixed). The comparison uses the most recent row per cell, as the analyses do.
* **The widened-arm analysis** prints how many duplicate rows it skipped. The original has
  some from a sweep that was briefly run twice; the re-run has none, so that one line differs.
* **Six engine tests skip.** They check that the missingness injector is a bit-identical port
  of the earlier B2 artefact, which is not part of the bundle. Expect `344 passed, 6 skipped`.
* **Some analyses say "not applicable".** Each analysis needs particular sweeps; on the
  smaller profiles the ones whose sweeps are not included are reported as not applicable
  instead of being run. Only `full` makes every analysis applicable.
* **`ofat_scaling_full`** is not re-run. It stopped at 97 of its 112 cells, no analysis reads
  it, and `ofat_scaling_v2` supersedes it.

## If something goes wrong

* *"bundle not found"*: the folder is not at `MyDrive/PipelineLab_Colab`; check the path in
  the first code cell.
* *pip could not install the pinned versions*: the Colab Python version may not have wheels
  for a pinned library. The message names the library; the run is not trustworthy for exact
  reproduction until the versions match.
* *a chunk reports ENGINE DID NOT FINISH*: its log is in `results_<profile>/chunks/<chunk>.error.txt`.
  The chunk is not marked done, so the next run retries it.
