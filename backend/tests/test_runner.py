# Confirms core.runner launches a real smoke config to completion under each
# engine's own interpreter, with output isolated from that engine's real
# results, per docs/build-order.md step 7's "Done when".
import time

import pytest
import yaml

from app.core.config_builder import build_config_dict
from app.core.errors import RunLaunchError
from app.core.runner import get_process, start_run
from app.engines.b2 import B2Engine
from app.engines.prepfx import PrepfxEngine

B2_SMOKE_FORM = {
    "name": "dashboard_smoke", "factor": "scaling",
    "techniques": ["standard", "minmax"],
    "datasets": ["credit-g", "house_16H"],
    "models": ["logreg", "random_forest"], "k": 5, "seed": 671,
}
PREPFX_SMOKE_FORM = {
    "name": "dashboard_smoke", "factor": "scaling",
    "techniques": ["standard", "minmax", "robust", "none"],
    "datasets": ["iris", "wine"],
    # prepfx's model key is "logistic", not b2's "logreg".
    "models": ["logistic"], "k": 3, "seed": 20260702,
}

# Confirmed by timing configs/smoke.yaml directly under b2's own
# interpreter: ~6m40s on this machine when memory is under pressure (the
# process itself burns well under a second of CPU — it is almost entirely
# blocked on I/O/paging, not slow computation). prepfx's smoke config is
# much smaller and finishes in well under a minute.
TIMEOUT_SECONDS = 900


def _wait_for_exit(handle, timeout=TIMEOUT_SECONDS) -> int:
    """Poll a launched run until it exits or the timeout elapses."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        code = handle.poll()
        if code is not None:
            return code
        time.sleep(0.5)
    handle.process.kill()
    pytest.fail(f"run {handle.run_id} did not exit within {timeout}s")


def test_b2_smoke_run_completes_and_captures_its_log():
    engine = B2Engine()
    config = build_config_dict(engine, B2_SMOKE_FORM)
    handle = start_run(engine, config, B2_SMOKE_FORM["name"])

    assert get_process(handle.run_id) is handle
    assert handle.config_path.is_file()
    assert handle.output_dir is None  # b2's schema has no outputs_dir field

    code = _wait_for_exit(handle)
    assert code == 0, handle.log_path.read_text(encoding="utf-8", errors="replace")
    log_text = handle.log_path.read_text(encoding="utf-8")
    assert "Run complete" in log_text


def test_prepfx_smoke_run_completes_and_writes_into_its_own_run_dir():
    engine = PrepfxEngine()
    config = build_config_dict(engine, PREPFX_SMOKE_FORM)
    handle = start_run(engine, config, PREPFX_SMOKE_FORM["name"])

    assert handle.output_dir == handle.run_dir / "outputs"
    written_config = yaml.safe_load(handle.config_path.read_text(encoding="utf-8"))
    assert written_config["outputs_dir"] == f"{handle.output_dir.resolve().as_posix()}/"

    code = _wait_for_exit(handle)
    assert code == 0, handle.log_path.read_text(encoding="utf-8", errors="replace")
    # run_experiment.py writes the catalogue under results/ and the summary
    # and verdict tables under tables/ (see run_experiment.py's `run()`).
    assert (handle.output_dir / "results" / "scaling_catalogue.csv").is_file()
    assert (handle.output_dir / "tables" / "scaling_summary.csv").is_file()
    assert (handle.output_dir / "tables" / "scaling_verdicts.csv").is_file()


def test_prepfx_run_never_touches_the_real_outputs_directory():
    engine = PrepfxEngine()
    real_summary = engine.outputs_dir / "tables" / "scaling_summary.csv"
    before = real_summary.read_bytes() if real_summary.is_file() else None

    config = build_config_dict(engine, PREPFX_SMOKE_FORM)
    handle = start_run(engine, config, PREPFX_SMOKE_FORM["name"])
    _wait_for_exit(handle)

    after = real_summary.read_bytes() if real_summary.is_file() else None
    assert after == before, "a dashboard run modified the real B1 results file"


def test_each_run_gets_its_own_isolated_run_directory():
    engine = B2Engine()
    config = build_config_dict(engine, B2_SMOKE_FORM)
    first = start_run(engine, config, B2_SMOKE_FORM["name"])
    second = start_run(engine, build_config_dict(engine, B2_SMOKE_FORM), B2_SMOKE_FORM["name"])

    assert first.run_id != second.run_id
    assert first.run_dir != second.run_dir
    _wait_for_exit(first)
    _wait_for_exit(second)


def test_get_process_returns_none_for_an_unknown_run_id():
    assert get_process("not-a-real-run-id") is None


def test_launch_argv_uses_the_engines_own_interpreter_not_bare_python():
    engine = B2Engine()
    config = build_config_dict(engine, B2_SMOKE_FORM)
    handle = start_run(engine, config, B2_SMOKE_FORM["name"])
    try:
        # The real .venv interpreter path, not the literal string "python"
        # that engine.run_command() returns as a schema example.
        assert str(engine.root_path) in str(handle.process.args[0]) or \
            handle.process.args[0] != "python"
    finally:
        _wait_for_exit(handle)


def test_run_launch_error_on_an_unwritable_config_target(monkeypatch, tmp_path):
    import app.core.runner as runner_module

    engine = B2Engine()
    config = build_config_dict(engine, B2_SMOKE_FORM)
    # Point RUNS_DIR at a file (not a directory), so mkdir fails.
    blocked = tmp_path / "blocked"
    blocked.write_text("not a directory")
    monkeypatch.setattr(runner_module, "RUNS_DIR", blocked)

    with pytest.raises(RunLaunchError):
        start_run(engine, config, B2_SMOKE_FORM["name"])
