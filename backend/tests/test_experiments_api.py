# Confirms POST /api/experiments round-trips a wizard payload into a real
# generated YAML path, and GET choices matches the engine's fixed lists,
# per docs/build-order.md step 9's "Done when".
import yaml
from fastapi.testclient import TestClient

from app.engines.b2 import B2Engine
from app.engines.prepfx import PrepfxEngine
from app.main import app

client = TestClient(app)

B2_SCALING_FORM = {
    "engine": "b2", "name": "api test scaling", "factor": "scaling",
    "techniques": ["standard", "minmax"],
    "datasets": ["credit-g", "house_16H"],
    "models": ["logreg", "random_forest"], "k": 5, "seed": 671,
}
PREPFX_SCALING_FORM = {
    "engine": "prepfx", "name": "api test prepfx", "factor": "scaling",
    "techniques": ["standard", "minmax", "robust", "none"],
    "datasets": ["iris", "wine"],
    "models": ["logistic"], "k": 3, "seed": 20260702,
}


def _isolate_configs_dir(monkeypatch, tmp_path):
    """Redirect both engines' configs_dir so API tests never touch the
    real preprocessing-effects-framework/configs or
    Artefact/Research_Impact_of_Preprocess/configs directories.
    """
    monkeypatch.setattr(PrepfxEngine, "configs_dir", tmp_path / "prepfx")
    monkeypatch.setattr(B2Engine, "configs_dir", tmp_path / "b2")


def test_get_choices_matches_b2s_fixed_lists():
    response = client.get("/api/experiments/choices", params={"engine": "b2", "factor": "scaling"})
    assert response.status_code == 200
    body = response.json()
    engine = B2Engine()
    assert body == {
        "techniques": engine.fixed_techniques("scaling"),
        "models": engine.fixed_models(),
        "mechanisms": engine.valid_mechanisms(),
    }
    assert "logreg" in body["models"]


def test_get_choices_matches_prepfxs_fixed_lists():
    response = client.get("/api/experiments/choices", params={"engine": "prepfx", "factor": "imputation"})
    assert response.status_code == 200
    body = response.json()
    engine = PrepfxEngine()
    assert body == {
        "techniques": engine.fixed_techniques("imputation"),
        "models": engine.fixed_models(),
        "mechanisms": engine.valid_mechanisms(),
    }
    # prepfx's model key, never b2's "logreg" (the two engines differ).
    assert "logistic" in body["models"]
    assert "logreg" not in body["models"]


def test_get_choices_rejects_an_unknown_engine():
    response = client.get("/api/experiments/choices", params={"engine": "bogus", "factor": "scaling"})
    assert response.status_code == 400


def test_get_choices_rejects_an_unknown_factor():
    response = client.get("/api/experiments/choices", params={"engine": "b2", "factor": "bogus"})
    assert response.status_code == 400


def test_post_experiment_round_trips_a_b2_form_to_a_real_config_path(monkeypatch, tmp_path):
    _isolate_configs_dir(monkeypatch, tmp_path)
    response = client.post("/api/experiments", json=B2_SCALING_FORM)
    assert response.status_code == 200
    body = response.json()
    assert body["engine"] == "b2"
    written = yaml.safe_load(open(body["config_path"], encoding="utf-8"))
    assert written["factor"] == "scaler"
    assert written["techniques"] == ["standard", "minmax"]
    assert written["experiment"] == "api test scaling"


def test_post_experiment_round_trips_a_prepfx_form_using_its_own_field_names(monkeypatch, tmp_path):
    _isolate_configs_dir(monkeypatch, tmp_path)
    response = client.post("/api/experiments", json=PREPFX_SCALING_FORM)
    assert response.status_code == 200
    body = response.json()
    written = yaml.safe_load(open(body["config_path"], encoding="utf-8"))
    assert written["arm"] == "scaling"
    assert "factor" not in written and "techniques" not in written


def test_post_experiment_rejects_a_missing_engine_field(monkeypatch, tmp_path):
    _isolate_configs_dir(monkeypatch, tmp_path)
    form = dict(B2_SCALING_FORM)
    del form["engine"]
    response = client.post("/api/experiments", json=form)
    assert response.status_code == 400


def test_post_experiment_rejects_an_unknown_engine(monkeypatch, tmp_path):
    _isolate_configs_dir(monkeypatch, tmp_path)
    form = dict(B2_SCALING_FORM, engine="bogus")
    response = client.post("/api/experiments", json=form)
    assert response.status_code == 400


def test_post_experiment_surfaces_a_specific_422_for_an_invalid_combo(monkeypatch, tmp_path):
    _isolate_configs_dir(monkeypatch, tmp_path)
    form = dict(B2_SCALING_FORM, models=["xgboost"])
    response = client.post("/api/experiments", json=form)
    assert response.status_code == 422
    assert "xgboost" in response.json()["detail"]


def test_post_experiment_twice_with_the_same_name_is_a_409(monkeypatch, tmp_path):
    _isolate_configs_dir(monkeypatch, tmp_path)
    first = client.post("/api/experiments", json=B2_SCALING_FORM)
    assert first.status_code == 200
    second = client.post("/api/experiments", json=B2_SCALING_FORM)
    assert second.status_code == 409
    assert "already exists" in second.json()["detail"]
