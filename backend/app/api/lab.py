# /api/lab - sweep expansion, cost estimate and batch launch for the
# Pipeline Lab engine.
#
# The cost estimate is the substance of this module. On this machine a
# full-factorial sweep is ~65,280 runs and simply not runnable, while an
# OFAT sweep is ~100-300. Worse, the run count alone understates the
# cost: nested CV turns 18 runs into 540 model fits. So the composer is
# given BOTH numbers before anything launches, plus a guard against an
# accidental full-factorial.
from fastapi import APIRouter, HTTPException

from ..core.config_builder import build_config_dict
from ..core.errors import ConfigValidationError, RunLaunchError
from ..core.form_schema import normalise_form, supported_factors
from ..core.runner import start_run
from ..engines.registry import get_engine

router = APIRouter(prefix="/api/lab", tags=["lab"])

# Measured on this machine, small datasets, k=10 (2026-10-10):
#   logreg ~34-43 ms/fit, svm ~27-29 ms/fit, random_forest ~231-304 ms/fit
# So ~100 ms/fit is a fair average across the four models, and large
# datasets (adult is 48,842 rows) are far slower again. This is used
# only to turn a fit count into a rough minutes figure, which is more
# use to a reader than a bare number.
SECONDS_PER_FIT_ESTIMATE = 0.1
# Above ~15 minutes of estimated work, say so before launching.
FIT_WARNING_THRESHOLD = 10_000
# Above ~7 hours, refuse: this is not an interactive sweep any more.
FIT_REFUSAL_THRESHOLD = 250_000


def _lab():
    """Return the lab adapter, or a 400 if it is not available."""
    return get_engine("lab")


@router.get("/choices")
def lab_choices() -> dict:
    """Return everything the composer needs to build its grid.

    Inputs: none.
    Output: the five OFAT components with their technique lists
    (baseline first), the four models, the registered datasets, and the
    baseline map the composer pre-fills its first column with. All read
    from the engine itself, so the UI cannot drift from what will run.
    """
    engine = _lab()
    return {
        "components": list(engine.factors),
        "techniques": {c: engine.fixed_techniques(c) for c in engine.factors},
        "baselines": engine.baselines(),
        "models": engine.fixed_models(),
        "datasets": engine.list_datasets(),
        # This engine injects no missingness, so the wizard must not
        # offer a mechanism control for it.
        "mechanisms": engine.valid_mechanisms(),
    }


@router.post("/estimate")
def estimate_sweep(form: dict) -> dict:
    """Cost a sweep without running it.

    Inputs: form - the wizard payload (same shape as POST /api/runs,
    minus "engine"): name, factor, techniques, datasets, models, k, seed.
    Output: dict with "runs", "model_fits", "fits_per_run" (per model),
    "is_ofat", "warnings" and "blocked". `model_fits` is the number that
    actually predicts wall-clock, because nested CV multiplies it.
    Raises: HTTPException 422 with the specific reason if the form is
    invalid.
    """
    engine = _lab()
    # `inner_k` and `confirm_cost` are API-level knobs, not wizard
    # fields, and normalise_form rejects anything it does not know. They
    # must be stripped here exactly as POST /runs strips them, or
    # supplying inner_k would 422 and the parameter would be dead.
    payload = {k: v for k, v in form.items()
               if k not in ("engine", "confirm_cost", "inner_k")}
    try:
        wizard = normalise_form(engine, payload)
    except ConfigValidationError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return _estimate(engine, wizard, form)


def _estimate(engine, wizard, form: dict) -> dict:
    """Compute the cost breakdown for a validated form."""
    import sys

    sys.path.insert(0, str(engine.root_path / "src"))
    # budgets.py deliberately imports nothing, so the dashboard can cost
    # a sweep without the engine's dependencies. Importing
    # components.tuning here instead pulls in sklearn and breaks a fresh
    # dashboard install -- caught by the step-13 fresh-environment check.
    from piplab.components import budgets as engine_budgets

    runs = len(wizard.datasets) * len(wizard.models) * len(wizard.techniques)
    inner_k = int(form.get("inner_k", 3))

    # Cost differs per model AND per tuning level: logreg's grid has 4
    # candidates, svm's 6, and random/bayesian use 10. When the sweep
    # varies tuning, each level runs at its OWN cost, so the total is a
    # sum over (technique, model) rather than the dearest level times
    # everything -- which over-estimated by ~2x and would have pushed a
    # modest sweep past the confirmation threshold for nothing.
    if wizard.factor == "tuning":
        level_for = {technique: technique for technique in wizard.techniques}
    else:
        level_for = {technique: "none" for technique in wizard.techniques}

    per_model: dict[str, int] = {}
    fits = 0
    for technique in wizard.techniques:
        level = level_for[technique]
        for model in wizard.models:
            cost = engine_budgets.fits_per_run(level, model, wizard.k, inner_k)
            fits += len(wizard.datasets) * cost
            # Report the dearest per-model figure, so the UI can show
            # what the most expensive single run will cost.
            per_model[model] = max(per_model.get(model, 0), cost)
    tuning_level = _tuning_level(wizard)

    warnings = []
    if tuning_level != "none":
        baseline_fits = len(wizard.datasets) * len(wizard.techniques) * wizard.k * len(wizard.models)
        warnings.append(
            f"Nested cross-validation: {fits:,} model fits for {runs:,} runs "
            f"({fits / max(baseline_fits, 1):.0f}x an untuned sweep), because each outer "
            f"fold runs an inner {inner_k}-fold search."
        )
    if wizard.factor == "encoding":
        warnings.append(
            "Encoding only varies on datasets with categorical features; on an "
            "all-numeric dataset every level builds an identical pipeline and the "
            "result is a guaranteed null. Checking which of these datasets qualify "
            "requires loading them, so it is not done in this estimate."
        )
    if fits >= FIT_WARNING_THRESHOLD:
        warnings.append(
            f"{fits:,} model fits is roughly {_minutes(fits)} on this machine, measured "
            "at ~0.1 s/fit on small datasets. Large datasets (adult is 48,842 rows) are "
            "much slower, and this machine has shown heavy paging under memory pressure, "
            "so treat that as a floor."
        )

    return {
        "runs": runs,
        "model_fits": fits,
        "estimated_minutes": round(fits * SECONDS_PER_FIT_ESTIMATE / 60.0, 1),
        "fits_per_run": per_model,
        "tuning": tuning_level,
        "inner_k": inner_k if tuning_level != "none" else None,
        "cv_k": wizard.k,
        "is_ofat": True,  # the form varies exactly one component by construction
        "varied_component": wizard.factor,
        "warnings": warnings,
        "blocked": fits >= FIT_REFUSAL_THRESHOLD,
        "blocked_reason": (
            f"{fits:,} model fits (roughly {_minutes(fits)}) exceeds the "
            f"{FIT_REFUSAL_THRESHOLD:,} limit for an interactive sweep. Reduce the "
            "datasets, models or techniques, or run the engine's CLI directly if this "
            "is genuinely intended."
            if fits >= FIT_REFUSAL_THRESHOLD else ""
        ),
    }


def _minutes(fits: int) -> str:
    """Render a fit count as a rough human duration.

    Inputs: fits - the model-fit count.
    Output: e.g. "25 minutes" or "3.2 hours". Deliberately coarse: the
    per-fit figure is measured on small datasets and varies by an order
    of magnitude across models, so false precision would mislead.
    """
    minutes = fits * SECONDS_PER_FIT_ESTIMATE / 60.0
    if minutes < 90:
        return f"{minutes:.0f} minutes"
    return f"{minutes / 60.0:.1f} hours"


def _tuning_level(wizard) -> str:
    """Return the dearest tuning level in this sweep, for reporting.

    Used only as a label and to decide whether the nested-CV warning
    applies; the cost itself is summed per level in _estimate().
    """
    if wizard.factor != "tuning":
        return "none"
    order = {"none": 0, "grid": 1, "random": 2, "bayesian": 2}
    return max(wizard.techniques, key=lambda level: order.get(level, 0))


@router.post("/runs")
def launch_sweep(form: dict) -> dict:
    """Launch one sweep, after costing it.

    Inputs: form - the wizard payload, plus optional "confirm_cost":
    true to proceed past the warning threshold.
    Output: dict with "run_id", "estimate" and the run's paths.
    Raises: HTTPException 422 for an invalid form, 409 when the sweep is
    above the refusal threshold or needs confirmation it has not been
    given, 500 if the engine could not be started.
    """
    engine = _lab()
    payload = {k: v for k, v in form.items() if k not in ("engine", "confirm_cost", "inner_k")}
    try:
        wizard = normalise_form(engine, payload)
    except ConfigValidationError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    estimate = _estimate(engine, wizard, form)
    if estimate["blocked"]:
        raise HTTPException(status_code=409, detail=estimate["blocked_reason"])
    if estimate["model_fits"] >= FIT_WARNING_THRESHOLD and not form.get("confirm_cost"):
        raise HTTPException(
            status_code=409,
            detail=(
                f"This sweep is {estimate['runs']:,} runs and {estimate['model_fits']:,} "
                f"model fits, roughly {_minutes(estimate['model_fits'])}. "
                "Resend with confirm_cost=true to proceed."
            ),
        )

    try:
        config = build_config_dict(engine, payload)
    except ConfigValidationError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    try:
        handle = start_run(engine, config, wizard.name)
    except RunLaunchError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    return {
        "run_id": handle.run_id,
        "engine": handle.engine_name,
        "config_path": str(handle.config_path),
        "log_path": str(handle.log_path),
        "estimate": estimate,
    }


@router.get("/record/{run_id}")
def lab_record(run_id: str) -> dict:
    """Return the recorded rows for one launched sweep.

    Inputs: run_id - the id returned by POST /api/lab/runs.
    Output: dict with "rows" (every recorded run) and "columns" (the
    schema's column notes, so the UI can explain a field rather than
    making the reader guess what `peak_rss_method` means).
    Raises: HTTPException 404 when the run is untracked or wrote no
    record yet.
    """
    from ..core.runner import get_process

    handle = get_process(run_id)
    if handle is None:
        raise HTTPException(status_code=404, detail=f"No run tracked with id '{run_id}'.")
    engine = _lab()
    db_path = engine.extract_results(handle.run_dir, handle.config)
    if db_path is None:
        raise HTTPException(
            status_code=404,
            detail="This run has not written its record yet. It may still be starting.",
        )
    import sys

    sys.path.insert(0, str(engine.root_path / "src"))
    from piplab.storage import column_notes

    return {"rows": engine.read_run_rows(db_path), "columns": column_notes()}


@router.get("/network/{run_id}")
def lab_network(run_id: str, metric: str = "accuracy_mean") -> dict:
    """Return the layered pipeline graph for one sweep.

    Each component is a layer and each technique a node; an edge joins
    consecutive layers along the path a run actually took. Node colour
    comes from the mean metric of runs through it, edge weight from how
    many runs took that path -- so the graph shows which paths were
    explored and which won, from recorded data only.

    Inputs: run_id; metric - which recorded column to colour by.
    Output: {"layers": [...], "nodes": [...], "edges": [...], "metric"}.
    Raises: HTTPException 404 as for /record, 400 for an unknown metric.
    """
    record = lab_record(run_id)
    rows = [r for r in record["rows"] if r.get("status") == "succeeded"]
    if metric not in record["columns"] and rows and metric not in rows[0]:
        raise HTTPException(status_code=400, detail=f"Unknown metric column '{metric}'.")

    engine = _lab()
    layers = list(engine.factors) + ["model"]

    nodes: dict[tuple[str, str], dict] = {}
    edges: dict[tuple[str, str, str, str], int] = {}
    for row in rows:
        path = [(layer, row.get(layer)) for layer in layers if row.get(layer)]
        for layer, technique in path:
            key = (layer, technique)
            entry = nodes.setdefault(key, {"layer": layer, "technique": technique,
                                           "runs": 0, "values": []})
            entry["runs"] += 1
            value = row.get(metric)
            if isinstance(value, (int, float)):
                entry["values"].append(float(value))
        for (layer_a, tech_a), (layer_b, tech_b) in zip(path, path[1:]):
            edge_key = (layer_a, tech_a, layer_b, tech_b)
            edges[edge_key] = edges.get(edge_key, 0) + 1

    node_list = []
    for (layer, technique), entry in nodes.items():
        values = entry.pop("values")
        entry["mean"] = round(sum(values) / len(values), 6) if values else None
        node_list.append(entry)
    best = max((n for n in node_list if n["mean"] is not None),
               key=lambda n: n["mean"], default=None)

    return {
        "layers": layers,
        "metric": metric,
        "nodes": sorted(node_list, key=lambda n: (layers.index(n["layer"]), n["technique"])),
        "edges": [
            {"from_layer": a, "from": ta, "to_layer": b, "to": tb, "runs": count}
            for (a, ta, b, tb), count in edges.items()
        ],
        "best_node": best,
        "n_runs": len(rows),
    }


@router.get("/trends/{run_id}")
def lab_trends(run_id: str, x: str = "scaling", y: str = "accuracy_mean",
               group: str = "model") -> dict:
    """Aggregate a sweep's record into a trend series.

    Aggregation happens here rather than in the browser so the UI never
    has to hold every row, and so the numbers shown are the same ones a
    direct SQL query would give.

    Inputs: run_id; x - the column to group along; y - the metric to
    average; group - a second grouping column ("none" for a single
    series).
    Output: {"series": {group: [{x, mean, sd_mean, n}]}, ...}.
    Raises: HTTPException 404 as for /record, 400 for an unknown column.
    """
    record = lab_record(run_id)
    rows = [r for r in record["rows"] if r.get("status") == "succeeded"]
    if not rows:
        return {"series": {}, "x": x, "y": y, "group": group, "n_runs": 0}

    available = set(rows[0])
    for column, label in ((x, "x"), (y, "y")):
        if column not in available:
            raise HTTPException(status_code=400, detail=f"Unknown {label} column '{column}'.")
    if group != "none" and group not in available:
        raise HTTPException(status_code=400, detail=f"Unknown group column '{group}'.")

    buckets: dict[str, dict[str, list[float]]] = {}
    for row in rows:
        value = row.get(y)
        if not isinstance(value, (int, float)):
            continue
        series = str(row.get(group)) if group != "none" else "all"
        buckets.setdefault(series, {}).setdefault(str(row.get(x)), []).append(float(value))

    series = {
        name: [
            {"x": key, "mean": round(sum(values) / len(values), 6), "n": len(values)}
            for key, values in sorted(points.items())
        ]
        for name, points in sorted(buckets.items())
    }
    return {"series": series, "x": x, "y": y, "group": group, "n_runs": len(rows)}
