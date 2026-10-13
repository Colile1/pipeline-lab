# backend/app/api/

FastAPI route handlers. Thin — each handler validates the request shape,
calls into `core/` or `engines/`, and returns JSON. No business logic here.

| File | Responsibility |
|---|---|
| `datasets.py` | `GET /api/datasets?engine=` list catalogue rows; `POST /api/datasets/upload` accept a CSV, delegate to `uploads/` |
| `experiments.py` | `GET /api/experiments/choices?engine=&factor=` fixed techniques/models/mechanisms from `engines/`; `POST /api/experiments` build+validate a wizard form (with an `"engine"` field) via `core/config_builder.py`, return `{engine, config_path}` |
| `runs.py` | `GET /api/runs` list every run this server process tracks (`{run_id, engine, state}`, newest first, the fast exit-code-only state — added for the frontend's Runs page, beyond the build-order's original three endpoints); `POST /api/runs` build+validate a wizard form (with an `"engine"` field, same shape as `POST /api/experiments`) and launch it via `core/runner.py`, return `{run_id, engine, config_path, log_path}`; `GET /api/runs/{run_id}` full validation summary via `core/run_status.py`; `GET /api/runs/{run_id}/log?offset=` tail the run log from a byte offset |
| `lab.py` | `GET /api/lab/choices` the engine's own components/techniques/baselines/models/datasets; `POST /api/lab/estimate` cost a sweep without running it (`runs`, `model_fits`, `estimated_minutes`, warnings, `blocked`); `POST /api/lab/runs` cost then launch, requiring `confirm_cost=true` above the warning threshold |
| `results.py` | `GET /api/results/{run_id}` read a succeeded run's real result tables: prepfx's own `tables/{arm}_summary.csv`/`{arm}_verdicts.csv` and `results/{arm}_catalogue.csv` under its isolated `output_dir`; b2's results, which have no per-run file, extracted on demand via `engine.extract_results()` and cached as `results.csv` under the run's own directory |

## Integration

Depends on `core/` (pure logic) and `engines/` (per-codebase adapters).
Mounted in `app/main.py`. Never imports `uploads/` internals directly from
more than one router — upload logic is called only from `datasets.py`.
Every router resolves an engine name through `engines/registry.py::get_engine`
(a single 400 for an unknown name, in one place) rather than keeping its
own copy of the engine list.

`POST /api/experiments` writes into the target engine's real `configs/`
directory by default (the same place its own pre-registered configs live),
and `config_builder.write_config` refuses to overwrite an existing file
there — a name collision is a 409, never a silent replace. Tests that hit
this route must monkeypatch `PrepfxEngine.configs_dir`/`B2Engine.configs_dir`
to a temp directory first (see `tests/test_experiments_api.py`); the
autouse `conftest.py` fixture deliberately leaves `configs_dir` alone, since
`test_config_builder.py` needs it pointed at the real folder to read real
example configs.

`POST /api/runs` is independent of `POST /api/experiments` — it calls
`build_config_dict` (not `build_config`) and hands the dict straight to
`runner.start_run`, which writes its own copy of the config into
`data/runs/<run_id>/` with `outputs_dir` isolated. A run therefore never
touches the engine's real `configs/` directory, so the collision guard
above does not apply here. `GET /api/runs/{run_id}` and `/log` 404 for a
run-id this server process is not tracking (including one launched before
a restart) — never reported as success, failure, or an empty log.

`GET /api/results/{run_id}` only ever returns tables for a run whose
`run_status.summarise_validation` reports `succeeded` — a still-running or
failed run is a 409, never a partial or fabricated table. b2 has no
per-run output file (every run logs to one shared `mlflow.db`, namespaced
by the config's `experiment` name); its results are extracted the first
time they are requested, using b2's own `mlflow` client under b2's own
interpreter (`engines/b2/extract_results.py`, run via
`engines/registration.py::run_engine_script`), and cached as
`data/runs/<run_id>/results.csv` so a second request reads the file
instead of re-querying MLflow.

`POST /api/lab/estimate` is the one route whose output is load-bearing
rather than informational. The run count alone badly understates the
work: nested CV turns 18 runs into 2,880 model fits. So the estimate
sums cost per **(technique, model)** pair -- candidate counts differ by
model (logreg's grid has 4, svm's 6) and by level (random/bayesian use
10) -- and reports an estimated duration from a measured ~0.1 s/fit
(logreg 34-43 ms, svm 27-29 ms, random_forest 231-304 ms on small
datasets, k=10, 2026-10-10). Thresholds: warn above 10,000 fits
(~17 min), refuse above 250,000 (~7 h), where `confirm_cost` does not
help.

Note `inner_k` and `confirm_cost` are API-level knobs, not wizard
fields; both routes strip them before `normalise_form`, which rejects
unknown fields. `/estimate` originally did not, which made `inner_k`
silently dead at its default -- there is a regression test for it.

## Done when

Each route has at least one test in `backend/tests/` that hits it via
FastAPI's `TestClient` and asserts on real response shape.
