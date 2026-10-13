# /api/runs - launch a wizard form as a real background run, check its
# status/validation summary, and tail its log.
from dataclasses import asdict

from fastapi import APIRouter, HTTPException

from ..core.config_builder import build_config_dict
from ..core.errors import ConfigValidationError, RunLaunchError
from ..core.run_status import get_status, summarise_validation
from ..core.runner import get_process, list_runs, start_run
from ..engines.registry import get_engine

router = APIRouter(prefix="/api/runs", tags=["runs"])


def _get_handle_and_engine(run_id: str):
    """Look up a tracked run and its matching engine adapter.

    Inputs: run_id - the id returned by a prior POST /api/runs.
    Output: (handle, engine) tuple.
    Raises: HTTPException 404 if this server process is not tracking that
    run-id (including a run launched before a restart — see
    core.runner.get_process).
    """
    handle = get_process(run_id)
    if handle is None:
        raise HTTPException(
            status_code=404,
            detail=(
                f"No run tracked with id '{run_id}'. It may have been launched "
                "before this server last restarted — its log and output files "
                "on disk, if any, are unaffected, but its status cannot be "
                "reported here."
            ),
        )
    return handle, get_engine(handle.engine_name)


@router.get("")
def list_tracked_runs() -> list[dict]:
    """List every run this server process currently tracks, newest first.

    Inputs: none.
    Output: list of {"run_id", "engine", "state"} — state is the fast
    exit-code-only check (core.run_status.get_status), not the full log
    parse; call GET /api/runs/{run_id} for the full validation summary. A
    run launched before this server process last restarted is not listed
    (see core.runner.list_runs).
    """
    return [
        {"run_id": h.run_id, "engine": h.engine_name, "state": get_status(h.run_id)}
        for h in list_runs()
    ]


@router.post("")
def create_run(form: dict) -> dict:
    """Validate a wizard form and launch it as a real background run.

    Inputs: form - the wizard payload; must include "engine" ("prepfx" or
    "b2") alongside the fields core.form_schema.normalise_form expects
    (name, factor, techniques, datasets, models, k, seed, and, for the
    imputation factor, missingness_rates/missingness_mechanisms).
    Output: dict with "run_id", "engine", "config_path" and "log_path".
    The run's own written config lives under data/runs/<run_id>/ — never
    the engine's own configs/ or outputs/ directories (see core/runner.py).
    Raises: HTTPException 400 if "engine" is missing or unknown, 422 with
    the specific reason if the form fails validation, 500 if the engine's
    own interpreter or process could not be started.
    """
    engine_name = form.get("engine")
    if not engine_name:
        raise HTTPException(status_code=400, detail="Field 'engine' is required.")
    adapter = get_engine(engine_name)
    wizard_form = {k: v for k, v in form.items() if k != "engine"}
    try:
        config = build_config_dict(adapter, wizard_form)
    except ConfigValidationError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    try:
        handle = start_run(adapter, config, wizard_form.get("name", ""))
    except RunLaunchError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return {
        "run_id": handle.run_id,
        "engine": handle.engine_name,
        "config_path": str(handle.config_path),
        "log_path": str(handle.log_path),
    }


@router.get("/{run_id}")
def get_run(run_id: str) -> dict:
    """Return one run's full validation summary.

    Inputs: run_id - the id returned by a prior POST /api/runs.
    Output: the ValidationSummary as a dict (state is one of "running",
    "succeeded", "failed"; never reported as succeeded on exit code alone
    — see core.run_status for the full rule).
    Raises: HTTPException 404 if this server process is not tracking that
    run-id.
    """
    handle, engine = _get_handle_and_engine(run_id)
    summary = summarise_validation(handle, engine)
    return asdict(summary)


@router.get("/{run_id}/log")
def get_run_log(run_id: str, offset: int = 0) -> dict:
    """Return a run's log, or the portion written since a prior offset.

    Inputs: run_id - the id returned by a prior POST /api/runs; offset -
    byte offset to read from (0 reads the whole log so far), so a caller
    polling for live output does not re-read what it already has.
    Output: dict with "text" (the log slice) and "offset" (the byte
    position to pass next time, i.e. offset + len(the bytes read)).
    Raises: HTTPException 404 if this server process is not tracking that
    run-id, 400 for a negative offset.
    """
    if offset < 0:
        raise HTTPException(status_code=400, detail="Field 'offset' must not be negative.")
    handle, _ = _get_handle_and_engine(run_id)
    try:
        with handle.log_path.open("rb") as fh:
            fh.seek(offset)
            chunk = fh.read()
    except OSError as exc:
        raise HTTPException(status_code=404, detail=f"Could not read run log: {exc}") from exc
    return {
        "text": chunk.decode("utf-8", errors="replace"),
        "offset": offset + len(chunk),
    }
