# Confirms POST /api/runs launches a real engine run, GET /api/runs/{id}
# returns its validation summary, and GET /api/runs/{id}/log tails the log,
# per docs/build-order.md step 10's "Done when".
import time

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)

TIMEOUT_SECONDS = 900

PREPFX_SMOKE_FORM = {
    "engine": "prepfx", "name": "runs_api_smoke", "factor": "scaling",
    "techniques": ["standard", "minmax", "robust", "none"],
    "datasets": ["iris", "wine"],
    "models": ["logistic"], "k": 3, "seed": 20260702,
}


def _wait_until_finished(run_id):
    """Poll GET /api/runs/{run_id} until its state is no longer 'running'."""
    deadline = time.monotonic() + TIMEOUT_SECONDS
    while time.monotonic() < deadline:
        body = client.get(f"/api/runs/{run_id}").json()
        if body["state"] != "running":
            return body
        time.sleep(0.5)
    raise AssertionError(f"run {run_id} did not finish within {TIMEOUT_SECONDS}s")


def test_post_runs_rejects_a_missing_engine_field():
    form = dict(PREPFX_SMOKE_FORM)
    del form["engine"]
    response = client.post("/api/runs", json=form)
    assert response.status_code == 400


def test_post_runs_rejects_an_unknown_engine():
    response = client.post("/api/runs", json=dict(PREPFX_SMOKE_FORM, engine="bogus"))
    assert response.status_code == 400


def test_post_runs_surfaces_a_specific_422_for_an_invalid_combo():
    response = client.post("/api/runs", json=dict(PREPFX_SMOKE_FORM, models=["logreg"]))
    assert response.status_code == 422
    assert "logreg" in response.json()["detail"]


def test_get_run_404s_for_an_unknown_run_id():
    response = client.get("/api/runs/no-such-run")
    assert response.status_code == 404


def test_get_run_log_404s_for_an_unknown_run_id():
    response = client.get("/api/runs/no-such-run/log")
    assert response.status_code == 404


def test_get_run_log_rejects_a_negative_offset():
    # A real run-id isn't needed: the offset check runs before the lookup
    # would matter, but use a real launch so a 404 can't mask a 400.
    created = client.post("/api/runs", json=PREPFX_SMOKE_FORM)
    assert created.status_code == 200
    run_id = created.json()["run_id"]
    try:
        response = client.get(f"/api/runs/{run_id}/log", params={"offset": -1})
        assert response.status_code == 400
    finally:
        _wait_until_finished(run_id)


def test_full_round_trip_launch_poll_log_for_a_real_prepfx_smoke_run():
    created = client.post("/api/runs", json=PREPFX_SMOKE_FORM)
    assert created.status_code == 200
    body = created.json()
    run_id = body["run_id"]
    assert body["engine"] == "prepfx"
    assert body["config_path"]
    assert body["log_path"]

    summary = _wait_until_finished(run_id)
    assert summary["state"] == "succeeded", summary["notes"] + summary["errors"]
    assert summary["run_id"] == run_id
    assert summary["engine"] == "prepfx"
    assert summary["success_marker_seen"]
    assert summary["errors"] == []
    assert summary["outputs"], "a successful run must report its output files"

    log_response = client.get(f"/api/runs/{run_id}/log")
    assert log_response.status_code == 200
    log_body = log_response.json()
    assert "Grid configurations:" in log_body["text"]
    assert log_body["offset"] > 0

    # A second read from the returned offset gets nothing new (the run has
    # already finished and the whole log was already read).
    tail_response = client.get(f"/api/runs/{run_id}/log", params={"offset": log_body["offset"]})
    assert tail_response.json()["text"] == ""


def test_a_broken_config_round_trips_as_a_failed_run_via_the_api():
    broken = dict(PREPFX_SMOKE_FORM, datasets=["no_such_dataset_exists"])
    created = client.post("/api/runs", json=broken)
    assert created.status_code == 200
    run_id = created.json()["run_id"]

    summary = _wait_until_finished(run_id)
    assert summary["state"] == "failed"
    assert summary["errors"]
    assert not summary["success_marker_seen"]


def test_get_runs_lists_a_just_launched_run():
    created = client.post("/api/runs", json=PREPFX_SMOKE_FORM)
    assert created.status_code == 200
    run_id = created.json()["run_id"]
    try:
        listing = client.get("/api/runs")
        assert listing.status_code == 200
        rows = listing.json()
        matching = [r for r in rows if r["run_id"] == run_id]
        assert len(matching) == 1
        assert matching[0]["engine"] == "prepfx"
        assert matching[0]["state"] in ("running", "succeeded")
    finally:
        _wait_until_finished(run_id)


def test_get_runs_lists_newest_first():
    first = client.post("/api/runs", json=PREPFX_SMOKE_FORM).json()["run_id"]
    _wait_until_finished(first)
    second = client.post("/api/runs", json=PREPFX_SMOKE_FORM).json()["run_id"]
    _wait_until_finished(second)
    rows = client.get("/api/runs").json()
    ids = [r["run_id"] for r in rows]
    assert ids.index(second) < ids.index(first)
