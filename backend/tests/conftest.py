# Keeps every test away from the two research repos' real user-dataset files
# and real outputs/: upload and run paths point at a per-test temporary
# directory instead.
import pytest

from app.api import datasets as datasets_api
from app.core import runner as runner_module
from app.engines.b2 import B2Engine
from app.engines.prepfx import PrepfxEngine


@pytest.fixture(autouse=True)
def isolated_user_datasets(tmp_path, monkeypatch):
    """Redirect user-dataset records, caches, upload staging and run output to tmp_path.

    Inputs: pytest's tmp_path and monkeypatch fixtures.
    Output: tmp_path, for tests that inspect what registration or a run wrote.
    """
    monkeypatch.setattr(PrepfxEngine, "user_datasets_path", tmp_path / "prepfx" / "user_datasets.csv")
    monkeypatch.setattr(PrepfxEngine, "cache_dir", tmp_path / "prepfx" / "raw")
    monkeypatch.setattr(B2Engine, "user_datasets_path", tmp_path / "b2" / "user_catalogue.csv")
    monkeypatch.setattr(B2Engine, "datasets_dir", tmp_path / "b2")
    monkeypatch.setattr(datasets_api, "STAGING_DIR", tmp_path / "staging")
    monkeypatch.setattr(runner_module, "RUNS_DIR", tmp_path / "runs")
    monkeypatch.setattr(runner_module, "_PROCESSES", {})
    return tmp_path
