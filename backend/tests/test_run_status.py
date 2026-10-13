# Confirms run_status reports a real smoke run as succeeded and a
# deliberately-broken config as failed (never silently successful), per
# docs/build-order.md step 8's "Done when".
import time

import pytest

from app.core import run_status
from app.core.config_builder import build_config_dict
from app.core.run_status import (
    FAILED, RUNNING, SUCCEEDED, UNKNOWN, summarise_validation,
)
from app.core.runner import start_run
from app.engines.b2 import B2Engine
from app.engines.prepfx import PrepfxEngine

# Matches tests/test_runner.py: b2's smoke config has taken ~6m40s on a
# memory-constrained machine; prepfx's is much smaller.
TIMEOUT_SECONDS = 900

PREPFX_SMOKE_FORM = {
    "name": "status_smoke", "factor": "scaling",
    "techniques": ["standard", "minmax", "robust", "none"],
    "datasets": ["iris", "wine"],
    "models": ["logistic"], "k": 3, "seed": 20260702,
}
PREPFX_IMPUTATION_FORM = {
    "name": "status_imputation", "factor": "imputation",
    "techniques": ["mean", "median", "knn"],
    "datasets": ["iris", "wine"],
    "models": ["logistic"], "k": 3, "seed": 20260702,
    "missingness_rates": [0.15], "missingness_mechanisms": ["mcar"],
}


def _run_to_completion(engine, form):
    """Launch a form through the real engine and wait for it to exit."""
    config = build_config_dict(engine, form)
    handle = start_run(engine, config, form["name"])
    deadline = time.monotonic() + TIMEOUT_SECONDS
    while time.monotonic() < deadline:
        if handle.poll() is not None:
            return handle, config
        time.sleep(0.5)
    handle.process.kill()
    pytest.fail(f"run {handle.run_id} did not exit within {TIMEOUT_SECONDS}s")


# --- real successful run ----------------------------------------------------

def test_prepfx_smoke_run_is_reported_as_succeeded():
    engine = PrepfxEngine()
    handle, config = _run_to_completion(engine, PREPFX_SMOKE_FORM)
    summary = summarise_validation(handle, engine, config)

    assert summary.state == SUCCEEDED, summary.notes + summary.errors
    assert summary.exit_code == 0
    assert summary.success_marker_seen
    assert summary.errors == []
    # prepfx's grid = datasets x levels x models (run_experiment.py::run),
    # so 2 datasets x 4 scaling levels x 1 model = 8 configurations, and
    # progress is counted in "Dataset done:" lines, so 2.
    assert summary.expected == 8
    assert summary.reported_total == 8
    assert summary.completed == 2
    assert summary.outputs, "a successful prepfx run must have written output files"


def test_prepfx_imputation_run_compares_achieved_missingness_to_requested():
    engine = PrepfxEngine()
    handle, config = _run_to_completion(engine, PREPFX_IMPUTATION_FORM)
    summary = summarise_validation(handle, engine, config)

    assert summary.state == SUCCEEDED, summary.notes + summary.errors
    assert summary.missingness is not None, "prepfx records achieved missingness"
    assert summary.missingness["requested"] == 0.15
    assert summary.missingness["mechanism"] == ["mcar"]
    achieved = summary.missingness["achieved"]
    assert {a["dataset"] for a in achieved} == {"iris", "wine"}
    # Count-based injection lands within rounding of the request.
    for entry in achieved:
        assert abs(entry["proportion"] - 0.15) < 0.01, entry


# --- real broken run --------------------------------------------------------

def test_a_broken_config_is_reported_as_failed_not_successful():
    engine = PrepfxEngine()
    broken = dict(PREPFX_SMOKE_FORM, datasets=["no_such_dataset_exists"])
    handle, config = _run_to_completion(engine, broken)
    summary = summarise_validation(handle, engine, config)

    assert summary.state == FAILED
    assert summary.exit_code != 0
    assert not summary.success_marker_seen
    assert summary.errors, "the engine's own error text must be reported"
    assert summary.completed == 0


# --- state machine, against synthetic logs ---------------------------------

class _FakeProcess:
    def __init__(self, code):
        self._code = code

    def poll(self):
        return self._code


class _FakeHandle:
    def __init__(self, tmp_path, log_text, code, output_dir=None):
        self.run_id = "fake"
        self.engine_name = "prepfx"
        self.config_path = tmp_path / "config.yaml"
        self.run_dir = tmp_path
        self.log_path = tmp_path / "run.log"
        self.log_path.write_text(log_text, encoding="utf-8")
        self.output_dir = output_dir
        self.process = _FakeProcess(code)

    def poll(self):
        return self.process.poll()


SUCCESS_LOG = """Arm: scaling
Grid configurations: 4
CV folds: 3
Total fold fits: 12
Dataset done: iris (classification)
Dataset done: wine (classification)
Configurations evaluated: 4
Outputs written under: C:\\somewhere
"""


def test_zero_exit_without_the_success_marker_is_failed():
    # The crux of step 8: a clean exit code alone must never be read as
    # success, or a run killed mid-way looks fine.
    truncated = "Arm: scaling\nGrid configurations: 4\nDataset done: iris (classification)\n"
    handle = _FakeHandle(pytest_tmp(), truncated, 0)
    summary = summarise_validation(handle, PrepfxEngine(), {})
    assert summary.state == FAILED
    assert summary.completed == 1
    assert summary.expected == 4
    assert any("planned" in note for note in summary.notes)


def test_a_traceback_fails_a_run_even_with_a_zero_exit_code():
    log = SUCCESS_LOG + "Traceback (most recent call last):\nValueError: boom\n"
    handle = _FakeHandle(pytest_tmp(), log, 0)
    summary = summarise_validation(handle, PrepfxEngine(), {})
    assert summary.state == FAILED
    assert "Traceback (most recent call last):" in summary.errors
    assert "ValueError: boom" in summary.errors


def test_a_tracking_warning_does_not_fail_an_otherwise_good_run():
    log = SUCCESS_LOG.replace(
        "Dataset done: iris",
        "Tracking warning: could not start experiment: no server\nDataset done: iris",
    )
    handle = _FakeHandle(pytest_tmp(), log, 0)
    summary = summarise_validation(handle, PrepfxEngine(), {})
    assert summary.state == SUCCEEDED
    assert summary.warnings and "Tracking warning" in summary.warnings[0]
    assert summary.errors == []


def test_a_still_running_process_is_reported_as_running():
    handle = _FakeHandle(pytest_tmp(), "Arm: scaling\nGrid configurations: 4\n", None)
    summary = summarise_validation(handle, PrepfxEngine(), {})
    assert summary.state == RUNNING


def test_an_unreadable_log_is_unknown_not_successful():
    tmp = pytest_tmp()
    handle = _FakeHandle(tmp, "", 0)
    handle.log_path.unlink()
    summary = summarise_validation(handle, PrepfxEngine(), {})
    assert summary.state == UNKNOWN
    assert summary.notes


def test_success_marker_with_a_short_total_is_noted():
    log = SUCCESS_LOG.replace("Configurations evaluated: 4", "Configurations evaluated: 3")
    handle = _FakeHandle(pytest_tmp(), log, 0)
    summary = summarise_validation(handle, PrepfxEngine(), {})
    assert summary.reported_total == 3
    assert summary.expected == 4
    assert any("did not finish" in note for note in summary.notes)


def test_b2_never_claims_a_measured_missingness_rate():
    engine = B2Engine()
    config = {
        "experiment": "x", "factor": "imputer", "techniques": ["mean"],
        "datasets": ["wdbc"], "models": ["logreg"], "k": 10, "seed": 671,
        "missingness_rates": [0.15], "missingness_mechanisms": ["mcar"],
    }
    log = "Experiment: x\nFactor: imputer\nCombinations: 1\nRun complete: a\nCompleted: 1 runs logged to MLflow experiment 'x'\n"
    handle = _FakeHandle(pytest_tmp(), log, 0)
    handle.engine_name = "b2"
    summary = summarise_validation(handle, engine, config)
    assert summary.state == SUCCEEDED
    assert summary.missingness is None
    assert any("does not record" in note for note in summary.notes)


def test_get_status_is_unknown_for_an_untracked_run():
    assert run_status.get_status("no-such-run") == UNKNOWN


# pytest's tmp_path is a fixture; these synthetic tests need a directory
# without taking it as an argument in every signature.
_TMP_COUNTER = {"n": 0}
_TMP_ROOT = {"path": None}


@pytest.fixture(autouse=True)
def _capture_tmp_root(tmp_path):
    _TMP_ROOT["path"] = tmp_path
    yield


def pytest_tmp():
    """Return a fresh subdirectory of the current test's tmp_path."""
    _TMP_COUNTER["n"] += 1
    path = _TMP_ROOT["path"] / f"case{_TMP_COUNTER['n']}"
    path.mkdir(parents=True, exist_ok=True)
    return path
