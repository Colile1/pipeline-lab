# backend/app/core/

Pure logic. No subprocess calls, no network calls. The two exceptions,
where a function's whole job is exactly that: `config_builder.write_config`
writes a file, and `runner.start_run` launches a subprocess. Everything
else takes data in, returns data out, and is unit-testable without a
filesystem or a running engine.

| File | Responsibility | Key signatures |
|---|---|---|
| `errors.py` | UI-facing failure types: `ConfigValidationError`, `ConfigNameConflictError`, `UploadValidationError`, `DatasetRegistrationError`, `RunLaunchError`, `ResultsExtractionError` | one `Exception` subclass each, constructed with a UI-ready message |
| `form_schema.py` | Normalise + check a wizard dict against an engine's fixed design, in engine-neutral terms | `normalise_form(engine, form) -> WizardForm`; `supported_factors(engine) -> tuple[str, ...]` — asks the engine which components it varies (prepfx/b2 vary 2, lab varies 5) rather than assuming a global list |
| `config_builder.py` | Turn a validated form into that engine's own schema (delegated to the adapter) and write it as YAML | `build_config_dict(engine, form: dict) -> dict`; `build_config(engine, form: dict, configs_dir=None) -> Path`; `write_config(config: dict, name: str, target_dir: Path) -> Path` (writes an already-built dict, e.g. with `outputs_dir` overridden by the runner) — raises `ConfigValidationError` with a specific reason on any invalid combo, `ConfigNameConflictError` if the slugged filename already exists in `target_dir` (never overwrites, since that may be an engine's real `configs/` directory) |
| `runner.py` | Launch an engine's `run_experiment.py` under that engine's own `.venv` interpreter as a detached background process (`subprocess.Popen`), tracked by run-id; isolates a run's `outputs_dir` (where the engine's schema has one) into that run's own directory so a run can never overwrite the engine's real results | `start_run(engine, config: dict, experiment_name: str) -> RunHandle`; `get_process(run_id: str) -> RunHandle \| None`; `list_runs() -> list[RunHandle]` (newest first; added for the frontend's Runs page) — raises `RunLaunchError` if the config can't be written or the process can't start |
| `run_status.py` | Parse a run's log + output files into a validation summary | `get_status(run_id: str) -> str` (one of `RUNNING`/`SUCCEEDED`/`FAILED`/`UNKNOWN`); `summarise_validation(handle: RunHandle, engine: Engine, config: dict \| None = None) -> ValidationSummary` (folds expected/completed, errors, achieved-vs-requested missingness; `config` defaults to `handle.config` when omitted) |

## Integration

Called by `api/`. Depends on `engines/` for per-codebase fixed-design
lists, schema, and paths — never hardcodes an engine's config field names
itself.

## Done when

`config_builder.build_config` output for a known-good wizard payload is
structurally identical (same keys/values) to a real example config
already in that engine's `configs/` folder. `run_status` correctly
flags a deliberately-broken config as failed, not successful.
