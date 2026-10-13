# backend/app/engines/

One adapter per target research codebase. Each adapter is the single
source of truth, inside this app, for that engine's fixed experimental
design, config schema, dataset catalogue location, and run command. It
must mirror the target repo's own design notes — never invent a field or a
technique that repo doesn't actually support.

| File | Responsibility |
|---|---|
| `base.py` | `Engine` protocol: `name`, `root_path`, `configs_dir`, `outputs_dir`, `catalogue_path`, `fixed_techniques(factor) -> list[str]`, `fixed_models() -> list[str]`, `valid_mechanisms() -> list[str]`, `build_config_dict(form) -> dict`, `run_command(config_path) -> list[str]`, `list_datasets() -> list[dict]`, `log_markers() -> dict`, `read_achieved_missingness(output_dir, config) -> dict \| None`, `extract_results(run_dir, config) -> Path \| None` |
| `prepfx.py` | Concrete `PrepfxEngine` — root `../preprocessing-effects-framework`, scaling ∈ {standard, minmax, robust, none}, imputation ∈ {mean, median, knn}, models ∈ {logistic, svm, random_forest, gradient_boosting} (its own `pipelines/models.py` key is `logistic`, not `logreg`), config keys `arm/seed/cv.k/datasets/missingness.{proportion,mechanism}/models/tracking.experiment_name/outputs_dir`, mechanisms {mcar, mar, mnar}, one rate+mechanism per config, whole arm only (no technique subset); `list_datasets()` reads the DATASETS dict in src/prepfx/datasets/registry.py (24 registered datasets, excludes LARGE_DATASETS/MONSTER_DATASETS); `extract_results()` is a no-op — prepfx already writes its own `tables/{arm}_summary.csv`/`{arm}_verdicts.csv` |
| `registration.py` | `engine_python(root_path) -> str` (the engine's own `.venv` interpreter); `run_engine_script(root_path, script, options, error_cls, action) -> dict` (generic: run a script under the engine's interpreter, parse its JSON, raise `error_cls` on failure); `run_register_script(...)` is a thin wrapper of it fixed to `DatasetRegistrationError` |
| `registry.py` | `ENGINES` (name -> adapter class) and `get_engine(name) -> Engine` — the one place `api/` resolves "prepfx"/"b2"/"lab", so every router gets the same 400 for an unknown name |
| `lab.py` | Concrete `LabEngine` — root `../../pipeline-lab-engine`, the full Chapter 1 design: **5 OFAT components** (encoding, imputation, scaling, selection, tuning) plus the four models compared throughout. Config keys `name/vary/techniques/baseline/datasets/models/seed/evaluation/outputs_dir` — a **third** schema shape alongside prepfx's `arm` and b2's `factor`. Injects no missingness, so `valid_mechanisms()` is empty and `read_achieved_missingness()` is None. `extract_results()` returns the engine's own `lab.db` (no MLflow indirection, no subprocess). Dataset upload raises with an explanation rather than pretending |
| `prepfx/register_dataset.py`, `b2/register_dataset.py` | Scripts run under the engine's own interpreter: cache the CSV, characterise it with the engine's own function, append to the engine's user-dataset file, verify the engine's loader reads it back, print one JSON line |
| `b2/extract_results.py` | Runs under b2's own interpreter: reads one experiment's logged runs back out of b2's own `mlflow.db` (via b2's own `tracking.store.default_tracking_uri`), using the engine's own `mlflow` client, and writes them as a plain CSV; prints `{"results_path": ..., "rows": ...}` (path `None`/rows `0` when the experiment has no runs — never invents a row) |
| `b2.py` | Concrete `B2Engine` — root `../Artefact/Research_Impact_of_Preprocess`, same technique list and the same four model families but named `logreg` (not `logistic`) for logistic/linear regression, config keys `experiment/factor/techniques/datasets/models/k/seed/missingness_rates/missingness_mechanisms`, factor named `scaler`/`imputer`, mechanisms {mcar, mar}; `list_datasets()` reads datasets/catalogue.csv rows verbatim; `extract_results()` runs `b2/extract_results.py` under b2's interpreter, keyed by the config's `experiment` name |

**`lab.py` imports its fixed lists from the engine rather than copying
them.** `prepfx.py` and `b2.py` hardcode theirs, which is exactly how
`PrepfxEngine` came to claim the model key `logreg` when prepfx's own
key is `logistic` — a bug that survived three build steps because
nothing had executed a real prepfx run. `LabEngine` reads
`piplab.config.TECHNIQUES/MODELS/BASELINES` directly, so that class of
drift is impossible, and a test asserts the lists still match.

**The two engines name the logistic/linear-regression model differently**
(prepfx: `logistic`, b2: `logreg`) — confirmed against each engine's own
`pipelines/models.py`. Never assume `fixed_models()` lists match between
engines; a wizard built against one engine's model names will be rejected
at launch by the other.

**Log markers** (`log_markers()`) are copied verbatim from each engine's
own `print()` calls in its `run_experiment.py`, and checked against a real
run log. They are not a shared format: prepfx counts progress in datasets
(`Dataset done:`) against `Grid configurations:`, while b2 counts
combinations (`Run complete:`) against `Combinations:`. prepfx also prints
a non-fatal `Tracking warning:` when MLflow will not start, which must not
be treated as a failure; b2's `run_experiment.py` has no `try`/`except` at
all, so anything alarming in its log is a genuine traceback.

**Achieved missingness** (`read_achieved_missingness()`) is only available
for prepfx, which measures and writes `missing_proportion` per dataset
into `<outputs_dir>/results/<arm>_catalogue.csv`. b2 returns `None`: it
logs `missing_rate` to MLflow as a *parameter* (the requested rate echoed
back) and `inject_missing()` records no realised rate, so there is nothing
to verify against. Reporting b2's requested rate as "achieved" would be a
false confirmation, which is exactly what step 8 exists to prevent.

**Results extraction** (`extract_results()`) exists only because the two
engines store results completely differently: prepfx writes its own
`tables/{arm}_summary.csv`/`{arm}_verdicts.csv` under the run's isolated
`output_dir`, so there is nothing to extract (no-op, returns `None`). b2
logs every run to one shared `mlflow.db` across all experiments
(`tracking/store.py`'s `default_tracking_uri`), namespaced only by the
config's `experiment` name, so `api/results.py` cannot read a file
directly — `B2Engine.extract_results()` runs `b2/extract_results.py`
under b2's own interpreter (so the `mlflow` package and schema stay b2's
own concern, never the dashboard's) and writes the result rows to
`results.csv` in the run's own directory, read back like any other CSV.
This keeps `api/results.py` engine-agnostic: it only ever reads CSVs,
never queries MLflow itself.

## Integration

Used by `core/config_builder.py`, `core/runner.py`, `core/run_status.py`,
and `api/datasets.py`/`api/experiments.py`. Nothing outside this folder
should read a target repo's config examples directly — route it through
an `Engine`.

## Done when

For each engine, a unit test confirms `fixed_techniques`/`fixed_models`
match the lists stated in that target repo's own design notes, and
`run_command` matches the exact invocation shown in that repo's own
README commands section.
