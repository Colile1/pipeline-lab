# Confirms /api/lab expands a sweep, costs it honestly, and guards
# against an accidental full-factorial.
#
# The cost estimate is the substance: the run count alone badly
# understates the work, because nested CV turns 18 runs into thousands
# of model fits. A wrong estimate here is worse than none -- it would
# either block a feasible sweep or wave through one that takes days.
import pytest
from fastapi.testclient import TestClient

from app.api.lab import FIT_REFUSAL_THRESHOLD, FIT_WARNING_THRESHOLD
from app.main import app

client = TestClient(app)

MODELS = ["logreg", "random_forest", "svm", "gradient_boosting"]


def form(**overrides) -> dict:
    base = {
        "name": "lab_api_test", "factor": "scaling",
        "techniques": ["none", "standard"],
        "datasets": ["iris", "wine"], "models": ["logreg"],
        "k": 10, "seed": 671,
    }
    base.update(overrides)
    return base


# --- choices --------------------------------------------------------------

def test_choices_returns_the_engines_own_design():
    body = client.get("/api/lab/choices").json()
    assert body["components"] == ["encoding", "imputation", "scaling", "selection", "tuning"]
    assert body["models"] == ["logreg", "random_forest", "svm", "gradient_boosting"]
    # At least the 20 Chapter 1 asks for; the registry grows over time,
    # so assert the floor rather than a literal that a correct addition
    # would break.
    assert len(body["datasets"]) >= 20
    assert {d["id"] for d in body["datasets"]} >= {"iris", "adult", "house_16H"}


def test_choices_gives_the_baseline_the_composer_prefills():
    body = client.get("/api/lab/choices").json()
    assert body["baselines"] == {
        "encoding": "onehot", "imputation": "drop_rows",
        "scaling": "none", "selection": "none", "tuning": "none",
    }
    # Every baseline is the first option, which is how the grid shows it.
    for component, baseline in body["baselines"].items():
        assert body["techniques"][component][0] == baseline


def test_choices_offers_no_mechanism_control_for_this_engine():
    """It injects no missingness, so a mechanism control would mislead."""
    assert client.get("/api/lab/choices").json()["mechanisms"] == []


# --- the cost estimate ----------------------------------------------------

def test_an_untuned_sweep_costs_runs_times_k():
    body = client.post("/api/lab/estimate", json=form()).json()
    # 2 datasets x 1 model x 2 techniques = 4 runs, each 10 folds.
    assert body["runs"] == 4
    assert body["model_fits"] == 40
    assert body["tuning"] == "none"
    assert body["inner_k"] is None


def test_the_selection_sweep_matches_the_plans_figures():
    """PLAN.md quotes 120 runs for the selection OFAT sweep."""
    body = client.post("/api/lab/estimate", json=form(
        factor="selection",
        techniques=["none", "chi2", "mutual_info", "rfe", "lasso"],
        datasets=["iris", "wine", "breast_cancer", "wdbc", "heart-c", "credit-g"],
        models=MODELS,
    )).json()
    assert body["runs"] == 120
    assert body["model_fits"] == 1200


def test_a_tuning_sweep_prices_each_level_at_its_own_cost():
    """Not at the dearest level: logreg's grid has 4 candidates, svm's 6,
    and random uses 10. Pricing everything at the dearest over-estimated
    by ~2x and would push a modest sweep past the confirmation threshold.
    """
    body = client.post("/api/lab/estimate", json=form(
        factor="tuning", techniques=["none", "random", "grid"],
        datasets=["iris", "wine", "wdbc"], models=["logreg", "svm"],
    )).json()
    assert body["runs"] == 18
    # 3 datasets x [(10+10) none + (310+310) random + (130+190) grid]
    assert body["model_fits"] == 2880
    assert body["tuning"] == "random"


def test_nested_cv_cost_is_warned_about_with_the_multiple():
    body = client.post("/api/lab/estimate", json=form(
        factor="tuning", techniques=["none", "grid"],
        datasets=["iris"], models=["logreg"],
    )).json()
    assert body["inner_k"] == 3
    assert any("Nested cross-validation" in w for w in body["warnings"])


def test_tuning_costs_far_more_than_the_same_sweep_untuned():
    shared = dict(datasets=["iris", "wine"], models=["logreg"], k=10)
    untuned = client.post("/api/lab/estimate", json=form(
        factor="scaling", techniques=["none", "standard"], **shared)).json()
    tuned = client.post("/api/lab/estimate", json=form(
        factor="tuning", techniques=["none", "grid"], **shared)).json()
    assert tuned["runs"] == untuned["runs"]          # same number of runs...
    assert tuned["model_fits"] > untuned["model_fits"] * 5   # ...far more work


def test_fits_per_run_is_reported_per_model():
    body = client.post("/api/lab/estimate", json=form(
        factor="tuning", techniques=["none", "grid"],
        datasets=["iris"], models=["logreg", "svm"])).json()
    # svm's grid is larger, so its dearest run costs more.
    assert body["fits_per_run"]["svm"] > body["fits_per_run"]["logreg"]


def test_an_encoding_sweep_warns_that_all_numeric_datasets_are_a_no_op():
    body = client.post("/api/lab/estimate", json=form(
        factor="encoding", techniques=["onehot", "ordinal"])).json()
    assert any("all-numeric" in w for w in body["warnings"])


def test_a_long_sweep_warns_with_an_estimated_duration():
    """Thresholds are grounded in measurement: ~0.1 s/fit on small
    datasets (logreg 34-43 ms, svm 27-29 ms, random_forest 231-304 ms),
    so 10,000 fits is ~17 minutes and worth saying before launching."""
    body = client.post("/api/lab/estimate", json=form(
        factor="tuning", techniques=["random"],
        datasets=["iris", "wine", "wdbc", "heart-c", "credit-g", "adult",
                  "bank-marketing", "abalone", "concrete", "house_16H"],
        models=MODELS, k=10)).json()
    assert body["model_fits"] >= FIT_WARNING_THRESHOLD
    assert body["estimated_minutes"] > 15
    assert not body["blocked"]
    assert any("model fits is roughly" in w for w in body["warnings"])


def test_a_short_sweep_carries_no_cost_warning():
    body = client.post("/api/lab/estimate", json=form(
        datasets=["iris"], models=["logreg"], k=3)).json()
    assert body["model_fits"] < FIT_WARNING_THRESHOLD
    assert not any("roughly" in w for w in body["warnings"])


def test_the_estimate_reports_a_rough_duration_not_just_a_count():
    body = client.post("/api/lab/estimate", json=form(
        factor="selection",
        techniques=["none", "chi2", "mutual_info", "rfe", "lasso"],
        datasets=["iris", "wine", "breast_cancer", "wdbc", "heart-c", "credit-g"],
        models=MODELS)).json()
    assert body["model_fits"] == 1200
    assert body["estimated_minutes"] == pytest.approx(2.0, abs=0.5)


def test_an_absurd_sweep_is_blocked_with_a_reason():
    """Above ~7 hours of estimated work, confirmation is not offered."""
    fits_needed = FIT_REFUSAL_THRESHOLD
    # 20 datasets x 4 models x 3 dear tuning levels at k=10, inner=10.
    body = client.post("/api/lab/estimate", json=form(
        factor="tuning", techniques=["random", "grid", "bayesian"],
        datasets=["iris", "wine", "wdbc", "heart-c", "credit-g", "adult",
                  "bank-marketing", "abalone", "concrete", "house_16H",
                  "digits", "sonar", "pima", "ionosphere", "colic"],
        models=MODELS, k=10, inner_k=20)).json()
    assert body["model_fits"] >= fits_needed, body["model_fits"]
    assert body["blocked"]
    assert "exceeds the" in body["blocked_reason"]


def test_the_estimate_reports_which_component_varies():
    body = client.post("/api/lab/estimate", json=form(factor="selection",
                                                      techniques=["none", "rfe"])).json()
    assert body["varied_component"] == "selection"
    assert body["is_ofat"] is True


def test_an_invalid_form_is_a_422_with_the_specific_reason():
    response = client.post("/api/lab/estimate", json=form(models=["xgboost"]))
    assert response.status_code == 422
    assert "xgboost" in response.json()["detail"]


def test_a_factor_this_engine_cannot_vary_is_refused():
    response = client.post("/api/lab/estimate", json=form(factor="bogus"))
    assert response.status_code == 422


# --- launching ------------------------------------------------------------

def test_a_small_sweep_launches_and_returns_its_estimate(tmp_path, monkeypatch):
    from app.core import runner as runner_module

    monkeypatch.setattr(runner_module, "RUNS_DIR", tmp_path / "runs")
    response = client.post("/api/lab/runs", json=form(
        techniques=["none", "standard"], datasets=["iris"], models=["logreg"], k=3))
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["engine"] == "lab"
    assert body["run_id"]
    assert body["estimate"]["runs"] == 2
    assert body["estimate"]["model_fits"] == 6


def test_a_long_sweep_needs_explicit_confirmation(tmp_path, monkeypatch):
    from app.core import runner as runner_module

    monkeypatch.setattr(runner_module, "RUNS_DIR", tmp_path / "runs")
    payload = form(
        factor="tuning", techniques=["random"],
        datasets=["iris", "wine", "wdbc", "heart-c", "credit-g", "adult",
                  "bank-marketing", "abalone", "concrete", "house_16H"],
        models=MODELS, k=10)
    response = client.post("/api/lab/runs", json=payload)
    assert response.status_code == 409
    assert "confirm_cost=true" in response.json()["detail"]
    # The refusal must state the cost, not just refuse.
    assert "model fits" in response.json()["detail"]


def test_a_blocked_sweep_cannot_be_confirmed_past(tmp_path, monkeypatch):
    """Above the refusal threshold, confirm_cost must not help."""
    from app.core import runner as runner_module

    monkeypatch.setattr(runner_module, "RUNS_DIR", tmp_path / "runs")
    payload = form(
        factor="tuning", techniques=["random", "grid", "bayesian"],
        datasets=["iris", "wine", "wdbc", "heart-c", "credit-g", "adult",
                  "bank-marketing", "abalone", "concrete", "house_16H",
                  "digits", "sonar", "pima", "ionosphere", "colic"],
        models=MODELS, k=10, inner_k=20, confirm_cost=True)
    response = client.post("/api/lab/runs", json=payload)
    assert response.status_code == 409
    assert "exceeds the" in response.json()["detail"]


def test_launch_rejects_an_invalid_form_before_costing_it(tmp_path, monkeypatch):
    from app.core import runner as runner_module

    monkeypatch.setattr(runner_module, "RUNS_DIR", tmp_path / "runs")
    response = client.post("/api/lab/runs", json=form(models=["xgboost"]))
    assert response.status_code == 422


def test_inner_k_actually_reaches_the_estimate():
    """Regression guard: /estimate passed the whole form to
    normalise_form, which rejects unknown fields, so supplying inner_k
    returned 422 and the parameter was silently dead at its default."""
    shared = dict(factor="tuning", techniques=["grid"],
                  datasets=["iris"], models=["logreg"], k=10)
    low = client.post("/api/lab/estimate", json=form(inner_k=3, **shared))
    high = client.post("/api/lab/estimate", json=form(inner_k=9, **shared))
    assert low.status_code == 200, low.text
    assert high.status_code == 200, high.text
    assert high.json()["model_fits"] > low.json()["model_fits"]
    assert high.json()["inner_k"] == 9


def test_costing_a_sweep_needs_none_of_the_engines_dependencies():
    """Regression guard for a bug the step-13 fresh-install check caught.

    The composer costs a sweep from the dashboard's OWN interpreter,
    which deliberately does not have sklearn, pandas or optuna. The
    estimate originally imported `piplab.components.tuning`, which
    imports sklearn at module level, so every /estimate call failed with
    ModuleNotFoundError on a fresh dashboard install -- while passing
    here, because this machine happened to have sklearn.

    The arithmetic now lives in `piplab.components.budgets`, which
    imports nothing. This asserts that stays true.
    """
    import ast
    from pathlib import Path

    from app.engines.lab import REPO_ROOT

    source = (REPO_ROOT / "src" / "piplab" / "components" / "budgets.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    imported = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module.split(".")[0])
    assert imported == set(), f"budgets.py must import nothing; found {sorted(imported)}"


def test_the_estimate_route_does_not_import_the_sklearn_backed_module():
    """The same guard, from the caller's side."""
    from pathlib import Path

    import app.api.lab as lab_module

    source = Path(lab_module.__file__).read_text(encoding="utf-8")
    assert "from piplab.components import budgets" in source
    assert "import tuning" not in source, (
        "costing must not import components.tuning: it pulls in sklearn"
    )
