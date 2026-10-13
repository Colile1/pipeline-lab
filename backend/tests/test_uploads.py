# Confirms POST /api/datasets/upload registers a CSV in each engine's own
# records with characteristics matching hand-computed values, and that the
# engine's own loader reads it back - per docs/build-order.md step 6.
import csv
import subprocess

import pandas as pd
import pytest
from fastapi.testclient import TestClient

from app.core.errors import UploadValidationError
from app.engines.b2 import B2Engine
from app.engines.prepfx import PrepfxEngine
from app.engines.registration import engine_python
from app.main import app
from app.uploads.validate import check_dataset_id, infer_task, validate_csv

client = TestClient(app)

# 6 rows; b == 2*a so |r| = 1; one blank cell in a (1 of 18 feature cells);
# one text feature; balanced binary target. Every value below is hand-computed.
TOY_CSV = "a,b,cat,label\n,2,x,0\n2,4,y,1\n3,6,x,0\n4,8,y,1\n5,10,x,0\n6,12,y,1\n"
# Same features with a continuous target, for the regression path.
TOY_REGRESSION_CSV = "a,b,cat,price\n,2,x,1.5\n2,4,y,2.25\n3,6,x,3.5\n4,8,y,4.75\n5,10,x,5.5\n6,12,y,6.25\n"


def _upload(engine, dataset_id, content=TOY_CSV, target="label", **extra):
    """POST one CSV to the upload route and return the response."""
    return client.post(
        "/api/datasets/upload",
        files={"file": ("toy.csv", content, "text/csv")},
        data={"engine": engine, "dataset_id": dataset_id, "target": target, **extra},
    )


def _run_in_engine(engine, code):
    """Run a snippet under the engine's own interpreter; return its stdout."""
    proc = subprocess.run(
        [engine_python(engine.root_path), "-c", code],
        capture_output=True, text=True, cwd=engine.root_path,
    )
    assert proc.returncode == 0, proc.stderr
    return proc.stdout.strip()


def test_prepfx_upload_registers_spec_with_hand_computed_profile():
    response = _upload("prepfx", "toy-upload")
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["task"] == "classification"
    assert body["task_inferred"] is True
    assert body["registered"] == {
        "id": "toy-upload", "source": "local", "ref": "toy.csv",
        "task": "classification", "target": "label",
        "licence": "user upload (experiment-dashboard)",
    }
    assert body["characteristics"] == {
        "dataset_id": "toy-upload", "task": "classification",
        "n_rows": 6, "n_features": 3, "n_numeric": 2, "n_categorical": 1,
        "mean_abs_correlation": 1.0, "missing_proportion": 0.055556,
        "missing_mechanism": "none", "class_balance": 1.0,
    }
    engine = PrepfxEngine()
    with engine.user_datasets_path.open(newline="", encoding="utf-8") as fh:
        assert list(csv.DictReader(fh)) == [body["registered"]]
    assert (engine.cache_dir / "toy-upload.parquet").is_file()


def test_prepfx_own_loader_reads_the_upload_back():
    assert _upload("prepfx", "toy-upload").status_code == 200
    engine = PrepfxEngine()
    out = _run_in_engine(engine, (
        "import sys; sys.path.insert(0, 'src')\n"
        "from prepfx.datasets.registry import load_user_datasets\n"
        "from prepfx.datasets.fetch import fetch, load_xy\n"
        f"spec = load_user_datasets(r'{engine.user_datasets_path}')['toy-upload']\n"
        f"X, y = load_xy(spec, fetch(spec, r'{engine.cache_dir}'))\n"
        "print(X.shape[0], X.shape[1], y.name, sorted(y.unique().tolist()))"
    ))
    assert out == "6 3 label [0, 1]"


def test_b2_upload_registers_row_with_hand_computed_characteristics():
    response = _upload("b2", "toy-upload", domain="testing")
    assert response.status_code == 200, response.text
    body = response.json()
    # var(a) over [2..6] = 2.5, var(b) = 14, log10(14 / 2.5) = 0.748 -> 0.75.
    expected = {
        "dataset": "toy-upload", "task_type": "classification", "domain": "testing",
        "openml_id": None, "n_rows": 6, "n_features": 3, "n_numeric": 2,
        "n_categorical": 1, "missing_pct": 5.56, "n_classes": 2,
        "imbalance_ratio": 1.0, "var_ratio_log10": 0.75, "mean_abs_corr": 1.0,
    }
    assert body["characteristics"] == expected
    assert body["registered"] == {**expected, "target_col": "label"}
    engine = B2Engine()
    with engine.user_datasets_path.open(newline="", encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))
    assert len(rows) == 1
    assert rows[0]["dataset"] == "toy-upload" and rows[0]["missing_pct"] == "5.56"
    assert (engine.datasets_dir / "cache" / "toy-upload" / "X.parquet").is_file()
    assert (engine.datasets_dir / "cache" / "toy-upload" / "y.parquet").is_file()


def test_b2_own_loader_reads_the_upload_back():
    assert _upload("b2", "toy-upload").status_code == 200
    engine = B2Engine()
    out = _run_in_engine(engine, (
        "import sys; sys.path.insert(0, 'src')\n"
        "from pathlib import Path\n"
        "from research_impact_of_preprocess.data import loaders, registry\n"
        f"registry.USER_CATALOGUE_PATH = Path(r'{engine.user_datasets_path}')\n"
        f"loaders._DATASETS_DIR = Path(r'{engine.datasets_dir}')\n"
        "X, y, md = loaders.load_dataset('toy-upload')\n"
        "print(X.shape[0], X.shape[1], md['meta'].task_type, md['feature_types']['cat'])"
    ))
    assert out == "6 3 classification categorical"


def test_b2_regression_upload_leaves_class_columns_blank():
    response = _upload("b2", "toy-reg", content=TOY_REGRESSION_CSV, target="price")
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["task"] == "regression"
    assert body["characteristics"]["n_classes"] is None
    assert body["characteristics"]["imbalance_ratio"] is None
    assert body["characteristics"]["var_ratio_log10"] == 0.75


def test_uploads_appear_after_each_engines_design_datasets():
    assert _upload("prepfx", "toy-upload").status_code == 200
    assert _upload("b2", "toy-upload").status_code == 200
    prepfx_rows = client.get("/api/datasets", params={"engine": "prepfx"}).json()
    assert len(prepfx_rows) == 25
    assert prepfx_rows[-1]["id"] == "toy-upload" and prepfx_rows[-1]["source"] == "local"
    b2_rows = client.get("/api/datasets", params={"engine": "b2"}).json()
    assert len(b2_rows) == 13
    assert b2_rows[-1]["dataset"] == "toy-upload" and b2_rows[-1]["openml_id"] is None
    assert set(b2_rows[-1]) == set(b2_rows[0])


@pytest.mark.parametrize("engine,taken", [("prepfx", "iris"), ("prepfx", "adult"), ("b2", "wdbc")])
def test_upload_rejects_a_name_the_engine_already_has(engine, taken):
    response = _upload(engine, taken)
    assert response.status_code == 422
    assert "already registered" in response.json()["detail"]


@pytest.mark.parametrize("engine", ["prepfx", "b2"])
def test_upload_rejects_the_same_name_twice(engine):
    assert _upload(engine, "toy-upload").status_code == 200
    assert _upload(engine, "toy-upload").status_code == 422


def test_upload_reports_engine_refusal_and_registers_nothing(isolated_user_datasets):
    engine = PrepfxEngine()
    engine.cache_dir.mkdir(parents=True)
    (engine.cache_dir / "toy-upload.parquet").write_bytes(b"stale")
    response = _upload("prepfx", "toy-upload")
    assert response.status_code == 500
    assert "cached file already exists" in response.json()["detail"]
    assert not engine.user_datasets_path.exists()
    assert (engine.cache_dir / "toy-upload.parquet").read_bytes() == b"stale"


def test_upload_rejects_unknown_engine_and_clears_staging(isolated_user_datasets):
    assert _upload("b3", "toy-upload").status_code == 400
    assert _upload("b2", "toy-upload", target="nope").status_code == 422
    assert _upload("b2", "toy-upload").status_code == 200
    assert list((isolated_user_datasets / "staging").iterdir()) == []


@pytest.mark.parametrize("content,target,fragment", [
    (TOY_CSV, "missing", "is not in the CSV"),
    ("a,b,label\n1,,0\n2,,1\n", "label", "no values at all: b"),
    ("a,label\n1,0\n2,\n3,1\n", "label", "1 missing value(s)"),
    ("a,label\n1,0\n2,0\n", "label", "only one distinct value"),
    ("label\n0\n1\n", "label", "no feature columns"),
    ("cat,label\nx,0\ny,1\n", "label", "no numeric feature columns"),
    ("a,a,label\n1,2,0\n3,4,1\n", "label", "duplicate column names: a"),
    ("a,label\n1,0\n2,0\n3,1\n", "label", "class with only one row"),
    ("a,label\n", "label", "no data rows"),
])
def test_validate_csv_rejects_with_a_specific_reason(tmp_path, content, target, fragment):
    path = tmp_path / "bad.csv"
    path.write_text(content, encoding="utf-8")
    with pytest.raises(UploadValidationError, match=fragment.replace("(", r"\(").replace(")", r"\)")):
        validate_csv(path, target)


def test_validate_csv_rejects_text_target_for_regression(tmp_path):
    path = tmp_path / "toy.csv"
    path.write_text("a,label\n1,p\n2,q\n3,p\n4,q\n", encoding="utf-8")
    with pytest.raises(UploadValidationError, match="cannot be a regression target"):
        validate_csv(path, "label", "regression")
    with pytest.raises(UploadValidationError, match="Unknown task type"):
        validate_csv(path, "label", "clustering")


def test_validate_csv_warns_on_a_small_class(tmp_path):
    path = tmp_path / "toy.csv"
    path.write_text(TOY_CSV, encoding="utf-8")
    result = validate_csv(path, "label")
    assert result.task == "classification" and result.task_inferred
    assert result.warnings == (
        "Smallest class has 3 rows; cross-validation with more than 3 folds will fail on this dataset.",
    )
    assert validate_csv(path, "label", "classification").task_inferred is False


def test_infer_task_rules():
    assert infer_task(pd.Series(["p", "q", "p"])) == "classification"
    assert infer_task(pd.Series([True, False, True])) == "classification"
    assert infer_task(pd.Series([0, 1, 2, 1])) == "classification"
    assert infer_task(pd.Series([1.0, 2.0, 1.0])) == "classification"
    assert infer_task(pd.Series([1.5, 2.0, 3.25])) == "regression"
    assert infer_task(pd.Series(range(21))) == "regression"
    assert infer_task(pd.Series(range(20))) == "classification"


@pytest.mark.parametrize("bad", ["A", "a", "Has Space", "-lead", "x" * 41, "../up"])
def test_check_dataset_id_rejects_malformed_names(bad):
    with pytest.raises(UploadValidationError, match="is not valid"):
        check_dataset_id(bad, set())
