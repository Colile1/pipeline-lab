# The research summary page: one page covering the whole project.
#
# The thing worth guarding is that the page's numbers come from the
# record rather than being typed into the template, because a hardcoded
# figure here would silently go stale as soon as another sweep lands.
import pytest
from fastapi.testclient import TestClient

from app.core import catalogue
from app.main import app

client = TestClient(app)

record_exists = pytest.mark.skipif(
    not catalogue.db_path().exists(),
    reason="no lab.db yet; run a sweep first",
)


def test_the_page_renders_and_loads_its_script():
    response = client.get("/summary")
    assert response.status_code == 200
    assert "summary.js" in response.text
    assert client.get("/static/js/summary.js").status_code == 200


def test_the_page_is_reachable_from_the_navigation():
    """A page nothing links to is a page nobody finds."""
    assert 'href="/summary"' in client.get("/dashboard").text


@pytest.mark.parametrize("figure", [
    "fig1_effects_by_factor.png",
    "fig2_scaling_by_model.png",
    "fig4_droprows_artefact.png",
    "fig5_tuning_cost_benefit.png",
    "fig6_protocol_agreement.png",
    "fig9_selection_tail_risk.png",
])
def test_every_figure_the_page_references_is_served(figure):
    """A broken image is invisible in a template test but obvious to a
    reader, so each one is fetched rather than assumed present."""
    assert figure in client.get("/summary").text
    assert client.get(f"/static/figures/{figure}").status_code == 200


@record_exists
def test_the_summary_api_reports_the_real_record():
    data = client.get("/api/analysis/summary").json()
    totals = data["totals"]
    assert totals["total_runs"] > 0
    assert (totals["succeeded"] + totals["failed"] + totals["skipped"]
            == totals["total_runs"])
    assert totals["datasets"] > 0
    assert totals["hours"] >= 0


@record_exists
def test_the_sensitivity_map_covers_the_four_factors():
    data = client.get("/api/analysis/summary").json()
    assert set(data["sensitivity"]) == {"scaling", "encoding",
                                        "selection", "tuning"}
    # Encoding is the known-zero row: the median dataset in this registry
    # has no categorical features, so the three encoders are no-ops. If
    # this ever becomes non-zero the registry changed, not the code.
    assert all(v == 0.0 for v in data["sensitivity"]["encoding"].values())


@record_exists
def test_scaling_sensitivity_separates_linear_models_from_trees():
    """The page's headline claim, asserted against the record.

    Non-vacuous: it would fail if the spread calculation collapsed to a
    constant, which is the realistic way this could silently break.
    """
    scaling = client.get("/api/analysis/summary").json()["sensitivity"]["scaling"]
    assert scaling["svm"] > scaling["random_forest"]
    assert scaling["svm"] > scaling["gradient_boosting"]
    assert scaling["gradient_boosting"] < 0.5


@record_exists
def test_the_page_hardcodes_no_count_the_api_could_supply():
    """Numbers are fetched at render time, not written into the HTML.

    The run total is the one most likely to be pasted in by hand and the
    most certain to go stale, so the template must not contain it.
    """
    totals = client.get("/api/analysis/summary").json()["totals"]
    page = client.get("/summary").text
    assert str(totals["total_runs"]) not in page
    assert f"{totals['total_runs']:,}" not in page
