# Runs a one-off script under an engine's own interpreter, so a result is
# computed by that engine's own code and library versions rather than the
# dashboard's — used for dataset registration and for extracting results
# from a store only the engine's own libraries can read (b2's MLflow db).
import json
import subprocess
import sys
from pathlib import Path

from ..core.errors import DatasetRegistrationError

TIMEOUT_SECONDS = 300


def engine_python(root_path: Path) -> str:
    """Return the interpreter that an engine's own code runs under.

    Inputs: root_path - the engine repo root.
    Output: path to that repo's .venv interpreter, or this process's own
    interpreter when the repo has no .venv.
    """
    for candidate in (root_path / ".venv" / "Scripts" / "python.exe",
                      root_path / ".venv" / "bin" / "python"):
        if candidate.is_file():
            return str(candidate)
    return sys.executable


def run_engine_script(
    root_path: Path, script: Path, options: dict[str, str],
    error_cls: type[Exception] = DatasetRegistrationError,
    action: str = "script",
) -> dict:
    """Run one script under an engine's own interpreter and return its JSON result.

    Inputs: root_path - the engine repo root (also the working directory);
    script - the script to run; options - its --name value pairs;
    error_cls - exception type to raise on failure (lets each caller
    surface a failure as its own error type to the API layer);
    action - a short label for this run used only in error messages
    (e.g. "Dataset registration", "Result extraction").
    Output: the dict the script printed as its last stdout line.
    Raises: error_cls carrying the script's last error line if it exits
    non-zero, times out, or prints no JSON.
    """
    argv = [engine_python(root_path), str(script)]
    for name, value in options.items():
        argv += [f"--{name}", str(value)]
    try:
        proc = subprocess.run(
            argv, cwd=root_path, capture_output=True, text=True,
            encoding="utf-8", errors="replace", timeout=TIMEOUT_SECONDS,
        )
    except subprocess.TimeoutExpired as exc:
        raise error_cls(f"{action} timed out after {TIMEOUT_SECONDS} seconds.") from exc
    if proc.returncode != 0:
        lines = [ln for ln in proc.stderr.strip().splitlines() if ln.strip()]
        reason = lines[-1].removeprefix("Error: ") if lines else f"exit code {proc.returncode}"
        raise error_cls(f"{action} failed: {reason}")
    try:
        return json.loads(proc.stdout.strip().splitlines()[-1])
    except (IndexError, json.JSONDecodeError) as exc:
        raise error_cls(f"{action} finished but reported no result.") from exc


def run_register_script(root_path: Path, script: Path, options: dict[str, str]) -> dict:
    """Run one engine registration script and return its JSON result.

    Thin wrapper over run_engine_script fixed to DatasetRegistrationError,
    kept so existing callers (engines/prepfx.py, engines/b2.py's dataset
    registration) are unaffected by run_engine_script's more general signature.
    Inputs: root_path - the engine repo root; script - the register_dataset.py
    to run; options - its --name value pairs.
    Output: the dict the script printed as its last stdout line.
    Raises: DatasetRegistrationError — see run_engine_script.
    """
    return run_engine_script(root_path, script, options, DatasetRegistrationError, "Dataset registration")
