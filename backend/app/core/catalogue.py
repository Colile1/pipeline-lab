# catalogue.py: read-only access to the engine's run record.
#
# WHY THIS EXISTS. Until now every lab data endpoint was keyed by the
# run_id that POST /api/lab/runs returned, and those ids live in
# core/runner.py's in-memory _PROCESSES dict. Two consequences:
# a sweep launched from the command line was invisible to the UI, and
# restarting the server lost every id, so even UI-launched sweeps became
# unreachable. The 201 rows recorded so far were all CLI runs, so the
# analysis pages could not see any real results at all.
#
# The fix is to treat the engine's lab.db as the single source of truth
# and read it directly. The engine remains the only writer; this module
# opens the file with mode=ro so the dashboard cannot corrupt a record
# mid-sweep, and so a bug here can never cost a run. Nothing is copied,
# so there is no second store to fall out of sync.
#
# Every query is parameterised and every column name is checked against
# the engine's own schema before it reaches SQL, because several
# endpoints take a column name from the query string.
from __future__ import annotations

import sqlite3
import sys
from contextlib import contextmanager
from pathlib import Path

from ..engines.registry import get_engine

# Scores that may be aggregated, and whether a larger number is better.
# RMSE is the one where lower wins; getting this backwards would invert
# every regression conclusion, so it is declared once here.
METRICS = {
    "accuracy_mean": True,
    "f1_mean": True,
    "rmse_mean": False,
    "wall_seconds": False,
    "cpu_seconds_user": False,
    "peak_rss_mb": False,
}

# Columns a reader may group or split by. Restricted to the design and
# dataset-characteristic columns: grouping by run_id or a timestamp
# produces one row per group and tells nobody anything.
DIMENSIONS = (
    "config_name", "vary", "encoding", "imputation", "scaling", "selection",
    "tuning", "model", "dataset", "task_type", "protocol", "cv_k",
    "status", "machine_fingerprint", "seed",
)


class CatalogueError(RuntimeError):
    """The record could not be read. Carries a reader-facing reason."""


def engine_src_on_path() -> Path:
    """Put the engine's src/ on sys.path and return its root.

    The dashboard runs under its own interpreter, which deliberately
    lacks the engine's dependencies. Only piplab.storage.schema is
    imported here, and that module imports nothing heavy.
    """
    engine = get_engine("lab")
    src = engine.root_path / "src"
    if str(src) not in sys.path:
        sys.path.insert(0, str(src))
    return engine.root_path


def db_path() -> Path:
    """Absolute path to the engine's run record."""
    engine = get_engine("lab")
    return Path(engine.outputs_dir) / "lab.db"


def known_columns() -> tuple[str, ...]:
    """Every column the engine's schema declares.

    Read from the engine rather than restated here, so a schema change
    cannot leave this module validating against a stale list.
    """
    engine_src_on_path()
    from piplab.storage.schema import COLUMN_NAMES

    return tuple(COLUMN_NAMES)


def column_notes() -> dict:
    """The schema's per-column explanations, for UI tooltips."""
    engine_src_on_path()
    from piplab.storage import column_notes as notes

    return notes()


@contextmanager
def connect():
    """Open the record read-only.

    Raises CatalogueError with an actionable message when the file is
    missing, which is the normal state before the first sweep.
    """
    path = db_path()
    if not path.exists():
        raise CatalogueError(
            f"No run record yet at {path}. Launch a sweep from the Compose "
            f"page, or run the engine's run_experiment.py, and it will appear."
        )
    uri = f"file:{path.as_posix()}?mode=ro"
    connection = sqlite3.connect(uri, uri=True, timeout=5.0)
    connection.row_factory = sqlite3.Row
    try:
        yield connection
    finally:
        connection.close()


def _check(name: str, allowed, what: str) -> str:
    """Validate an identifier before it is interpolated into SQL."""
    if name not in allowed:
        raise CatalogueError(
            f"unknown {what} {name!r}; valid: {', '.join(sorted(allowed))}"
        )
    return name


def record_mtime() -> float:
    """Last-modified time of the record, or 0.0 when it does not exist.

    The UI polls this to decide whether anything changed, which is far
    cheaper than re-running every aggregate on a timer.
    """
    path = db_path()
    return path.stat().st_mtime if path.exists() else 0.0


def overview() -> dict:
    """Headline counts for the dashboard's top strip."""
    with connect() as c:
        total, ok, failed, skipped = c.execute(
            "select count(*), "
            "sum(status = 'succeeded'), "
            "sum(status = 'failed'), "
            "sum(status = 'skipped') from runs"
        ).fetchone()
        spend = c.execute(
            "select coalesce(sum(wall_seconds), 0), "
            "coalesce(max(peak_rss_mb), 0) from runs"
        ).fetchone()
        datasets = c.execute("select count(distinct dataset) from runs").fetchone()[0]
        configs = c.execute("select count(distinct config_name) from runs").fetchone()[0]
        last = c.execute(
            "select max(ended_at) from runs where ended_at is not null"
        ).fetchone()[0]
    return {
        "total_runs": total or 0,
        "succeeded": ok or 0,
        "failed": failed or 0,
        "skipped": skipped or 0,
        "datasets": datasets or 0,
        "sweeps": configs or 0,
        "compute_seconds": round(spend[0], 1),
        "peak_rss_mb": round(spend[1], 1),
        "last_run_ended": last,
        "record_path": str(db_path()),
        "record_mtime": record_mtime(),
    }


def sweeps() -> list[dict]:
    """One row per recorded sweep, newest first.

    This is the list the UI shows instead of the in-memory run registry,
    so a sweep launched from the command line is a first-class citizen.
    """
    with connect() as c:
        rows = c.execute(
            "select config_name, vary, "
            "count(*) as runs, "
            "sum(status = 'succeeded') as succeeded, "
            "sum(status = 'failed') as failed, "
            "sum(status = 'skipped') as skipped, "
            "count(distinct dataset) as datasets, "
            "count(distinct model) as models, "
            "min(started_at) as started, "
            "max(ended_at) as ended, "
            "round(sum(wall_seconds), 1) as wall_seconds, "
            "group_concat(distinct task_type) as tasks "
            "from runs group by config_name, vary "
            "order by max(started_at) desc"
        ).fetchall()
    return [dict(r) for r in rows]


def runs(config_name: str | None = None, status: str | None = None,
         dataset: str | None = None, model: str | None = None,
         limit: int = 500, offset: int = 0) -> dict:
    """Filtered rows from the record, with a total for paging."""
    where, params = [], []
    for column, value in (("config_name", config_name), ("status", status),
                          ("dataset", dataset), ("model", model)):
        if value:
            where.append(f"{column} = ?")
            params.append(value)
    clause = f"where {' and '.join(where)}" if where else ""
    with connect() as c:
        total = c.execute(f"select count(*) from runs {clause}", params).fetchone()[0]
        rows = c.execute(
            f"select * from runs {clause} order by started_at desc limit ? offset ?",
            [*params, min(limit, 2000), max(offset, 0)],
        ).fetchall()
    return {"total": total, "rows": [dict(r) for r in rows]}


def run_detail(run_id: str) -> dict:
    """One run, every field, plus its decoded per-fold scores."""
    with connect() as c:
        row = c.execute("select * from runs where run_id = ?", (run_id,)).fetchone()
    if row is None:
        raise CatalogueError(f"no run recorded with id {run_id!r}")
    detail = dict(row)
    engine_src_on_path()
    from piplab.storage import decode_fold_scores

    detail["fold_scores"] = decode_fold_scores(detail.get("fold_scores_json"))
    return detail


def aggregate(x: str, y: str, group: str = "none",
              config_name: str | None = None,
              task_type: str | None = None,
              model: str | None = None) -> dict:
    """Mean and spread of a metric, split by one or two dimensions.

    Succeeded runs only: a skipped run has a reason, not a score, and
    averaging it in would quietly bias every series it touches.
    """
    _check(x, DIMENSIONS, "x dimension")
    _check(y, METRICS, "metric")
    if group != "none":
        _check(group, DIMENSIONS, "group dimension")

    where = [f"status = 'succeeded'", f"{y} is not null"]
    params: list = []
    for column, value in (("config_name", config_name),
                          ("task_type", task_type), ("model", model)):
        if value:
            where.append(f"{column} = ?")
            params.append(value)
    clause = " and ".join(where)
    group_sql = f"{x}, {group}" if group != "none" else x

    with connect() as c:
        rows = c.execute(
            f"select {group_sql}, count(*) as n, avg({y}) as mean, "
            f"min({y}) as low, max({y}) as high "
            f"from runs where {clause} group by {group_sql} order by {x}",
            params,
        ).fetchall()

    series: dict[str, list] = {}
    for r in rows:
        key = str(r[group]) if group != "none" else "all"
        series.setdefault(key, []).append({
            "x": str(r[x]),
            "n": r["n"],
            "mean": r["mean"],
            "low": r["low"],
            "high": r["high"],
        })

    # A metric can be entirely absent from a filtered slice: accuracy is
    # null on every regression run, for instance. Say so, rather than
    # handing back an empty object the caller has to guess about.
    empty_reason = ""
    if not series:
        empty_reason = (
            f"No succeeded run in this selection recorded a {y}. "
            f"Classification runs record accuracy and F1; regression runs "
            f"record RMSE. Pick a metric the selected runs actually "
            f"produced."
        )
    return {
        "x": x, "y": y, "group": group,
        "higher_is_better": METRICS[y],
        "series": series,
        "empty_reason": empty_reason,
    }


def dimensions() -> dict:
    """What a reader may plot, and the values actually present.

    Driven by the record rather than by a hardcoded list, so a control
    never offers a dataset or technique that was never run.
    """
    present: dict[str, list] = {}
    with connect() as c:
        for column in DIMENSIONS:
            values = [
                r[0] for r in c.execute(
                    f"select distinct {column} from runs "
                    f"where {column} is not null order by {column}"
                )
            ]
            if len(values) > 1:
                present[column] = values
        metrics = [
            m for m in METRICS
            if c.execute(
                f"select count({m}) from runs where status = 'succeeded'"
            ).fetchone()[0] > 0
        ]
    return {"dimensions": present, "metrics": metrics,
            "higher_is_better": {m: METRICS[m] for m in metrics}}


# Factors in the five-component OFAT design, and the single-sweep arm
# each one's headline sensitivity is read from. Injected-missingness
# sweeps are excluded from the sensitivity map because there the
# missingness rate is a manipulated variable rather than a property of
# the dataset, so spreads are not comparable with the other arms.
SUMMARY_ARMS = {
    "scaling": ("ofat_scaling_v2", "none"),
    "encoding": ("ofat_encoding_v2", "onehot"),
    "selection": ("ofat_selection_v2", "none"),
    "tuning": ("ofat_tuning_v3", "none"),
}


def _median(values: list[float]) -> float:
    """True median: averages the middle pair on an even count.

    Written out rather than imported from statistics so the figure here
    matches the one the analysis scripts report exactly; taking the
    lower-middle element instead shifts several cells by a few tenths.
    """
    ordered = sorted(values)
    mid = len(ordered) // 2
    if len(ordered) % 2:
        return ordered[mid]
    return (ordered[mid - 1] + ordered[mid]) / 2.0


def research_summary() -> dict:
    """Headline numbers for the research summary page.

    Everything here is computed from the record at request time, so the
    page cannot drift from the database the way a hardcoded figure
    would. Returns the programme totals, the per-factor run counts, and
    the factor-by-model sensitivity map (median spread across a
    factor's levels, as a percentage of the baseline score).

    Inputs: none.
    Output: {"totals": {...}, "factors": [...], "sensitivity": {...},
             "cost": [...]}.
    """
    with connect() as c:
        total, ok, failed, skipped = c.execute(
            "select count(*), sum(status = 'succeeded'), "
            "sum(status = 'failed'), sum(status = 'skipped') from runs"
        ).fetchone()
        datasets = c.execute("select count(distinct dataset) from runs").fetchone()[0]
        models = c.execute("select count(distinct model) from runs").fetchone()[0]
        hours = c.execute(
            "select coalesce(sum(wall_seconds), 0) / 3600.0 from runs"
        ).fetchone()[0]

        factors = []
        for factor in ("scaling", "encoding", "imputation", "selection", "tuning"):
            n = c.execute(
                "select count(*) from runs where vary = ?", (factor,)
            ).fetchone()[0]
            h = c.execute(
                "select coalesce(sum(wall_seconds), 0) / 3600.0 from runs "
                "where vary = ?", (factor,)
            ).fetchone()[0]
            factors.append({"factor": factor, "runs": n, "hours": round(h, 1)})

        # Sensitivity: median spread across levels, per factor and model.
        sensitivity: dict[str, dict[str, float]] = {}
        for factor, (config, baseline) in SUMMARY_ARMS.items():
            rows = c.execute(
                f"select dataset, model, {factor}, task_type, "
                f"accuracy_mean, rmse_mean from runs "
                f"where config_name = ? and status = 'succeeded'",
                (config,),
            ).fetchall()
            groups: dict[tuple, dict] = {}
            for dataset, model, level, task, acc, rmse in rows:
                score = rmse if task == "regression" else acc
                if score is None:
                    continue
                groups.setdefault((dataset, model), {})[level] = score
            per_model: dict[str, list[float]] = {}
            for (_dataset, model), levels in groups.items():
                base = levels.get(baseline)
                if not base or len(levels) < 2:
                    continue
                values = list(levels.values())
                spread = 100.0 * (max(values) - min(values)) / abs(base)
                per_model.setdefault(model, []).append(spread)
            sensitivity[factor] = {
                model: round(_median(v), 2)
                for model, v in per_model.items() if v
            }

    return {
        "totals": {
            "total_runs": total or 0,
            "succeeded": ok or 0,
            "failed": failed or 0,
            "skipped": skipped or 0,
            "datasets": datasets or 0,
            "models": models or 0,
            "hours": round(hours, 1),
        },
        "factors": factors,
        "sensitivity": sensitivity,
    }
