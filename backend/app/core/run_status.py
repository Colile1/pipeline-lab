# Parses one run's log and output files into a validation summary. Pure
# reading: it never launches, mutates or re-runs anything. The guiding rule
# is that a run counts as successful only on positive evidence from the
# engine's own output — never by the absence of an error.
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

from .runner import get_process

# Python prints this when an exception reaches the top level. b2's
# run_experiment.py has no try/except at all, and prepfx catches only its
# MLflow start, so a traceback in either log is a real failure.
TRACEBACK_MARKER = "Traceback (most recent call last):"
# Lines carrying an engine's own fatal error text, worth surfacing verbatim.
ERROR_LINE = re.compile(r"^(?:\w*Error|Exception)\b.*", re.MULTILINE)

RUNNING = "running"
SUCCEEDED = "succeeded"
FAILED = "failed"
UNKNOWN = "unknown"


@dataclass
class ValidationSummary:
    """The post-run validation report for one run.

    Purpose: tell a non-technical user whether a run actually did what it
    was asked to do, with every number traceable to the engine's own log
    or output files.
    Inputs: see fields.
    Output: a summary the API serialises straight to JSON.
    """

    run_id: str
    engine: str
    state: str
    exit_code: int | None = None
    expected: int | None = None
    completed: int = 0
    expected_label: str = "units"
    progress_label: str = "completed"
    success_marker_seen: bool = False
    reported_total: int | None = None
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    missingness: dict | None = None
    outputs: list[str] = field(default_factory=list)
    config_path: str | None = None
    log_path: str | None = None
    notes: list[str] = field(default_factory=list)


def get_status(run_id: str) -> str:
    """Report whether a tracked run is still running, or how it ended.

    Inputs: run_id - the id returned by runner.start_run.
    Output: RUNNING, SUCCEEDED, FAILED, or UNKNOWN when this server
    process does not track that run (e.g. it was launched before a
    restart); UNKNOWN never means "fine".
    """
    handle = get_process(run_id)
    if handle is None:
        return UNKNOWN
    code = handle.poll()
    if code is None:
        return RUNNING
    return SUCCEEDED if code == 0 else FAILED


def summarise_validation(handle, engine, config: dict | None = None) -> ValidationSummary:
    """Build the full validation summary for one launched run.

    A run is reported as succeeded only when all three hold: the process
    exited 0, the engine's own success line is present, and no traceback
    appears in the log. Any other combination is reported as failed or
    still running, with the reason recorded — a missing success marker on
    a zero exit is treated as a failure, not glossed over.

    Inputs: handle - the RunHandle from runner.start_run; engine - the
    matching Engine adapter; config - the config dict the run used; when
    omitted, falls back to handle.config (the dict runner.start_run wrote
    to disk, after outputs_dir isolation), so a caller that already has
    the handle need not keep its own copy in sync.
    Output: a ValidationSummary.
    """
    if config is None:
        config = getattr(handle, "config", None)
    markers = engine.log_markers()
    log_text = _read_log(handle.log_path)
    summary = ValidationSummary(
        run_id=handle.run_id,
        engine=handle.engine_name,
        state=UNKNOWN,
        exit_code=handle.poll(),
        expected_label=markers.get("expected_label", "units"),
        progress_label=markers.get("progress_label", "completed"),
        config_path=str(handle.config_path),
        log_path=str(handle.log_path),
    )

    if log_text is None:
        summary.state = UNKNOWN
        summary.notes.append("The run log could not be read, so nothing about this run is confirmed.")
        return summary

    summary.expected = _first_int(markers.get("expected"), log_text)
    summary.completed = _count_matches(markers.get("progress"), log_text)
    summary.reported_total = _first_int(markers.get("success"), log_text)
    summary.success_marker_seen = summary.reported_total is not None or _matches(
        markers.get("success"), log_text
    )
    summary.errors = _collect_errors(log_text)
    summary.warnings = _collect_warnings(markers.get("warning"), log_text)
    summary.state = _decide_state(summary)
    _add_shortfall_note(summary)

    summary.missingness = engine.read_achieved_missingness(handle.output_dir, config or {})
    if summary.missingness is None and _requested_missingness(config):
        summary.notes.append(
            f"{handle.engine_name} does not record the missingness it actually achieved, "
            "so the requested rate could not be confirmed against a measured one."
        )
    else:
        _add_missingness_note(summary)

    summary.outputs = _list_outputs(handle.output_dir)
    if handle.output_dir is not None and not summary.outputs and summary.state == SUCCEEDED:
        summary.state = FAILED
        summary.notes.append(
            "The run reported success but wrote no output files, so its results are missing."
        )
    return summary


def _decide_state(summary: ValidationSummary) -> str:
    """Classify a run from its exit code, success marker and errors.

    Inputs: summary - a partly filled ValidationSummary.
    Output: RUNNING, SUCCEEDED or FAILED.
    """
    if summary.exit_code is None:
        return RUNNING
    if summary.exit_code != 0 or summary.errors:
        return FAILED
    if not summary.success_marker_seen:
        return FAILED
    return SUCCEEDED


def _add_shortfall_note(summary: ValidationSummary) -> None:
    """Record a note when fewer units finished than the run planned.

    Inputs: summary - the summary being built, updated in place.
    Output: None.
    """
    if summary.exit_code is None or summary.expected is None:
        return
    if summary.reported_total is not None and summary.reported_total < summary.expected:
        summary.notes.append(
            f"The engine reported {summary.reported_total} of {summary.expected} "
            f"{summary.expected_label}, so some did not finish."
        )
    if summary.state == FAILED and summary.completed < summary.expected:
        summary.notes.append(
            f"{summary.completed} {summary.progress_label} before the run stopped; "
            f"{summary.expected} {summary.expected_label} were planned."
        )


def _add_missingness_note(summary: ValidationSummary) -> None:
    """Flag any dataset whose achieved missingness missed the request.

    Inputs: summary - the summary being built, updated in place.
    Output: None.
    """
    report = summary.missingness
    if not report:
        return
    requested = report.get("requested")
    achieved = report.get("achieved") or []
    if requested is None or not achieved:
        return
    # 1 percentage point: count-based injection lands within rounding of the
    # request, so a larger gap means the run did not do what was asked.
    drifted = [a for a in achieved if abs(a["proportion"] - requested) > 0.01]
    if drifted:
        worst = max(drifted, key=lambda a: abs(a["proportion"] - requested))
        summary.notes.append(
            f"Achieved missingness differs from the requested {requested:.3f} on "
            f"{len(drifted)} of {len(achieved)} datasets (largest gap: "
            f"{worst['dataset']} at {worst['proportion']:.3f})."
        )


def _requested_missingness(config: dict | None) -> bool:
    """Say whether a config asked for injected missingness at all.

    Inputs: config - the config the run used, or None.
    Output: True when either engine's missingness fields are present.
    """
    if not config:
        return False
    return bool(config.get("missingness") or config.get("missingness_rates"))


def _read_log(log_path: Path) -> str | None:
    """Read a run log, tolerating encoding damage.

    Inputs: log_path - path to the run's log file.
    Output: the log text, or None if it cannot be read.
    """
    try:
        return Path(log_path).read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None


def _first_int(pattern: str | None, text: str) -> int | None:
    """Return the first captured integer for a pattern, if it matches.

    Inputs: pattern - regex with one capture group, or None; text - log text.
    Output: the integer, or None.
    """
    if not pattern:
        return None
    match = re.search(pattern, text, re.MULTILINE)
    if not match or not match.groups():
        return None
    try:
        return int(match.group(1))
    except (TypeError, ValueError):
        return None


def _matches(pattern: str | None, text: str) -> bool:
    """Say whether a pattern appears at all.

    Inputs: pattern - regex or None; text - log text.
    Output: True when the pattern matches.
    """
    return bool(pattern) and re.search(pattern, text, re.MULTILINE) is not None


def _count_matches(pattern: str | None, text: str) -> int:
    """Count how many lines match a progress pattern.

    Inputs: pattern - regex or None; text - log text.
    Output: the match count, 0 when there is no pattern.
    """
    if not pattern:
        return 0
    return len(re.findall(pattern, text, re.MULTILINE))


def _collect_errors(text: str) -> list[str]:
    """Collect failure evidence from a log, most useful line first.

    Inputs: text - log text.
    Output: list of distinct error lines; empty when the log is clean.
    """
    errors: list[str] = []
    if TRACEBACK_MARKER in text:
        errors.append(TRACEBACK_MARKER)
    for line in ERROR_LINE.findall(text):
        stripped = line.strip()
        if stripped and stripped not in errors:
            errors.append(stripped)
    return errors[:10]


def _collect_warnings(pattern: str | None, text: str) -> list[str]:
    """Collect an engine's own non-fatal warning lines.

    Inputs: pattern - the engine's warning regex, or None; text - log text.
    Output: list of warning lines, which never make a run count as failed.
    """
    if not pattern:
        return []
    return [line.strip() for line in re.findall(rf"{pattern}.*", text, re.MULTILINE)][:10]


def _list_outputs(output_dir) -> list[str]:
    """List the files a run wrote into its own output directory.

    Inputs: output_dir - the run's isolated output directory, or None for
    an engine that writes no files there (b2 logs to MLflow instead).
    Output: sorted relative paths; empty when there is nothing to list.
    """
    if output_dir is None:
        return []
    root = Path(output_dir)
    if not root.is_dir():
        return []
    return sorted(
        str(p.relative_to(root)).replace("\\", "/")
        for p in root.rglob("*")
        if p.is_file()
    )
