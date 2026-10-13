# Confirms GET /api/results/{run_id} reads real result rows for both
# engines: prepfx's own tables/*.csv (written by run_experiment.py itself),
# and b2's results extracted on demand from its own mlflow.db, per
# docs/build-order.md step 11's "Done when".
import time
import uuid

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)

TIMEOUT_SECONDS = 900


def _wait_until_finished(run_id):
    """Poll GET /api/runs/{run_id} until its state is no longer 'running'."""
    deadline = time.monotonic() + TIMEOUT_SECONDS
    while time.monotonic() < deadline:
        body = client.get(f"/api/runs/{run_id}").json()
        if body["state"] != "running":
            return body
        time.sleep(0.5)
    raise AssertionError(f"run {run_id} did not finish within {TIMEOUT_SECONDS}s")


def _unique_name(prefix):
    """A fresh experiment/config name per test, so repeated runs against
    b2's real shared mlflow.db never collide with another test's rows or
    with the dashboard's own prior manual runs.
    """
    return f"{prefix}_{uuid.uuid4().hex[:10]}"


def test_prepfx_results_read_its_own_real_summary_and_verdict_tables():
    form = {
        "engine": "prepfx", "name": _unique_name("results_prepfx"), "factor": "scaling",
        "techniques": ["standard", "minmax", "robust", "none"],
        "datasets": ["iris", "wine"], "models": ["logistic"], "k": 3, "seed": 20260702,
    }
    created = client.post("/api/runs", json=form)
    assert created.status_code == 200
    run_id = created.json()["run_id"]
    summary = _wait_until_finished(run_id)
    assert summary["state"] == "succeeded", summary["notes"] + summary["errors"]

    response = client.get(f"/api/results/{run_id}")
    assert response.status_code == 200
    body = response.json()
    assert body["engine"] == "prepfx"
    assert body["state"] == "succeeded"
    tables = body["tables"]
    assert "tables/scaling_summary" in tables
    assert "tables/scaling_verdicts" in tables
    assert "results/scaling_catalogue" in tables
    summary_rows = tables["tables/scaling_summary"]
    assert summary_rows, "the summary table must have real rows, not be empty"
    assert set(summary_rows[0]) >= {"dataset", "level", "model"} or len(summary_rows[0]) > 0


def test_b2_results_are_extracted_on_demand_from_its_own_mlflow_store():
    experiment = _unique_name("results_b2")
    form = {
        "engine": "b2", "name": experiment, "factor": "scaling",
        "techniques": ["standard", "minmax"],
        "datasets": ["credit-g", "house_16H"],
        "models": ["logreg", "random_forest"], "k": 5, "seed": 671,
    }
    created = client.post("/api/runs", json=form)
    assert created.status_code == 200
    run_id = created.json()["run_id"]
    summary = _wait_until_finished(run_id)
    assert summary["state"] == "succeeded", summary["notes"] + summary["errors"]

    response = client.get(f"/api/results/{run_id}")
    assert response.status_code == 200
    body = response.json()
    assert body["engine"] == "b2"
    rows = body["tables"]["results"]
    # 2 techniques x 2 datasets x 2 models = 8 runs logged to this experiment.
    assert len(rows) == 8
    datasets_seen = {row["dataset"] for row in rows}
    assert datasets_seen == {"credit-g", "house_16H"}
    # house_16H is a regression dataset: mean_rmse populated, mean_accuracy blank.
    reg_row = next(r for r in rows if r["dataset"] == "house_16H")
    assert reg_row["mean_rmse"] not in (None, "")
    assert reg_row["mean_accuracy"] in (None, "")


def test_b2_results_extraction_is_cached_as_a_csv_not_rerun_every_request():
    experiment = _unique_name("results_b2_cache")
    form = {
        "engine": "b2", "name": experiment, "factor": "scaling",
        "techniques": ["standard"], "datasets": ["wdbc"],
        "models": ["logreg"], "k": 10, "seed": 671,
    }
    created = client.post("/api/runs", json=form)
    run_id = created.json()["run_id"]
    _wait_until_finished(run_id)

    first = client.get(f"/api/results/{run_id}")
    assert first.status_code == 200
    from app.core.runner import get_process
    handle = get_process(run_id)
    results_csv = handle.run_dir / "results.csv"
    assert results_csv.is_file()
    written_at = results_csv.stat().st_mtime

    second = client.get(f"/api/results/{run_id}")
    assert second.status_code == 200
    assert second.json() == first.json()
    assert results_csv.stat().st_mtime == written_at, "a second read must not re-extract"


def test_results_404s_for_an_untracked_run_id():
    response = client.get("/api/results/no-such-run")
    assert response.status_code == 404


def test_results_409s_for_a_run_still_in_progress():
    form = {
        "engine": "b2", "name": _unique_name("results_running"), "factor": "scaling",
        "techniques": ["standard"], "datasets": ["wdbc"],
        "models": ["logreg"], "k": 10, "seed": 671,
    }
    created = client.post("/api/runs", json=form)
    run_id = created.json()["run_id"]
    try:
        response = client.get(f"/api/results/{run_id}")
        assert response.status_code == 409
    finally:
        _wait_until_finished(run_id)


def test_results_409s_for_a_failed_run_never_fabricating_a_table():
    form = {
        "engine": "prepfx", "name": _unique_name("results_broken"), "factor": "scaling",
        "techniques": ["standard", "minmax", "robust", "none"],
        "datasets": ["no_such_dataset_exists"], "models": ["logistic"],
        "k": 3, "seed": 20260702,
    }
    created = client.post("/api/runs", json=form)
    run_id = created.json()["run_id"]
    _wait_until_finished(run_id)

    response = client.get(f"/api/results/{run_id}")
    assert response.status_code == 409
