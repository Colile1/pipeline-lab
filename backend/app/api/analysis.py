# /api/analysis - the read side of the run record.
#
# Everything here reads the engine's lab.db directly rather than the
# in-memory run registry, so a sweep launched from the command line and
# one launched from the Compose page are the same thing to the UI, and
# nothing is lost when the server restarts.
#
# /pulse is the cheap endpoint the pages poll: it returns the record's
# modification time and row count and nothing else, so a page can ask
# "has anything changed?" many times without re-running aggregates.
from fastapi import APIRouter, HTTPException, Query

from ..core import catalogue, findings

router = APIRouter(prefix="/api/analysis", tags=["analysis"])


def _guard(call, *args, **kwargs):
    """Run a catalogue call, turning its errors into readable 4xx.

    Something that is simply not there is a 404; a malformed request,
    such as an unknown column name, is the caller's mistake and a 400.
    """
    try:
        return call(*args, **kwargs)
    except catalogue.CatalogueError as exc:
        message = str(exc)
        missing = message.startswith("No run record") or "no run recorded" in message
        raise HTTPException(
            status_code=404 if missing else 400, detail=message
        ) from exc


@router.get("/pulse")
def pulse() -> dict:
    """Cheap change-detector for auto-refresh.

    Returns the record's mtime and row count. A page polls this and only
    re-fetches the expensive views when one of them moves, so an idle
    dashboard costs almost nothing.
    """
    path = catalogue.db_path()
    if not path.exists():
        return {"exists": False, "mtime": 0.0, "total_runs": 0, "running": False}
    with catalogue.connect() as c:
        total = c.execute("select count(*) from runs").fetchone()[0]
        # A row whose end time is missing is still in flight.
        running = c.execute(
            "select count(*) from runs where ended_at is null"
        ).fetchone()[0]
    return {
        "exists": True,
        "mtime": catalogue.record_mtime(),
        "total_runs": total,
        "running": bool(running),
    }


@router.get("/overview")
def overview() -> dict:
    """Headline counts for the dashboard strip."""
    return _guard(catalogue.overview)


@router.get("/summary")
def research_summary() -> dict:
    """Programme totals and the factor-by-model sensitivity map.

    Backs the research summary page. Computed from the record on every
    request so the page cannot drift from the database.
    """
    return _guard(catalogue.research_summary)


@router.get("/sweeps")
def sweeps() -> dict:
    """Every recorded sweep, however it was launched."""
    return {"sweeps": _guard(catalogue.sweeps)}


@router.get("/dimensions")
def dimensions() -> dict:
    """What can be plotted, taken from what was actually run."""
    return _guard(catalogue.dimensions)


@router.get("/columns")
def columns() -> dict:
    """The schema's own column explanations, for tooltips."""
    return {"columns": _guard(catalogue.column_notes)}


@router.get("/runs")
def runs(config_name: str | None = None, status: str | None = None,
         dataset: str | None = None, model: str | None = None,
         limit: int = Query(500, ge=1, le=2000),
         offset: int = Query(0, ge=0)) -> dict:
    """Filtered rows from the record."""
    return _guard(catalogue.runs, config_name=config_name, status=status,
                  dataset=dataset, model=model, limit=limit, offset=offset)


@router.get("/run/{run_id}")
def run_detail(run_id: str) -> dict:
    """One run, every recorded field, with its per-fold scores."""
    return _guard(catalogue.run_detail, run_id)


@router.get("/aggregate")
def aggregate(x: str = "scaling", y: str = "accuracy_mean",
              group: str = "none", config_name: str | None = None,
              task_type: str | None = None, model: str | None = None) -> dict:
    """Mean and range of a metric, split by one or two dimensions."""
    return _guard(catalogue.aggregate, x=x, y=y, group=group,
                  config_name=config_name, task_type=task_type, model=model)


@router.get("/findings")
def sweep_findings(config_name: str) -> dict:
    """Every testable finding in one sweep.

    This is the statistical framework, not a summary of means: Friedman
    first, post-hoc only when licensed, Holm correction, effect sizes
    always, and an explicit power verdict so a result that *cannot* be
    significant is never read as evidence of no effect.
    """
    if not findings.scipy_available():
        return {
            "available": False,
            "config_name": config_name,
            "findings": [],
            "reason": "scipy is not installed in this environment, so no "
                      "statistical test can run here. Install it with "
                      "'pip install -r requirements.txt'. The recorded "
                      "measurements shown elsewhere are unaffected.",
        }
    try:
        results = findings.headline(config_name)
    except catalogue.CatalogueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {"available": True, "config_name": config_name,
            "findings": results, "reason": ""}


@router.get("/finding")
def one_finding(config_name: str, metric: str, task_type: str,
                model: str | None = None) -> dict:
    """One finding in full, for the drill-down panel."""
    if not findings.scipy_available():
        raise HTTPException(
            status_code=503,
            detail="scipy is not installed in this environment, so no "
                   "statistical test can run here.",
        )
    try:
        return findings.analyse(config_name, metric, task_type, model)
    except catalogue.CatalogueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/export")
def export(config_name: str | None = None) -> dict:
    """The raw rows, for a reader who wants the numbers themselves.

    Returned as JSON with the column notes attached so the file explains
    its own fields. The UI turns this into a CSV download client-side,
    which keeps the server from having to hold a whole sweep in memory
    twice.
    """
    data = _guard(catalogue.runs, config_name=config_name, limit=2000)
    return {
        "rows": data["rows"],
        "total": data["total"],
        "columns": _guard(catalogue.column_notes),
        "record_path": str(catalogue.db_path()),
    }
