# Confirms GET /api/datasets returns each engine's real catalogue rows,
# per docs/build-order.md step 5's "Done when".
from fastapi.testclient import TestClient

from app.engines.b2 import B2Engine
from app.engines.prepfx import PrepfxEngine
from app.main import app

client = TestClient(app)


def test_b2_datasets_match_the_real_catalogue_csv():
    response = client.get("/api/datasets", params={"engine": "b2"})
    assert response.status_code == 200
    body = response.json()
    expected = B2Engine().list_datasets()
    assert body == expected
    assert len(body) == 12
    wdbc = next(row for row in body if row["dataset"] == "wdbc")
    assert wdbc["task_type"] == "classification"
    assert wdbc["n_rows"] == 569
    assert wdbc["n_classes"] == 2


def test_b2_datasets_use_none_not_nan_for_blank_cells():
    response = client.get("/api/datasets", params={"engine": "b2"})
    abalone = next(row for row in response.json() if row["dataset"] == "abalone")
    assert abalone["task_type"] == "regression"
    assert abalone["n_classes"] is None
    assert abalone["imbalance_ratio"] is None


def test_prepfx_datasets_match_the_real_registry():
    response = client.get("/api/datasets", params={"engine": "prepfx"})
    assert response.status_code == 200
    body = response.json()
    expected = PrepfxEngine().list_datasets()
    assert body == expected
    assert len(body) == 24
    iris = next(row for row in body if row["id"] == "iris")
    assert iris["source"] == "sklearn"
    assert iris["task"] == "classification"


def test_prepfx_datasets_excludes_optional_large_and_monster_sets():
    response = client.get("/api/datasets", params={"engine": "prepfx"})
    ids = {row["id"] for row in response.json()}
    assert "adult" not in ids
    assert "magic" not in ids


def test_unknown_engine_is_a_specific_400_not_a_500():
    response = client.get("/api/datasets", params={"engine": "bogus"})
    assert response.status_code == 400
    assert "bogus" in response.json()["detail"]


def test_missing_engine_param_is_a_422():
    response = client.get("/api/datasets")
    assert response.status_code == 422
