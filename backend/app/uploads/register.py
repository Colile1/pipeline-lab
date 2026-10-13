# Orchestrates one upload: check the name, validate the CSV, then hand it to
# the target engine, which characterises and registers it with its own code.
from pathlib import Path

from .validate import check_dataset_id, validate_csv


def register_upload(
    engine,
    csv_path: Path,
    dataset_id: str,
    target: str,
    task: str | None = None,
    domain: str = "unspecified",
    source_name: str = "",
) -> dict:
    """Validate a staged CSV and register it in the target engine.

    Inputs: engine - an Engine adapter; csv_path - the staged CSV;
    dataset_id - the name to register under; target - the target column;
    task - task type or None to infer; domain - application domain (used
    by engines whose catalogue records one); source_name - original filename.
    Output: dict with engine, dataset_id, target, task, task_inferred,
    warnings, plus the engine's own "registered" record and
    "characteristics" exactly as that engine computed them.
    Raises: UploadValidationError if the name or CSV is unusable;
    DatasetRegistrationError if the engine's registration step fails.
    """
    check_dataset_id(dataset_id, engine.registered_ids())
    checked = validate_csv(csv_path, target, task)
    outcome = engine.register_dataset(
        csv_path, dataset_id, checked.target, checked.task, domain, source_name
    )
    return {
        "engine": engine.name,
        "dataset_id": dataset_id,
        "target": checked.target,
        "task": checked.task,
        "task_inferred": checked.task_inferred,
        "warnings": list(checked.warnings),
        "registered": outcome["registered"],
        "characteristics": outcome["characteristics"],
    }
