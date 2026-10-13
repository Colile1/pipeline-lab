# Confirms the analysis API and its pages: the endpoints the Dashboard,
# Findings, Explorer and Guide read, and the auto-refresh pulse.
import pytest
from fastapi.testclient import TestClient

from app.core import catalogue
from app.main import app

client = TestClient(app)

record_exists = pytest.mark.skipif(
    not catalogue.db_path().exists(),
    reason="no lab.db yet; run a sweep first",
)


@pytest.mark.parametrize("path,script", [
    ("/dashboard", "dashboard.js"),
    ("/findings", "findings.js"),
    ("/explorer", "explorer.js"),
])
def test_each_analysis_page_renders_and_loads_its_script(path, script):
    response = client.get(path)
    assert response.status_code == 200
    assert script in response.text
    assert "analysis-common.js" in response.text
    assert client.get(f"/static/js/{script}").status_code == 200


def test_the_guide_is_server_rendered_prose():
    """The guide must be readable even if every script fails: it is the
    page a confused reader lands on. Its content is therefore in the
    HTML itself, and it loads no page script of its own.
    """
    import re

    response = client.get("/guide")
    assert response.status_code == 200
    scripts = re.findall(r'<script[^>]*src="([^"]+)"', response.text)
    assert all(src.endswith("common.js") for src in scripts), scripts
    for word in ("Scaling", "Leakage", "p-value", "glossary",
                 "Cross-validation", "Baseline"):
        assert word.lower() in response.text.lower()


def test_the_guide_explains_the_power_trap_in_plain_words():
    """The single most misreadable result in this project: a test that
    could not have found anything is not evidence of no effect."""
    text = client.get("/guide").text
    assert "could not tell" in text.lower()
    assert "six datasets" in text.lower() or "6 datasets" in text.lower()


def test_every_page_offers_the_guide():
    """Help has to be reachable from wherever the reader is."""
    for path in ("/dashboard", "/findings", "/explorer", "/compose"):
        assert 'href="/guide"' in client.get(path).text


def test_the_pulse_endpoint_answers_even_with_no_record():
    """Auto-refresh must not break on a fresh install."""
    body = client.get("/api/analysis/pulse").json()
    assert set(body) >= {"exists", "mtime", "total_runs", "running"}


@record_exists
def test_the_pulse_reports_the_real_row_count():
    body = client.get("/api/analysis/pulse").json()
    assert body["exists"]
    assert body["total_runs"] == catalogue.overview()["total_runs"]


@record_exists
def test_the_overview_endpoint_matches_the_catalogue():
    body = client.get("/api/analysis/overview").json()
    assert body["total_runs"] == catalogue.overview()["total_runs"]


@record_exists
def test_sweeps_are_listed_without_having_been_launched_here():
    """The whole point: CLI-launched sweeps are visible.

    conftest resets the in-memory run registry for every test, so if
    this endpoint depended on it the list would always be empty.
    """
    body = client.get("/api/analysis/sweeps").json()
    assert body["sweeps"]
    assert all(s["runs"] > 0 for s in body["sweeps"])


@record_exists
def test_aggregate_returns_plottable_series():
    body = client.get(
        "/api/analysis/aggregate?x=scaling&y=accuracy_mean&group=model").json()
    assert body["series"]
    for points in body["series"].values():
        assert all({"x", "mean", "n"} <= set(p) for p in points)


def test_aggregate_refuses_an_unknown_column():
    assert client.get("/api/analysis/aggregate?x=bogus").status_code == 400
    assert client.get("/api/analysis/aggregate?y=bogus").status_code == 400


def test_aggregate_refuses_an_injection_attempt():
    """Column names reach SQL, so a rejected name must 400, not execute."""
    response = client.get(
        "/api/analysis/aggregate?x=scaling;drop%20table%20runs")
    assert response.status_code == 400


@record_exists
def test_the_dimensions_endpoint_only_offers_what_was_run():
    body = client.get("/api/analysis/dimensions").json()
    assert "scaling" in body["dimensions"]
    assert body["metrics"]
    assert set(body["higher_is_better"]) == set(body["metrics"])


@record_exists
def test_a_run_can_be_fetched_by_its_recorded_id():
    rows = client.get("/api/analysis/runs?limit=1").json()["rows"]
    run_id = rows[0]["run_id"]
    body = client.get(f"/api/analysis/run/{run_id}").json()
    assert body["run_id"] == run_id
    assert "fold_scores" in body


def test_an_unknown_run_id_is_a_404():
    assert client.get("/api/analysis/run/not-a-real-id").status_code == 404


@record_exists
def test_findings_report_the_same_result_the_engine_does():
    """The UI must not contradict the written research."""
    body = client.get(
        "/api/analysis/findings?config_name=ofat_scaling_full").json()
    if not body["available"]:
        pytest.skip(body["reason"])
    logreg = [
        f for f in body["findings"]
        if f["model"] == "logreg" and f["metric"] == "accuracy_mean"
    ]
    assert logreg, "the logreg accuracy finding should be present"
    finding = logreg[0]
    assert finding["friedman"]["significant"]
    assert finding["n_datasets"] == 11
    rejected = [c for c in finding["comparisons"] if c["rejected"]]
    assert [c["level"] for c in rejected] == ["standard"]


@record_exists
def test_every_finding_carries_a_power_verdict():
    """A result that cannot be significant must never read as a null."""
    body = client.get(
        "/api/analysis/findings?config_name=ofat_scaling_regression").json()
    if not body["available"]:
        pytest.skip(body["reason"])
    for finding in body["findings"]:
        if finding["friedman"]["significant"]:
            power = finding["power"]
            assert set(power) >= {
                "underpowered", "wilcoxon_floor", "holm_bar", "datasets_needed"
            }


@record_exists
def test_export_returns_rows_and_their_column_notes():
    body = client.get(
        "/api/analysis/export?config_name=ofat_scaling_full").json()
    assert body["rows"]
    assert body["columns"]
    # The notes exist so the UI can explain a field rather than making
    # the reader guess what peak_rss_method means.
    assert "peak_rss_method" in body["columns"]


def test_the_original_pages_still_render():
    """The analysis pages are additive; nothing earlier may break."""
    for path in ("/", "/datasets", "/experiment", "/runs", "/results",
                 "/compose", "/network", "/trends"):
        assert client.get(path).status_code == 200
