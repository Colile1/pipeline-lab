# /api/results - read a completed run's real result rows: for prepfx, its
# own tables/{arm}_summary.csv and {arm}_verdicts.csv under the run's
# isolated output_dir; for b2 (which has no per-run output file, only its
# shared mlflow.db), the engine's own extract_results() is run on demand
# and cached as run_dir/results.csv.
import csv

from fastapi import APIRouter, HTTPException

from ..core.errors import ResultsExtractionError
from ..core.run_status import FAILED, RUNNING, SUCCEEDED, summarise_validation
from ..core.runner import get_process
from ..engines.registry import get_engine

router = APIRouter(prefix="/api/results", tags=["results"])


@router.get("/{run_id}")
def get_results(run_id: str) -> dict:
    """Return one completed run's real result tables.

    Inputs: run_id - the id returned by a prior POST /api/runs.
    Output: dict with "run_id", "engine", "state", and "tables" — a dict
    of {table_name: [row, ...]}, each row read verbatim from a CSV the
    engine itself wrote (or, for b2, extracted from its own MLflow store
    by b2's own code). Never includes a table for a run that has not
    succeeded.
    Raises: HTTPException 404 if this server process is not tracking that
    run-id, 409 if the run has not finished or did not succeed (results
    are only meaningful for a succeeded run), 500 if b2's own result
    extraction fails.
    """
    handle = get_process(run_id)
    if handle is None:
        raise HTTPException(
            status_code=404,
            detail=(
                f"No run tracked with id '{run_id}'. It may have been launched "
                "before this server last restarted."
            ),
        )
    engine = get_engine(handle.engine_name)
    summary = summarise_validation(handle, engine)
    if summary.state == RUNNING:
        raise HTTPException(status_code=409, detail="This run has not finished yet.")
    if summary.state == FAILED:
        raise HTTPException(
            status_code=409,
            detail="This run did not succeed, so it has no results to report.",
        )
    if summary.state != SUCCEEDED:
        raise HTTPException(
            status_code=409,
            detail=f"This run's state ('{summary.state}') cannot be confirmed as succeeded.",
        )

    tables = _read_native_tables(handle)
    if not tables:
        tables = _read_extracted_table(handle, engine)
    return {"run_id": run_id, "engine": handle.engine_name, "state": summary.state, "tables": tables}


def _read_native_tables(handle) -> dict:
    """Read every CSV an engine wrote directly into this run's output_dir.

    Inputs: handle - the RunHandle.
    Output: dict of {relative CSV path without extension: [row, ...]};
    empty when this engine has no per-run output_dir (b2).
    """
    if handle.output_dir is None or not handle.output_dir.is_dir():
        return {}
    tables = {}
    for csv_path in sorted(handle.output_dir.rglob("*.csv")):
        name = str(csv_path.relative_to(handle.output_dir).with_suffix("")).replace("\\", "/")
        tables[name] = _read_csv_rows(csv_path)
    return tables


def _read_extracted_table(handle, engine) -> dict:
    """Extract (if needed) and read an engine's own results.csv.

    Inputs: handle - the RunHandle; engine - the matching Engine adapter.
    Output: dict with one key, "results", when the engine's extraction
    found rows; empty dict when there is nothing to extract (prepfx, which
    already has native tables) or nothing found.
    Raises: HTTPException 500 if extraction fails.
    """
    results_path = handle.run_dir / "results.csv"
    if not results_path.is_file():
        try:
            extracted = engine.extract_results(handle.run_dir, handle.config)
        except ResultsExtractionError as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc
        if extracted is None:
            return {}
        results_path = extracted
    return {"results": _read_csv_rows(results_path)}


def _read_csv_rows(path) -> list[dict]:
    """Read a CSV file's rows verbatim, as a list of dicts.

    Inputs: path - the CSV file.
    Output: list of row dicts in the file's own column order and values —
    no computed or reformatted fields.
    """
    with open(path, newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))
