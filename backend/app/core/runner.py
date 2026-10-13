# Launches one engine's run_experiment.py as a detached background process,
# tracked by run-id, with its output isolated from the engine's own real
# results. No analysis logic lives here — only process launch and bookkeeping.
from __future__ import annotations

import subprocess
import uuid
from dataclasses import dataclass
from pathlib import Path

from ..engines.registration import engine_python
from .config_builder import write_config
from .errors import RunLaunchError

# Dashboard-owned staging area for run artefacts, never under a target
# engine's own repo (see data/README.md).
RUNS_DIR = Path(__file__).resolve().parents[4] / "data" / "runs"

# run-id -> RunHandle, for the lifetime of this server process. A restart
# loses track of runs launched before it (get_process returns None; the
# log file and output directory on disk are untouched and still readable).
_PROCESSES: dict[str, "RunHandle"] = {}


@dataclass
class RunHandle:
    """Everything needed to track one launched run.

    Purpose: the single record core/api/run_status.py use to find a run's
    process, log, and isolated output directory.
    Inputs: see fields. `config` is the dict actually written to disk —
    after outputs_dir isolation — so run_status can read it back without
    the caller needing to keep its own copy in sync.
    Output: a handle stored in the in-memory process registry and
    returned to the caller that launched the run.
    """

    run_id: str
    engine_name: str
    config: dict
    config_path: Path
    run_dir: Path
    log_path: Path
    output_dir: Path | None
    process: subprocess.Popen

    def poll(self) -> int | None:
        """Check whether the process has finished without blocking.

        Inputs: none.
        Output: the exit code, or None if still running.
        """
        return self.process.poll()


def start_run(engine, config: dict, experiment_name: str) -> RunHandle:
    """Launch one engine config as a detached background process.

    Writes the config into its own run directory under data/runs/<run-id>,
    overriding outputs_dir (when the engine's schema has one) to a folder
    inside that same run directory — never the engine's own outputs_dir —
    so a dashboard run can never overwrite that engine's real results.

    Inputs: engine - an Engine adapter; config - a dict from
    core.config_builder.build_config_dict (already validated); experiment_name -
    the wizard form's experiment name, used only to slug the config filename.
    Output: a RunHandle, also kept in this module's in-memory registry.
    Raises: RunLaunchError if the config cannot be written or the process
    cannot be started (e.g. the engine's interpreter is missing).
    """
    run_id = uuid.uuid4().hex
    run_dir = RUNS_DIR / run_id
    output_dir = _isolate_outputs_dir(engine, config, run_dir)

    try:
        config_path = write_config(config, experiment_name, run_dir)
    except OSError as exc:
        raise RunLaunchError(f"Could not write run config: {exc}") from exc

    argv = _launch_argv(engine, config_path)
    log_path = run_dir / "run.log"
    try:
        log_file = log_path.open("w", encoding="utf-8")
    except OSError as exc:
        raise RunLaunchError(f"Could not open run log: {exc}") from exc

    try:
        process = subprocess.Popen(
            argv, cwd=engine.root_path, stdout=log_file, stderr=subprocess.STDOUT,
        )
    except OSError as exc:
        raise RunLaunchError(f"Could not start {engine.name} run: {exc}") from exc
    finally:
        # Popen duplicates the fd for the child; close this process's copy
        # either way, or every launched run leaks one open file handle here.
        log_file.close()

    handle = RunHandle(
        run_id=run_id, engine_name=engine.name, config=config, config_path=config_path,
        run_dir=run_dir, log_path=log_path, output_dir=output_dir, process=process,
    )
    _PROCESSES[run_id] = handle
    return handle


def get_process(run_id: str) -> RunHandle | None:
    """Look up a previously launched run by its run-id.

    Inputs: run_id - the id returned by start_run.
    Output: the RunHandle, or None if no run with that id is tracked by
    this server process (including runs launched before a restart).
    """
    return _PROCESSES.get(run_id)


def list_runs() -> list["RunHandle"]:
    """Return every run this server process currently tracks.

    Inputs: none.
    Output: list of RunHandle, most recently launched first. A run
    launched before this server process last restarted is not included
    (its log/output on disk are unaffected, but this process never
    tracked it — see get_process).
    """
    return list(reversed(_PROCESSES.values()))


def _launch_argv(engine, config_path: Path) -> list[str]:
    """Build the real subprocess argv for one engine's run_command.

    engine.run_command() returns a bare "python" as a schema example; a
    launch must use that engine's own .venv interpreter instead, since
    the dashboard's own interpreter does not have the engine's libraries
    (see engines/registration.py::engine_python).

    Inputs: engine - an Engine adapter; config_path - the written YAML.
    Output: argv list with the real interpreter substituted in.
    """
    argv = engine.run_command(config_path)
    return [engine_python(engine.root_path), *argv[1:]]


def _isolate_outputs_dir(engine, config: dict, run_dir: Path) -> Path | None:
    """Redirect a config's outputs_dir into the run's own directory, in place.

    prepfx's run_experiment.py overwrites <outputs_dir>/results/{arm}_*.csv
    and figures unconditionally, filed by arm name only — the same files
    the real B1 confirmatory results live in when outputs_dir is the
    engine's own "outputs/". Every dashboard run must use an isolated
    outputs_dir instead, so a run can never touch that record.

    Inputs: engine - an Engine adapter; config - the dict from
    build_config_dict, mutated in place when it has an outputs_dir key;
    run_dir - this run's own directory.
    Output: the absolute output path now set in config, or None if this
    engine's schema has no outputs_dir field (e.g. b2, which logs to its
    own shared mlflow.db instead).
    """
    if "outputs_dir" not in config:
        return None
    output_dir = run_dir / "outputs"
    # A literal trailing slash, matching every real prepfx config example.
    config["outputs_dir"] = f"{output_dir.resolve().as_posix()}/"
    return output_dir
