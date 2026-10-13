# Confirms the three Pipeline Lab pages render, reference their scripts,
# and that the network/trends endpoints aggregate real recorded runs.
import time

import pytest
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


@pytest.mark.parametrize("path,script", [
    ("/compose", "compose.js"),
    ("/network", "network.js"),
    ("/trends", "trends.js"),
])
def test_each_lab_page_renders_and_loads_its_script(path, script):
    response = client.get(path)
    assert response.status_code == 200
    assert script in response.text
    assert client.get(f"/static/js/{script}").status_code == 200


def test_the_original_pages_still_render():
    """The lab tabs are additive; the first build's pages must survive."""
    for path in ("/", "/datasets", "/experiment", "/runs", "/results"):
        assert client.get(path).status_code == 200


def test_the_nav_offers_the_lab_tabs():
    body = client.get("/compose").text
    for href in ("/compose", "/network", "/trends"):
        assert f'href="{href}"' in body


@pytest.fixture
def completed_sweep():
    """Launch one tiny real sweep and wait for it, for the data endpoints.

    Function-scoped deliberately: conftest.py has an autouse,
    function-scoped fixture that repoints RUNS_DIR and resets
    runner._PROCESSES, so a module-scoped launch would be wiped from the
    registry before the tests that use it ever run (and every data
    endpoint would 404). The cost is one real sweep per test, which is
    seconds at this size.
    """
    created = client.post("/api/lab/runs", json={
        "name": "pages_fixture", "factor": "scaling",
        "techniques": ["none", "standard"],
        "datasets": ["iris"], "models": ["logreg"], "k": 3, "seed": 671,
    })
    assert created.status_code == 200, created.text
    run_id = created.json()["run_id"]
    deadline = time.monotonic() + 300
    while time.monotonic() < deadline:
        if client.get(f"/api/runs/{run_id}").json()["state"] != "running":
            break
        time.sleep(0.5)
    return run_id


def test_the_record_endpoint_returns_rows_and_column_notes(completed_sweep):
    body = client.get(f"/api/lab/record/{completed_sweep}").json()
    assert len(body["rows"]) == 2
    assert body["rows"][0]["status"] == "succeeded"
    # Notes let the UI explain a field rather than making the reader guess.
    assert "peak_rss_method" in body["columns"]


def test_the_network_endpoint_builds_a_layered_graph(completed_sweep):
    body = client.get(f"/api/lab/network/{completed_sweep}").json()
    assert body["layers"] == ["encoding", "imputation", "scaling",
                              "selection", "tuning", "model"]
    assert body["n_runs"] == 2
    scaling_nodes = {n["technique"] for n in body["nodes"] if n["layer"] == "scaling"}
    assert scaling_nodes == {"none", "standard"}
    # Edges join consecutive layers along paths runs actually took.
    assert body["edges"]
    assert all(edge["runs"] >= 1 for edge in body["edges"])


def test_every_network_node_reports_how_many_runs_went_through_it(completed_sweep):
    body = client.get(f"/api/lab/network/{completed_sweep}").json()
    # The baseline components are shared by both runs; each scaling
    # level is taken by one. That is what edge weight means.
    by_key = {(n["layer"], n["technique"]): n for n in body["nodes"]}
    assert by_key[("encoding", "onehot")]["runs"] == 2
    assert by_key[("scaling", "none")]["runs"] == 1
    assert by_key[("scaling", "standard")]["runs"] == 1


def test_the_network_identifies_the_best_node_from_recorded_scores(completed_sweep):
    body = client.get(f"/api/lab/network/{completed_sweep}").json()
    assert body["best_node"] is not None
    assert body["best_node"]["mean"] is not None


def test_an_unknown_metric_is_refused(completed_sweep):
    response = client.get(f"/api/lab/network/{completed_sweep}?metric=roc_auc")
    assert response.status_code == 400


def test_the_trends_endpoint_aggregates_by_x_and_group(completed_sweep):
    body = client.get(
        f"/api/lab/trends/{completed_sweep}?x=scaling&y=accuracy_mean&group=model").json()
    assert body["n_runs"] == 2
    assert "logreg" in body["series"]
    points = {p["x"]: p for p in body["series"]["logreg"]}
    assert set(points) == {"none", "standard"}
    assert all(0.0 <= p["mean"] <= 1.0 for p in points.values())


def test_trends_can_plot_cost_against_the_same_axis(completed_sweep):
    """The view the resource capture exists for: was it worth the compute?"""
    body = client.get(
        f"/api/lab/trends/{completed_sweep}?x=scaling&y=wall_seconds&group=none").json()
    points = {p["x"]: p["mean"] for p in body["series"]["all"]}
    assert set(points) == {"none", "standard"}
    assert all(value > 0 for value in points.values())


def test_trends_aggregation_matches_a_direct_read_of_the_record(completed_sweep):
    """The plotted number must be the same one the record holds."""
    rows = client.get(f"/api/lab/record/{completed_sweep}").json()["rows"]
    expected = {
        row["scaling"]: row["accuracy_mean"]
        for row in rows if row["status"] == "succeeded"
    }
    body = client.get(
        f"/api/lab/trends/{completed_sweep}?x=scaling&y=accuracy_mean&group=none").json()
    plotted = {p["x"]: p["mean"] for p in body["series"]["all"]}
    assert plotted == pytest.approx(expected)


def test_trends_refuses_an_unknown_column(completed_sweep):
    assert client.get(f"/api/lab/trends/{completed_sweep}?x=bogus").status_code == 400
    assert client.get(f"/api/lab/trends/{completed_sweep}?y=bogus").status_code == 400


def test_the_data_endpoints_404_for_an_untracked_run():
    for path in ("record", "network", "trends"):
        assert client.get(f"/api/lab/{path}/no-such-run").status_code == 404
