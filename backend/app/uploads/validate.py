# Structural checks on an uploaded CSV before anything is registered: a usable
# target, no empty columns, an inferable task type, and a free dataset id.
import csv
import re
from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from ..core.errors import UploadValidationError

TASKS = ("classification", "regression")
ID_PATTERN = re.compile(r"^[a-z0-9][a-z0-9_-]{1,39}$")
# An integer-valued target with more distinct values than this is read as
# regression unless the user states the task.
MAX_INFERRED_CLASSES = 20
SMALL_CLASS_WARNING = 10


@dataclass(frozen=True)
class ValidationResult:
    """Outcome of a successful validation: the confirmed target and task."""

    target: str
    task: str
    task_inferred: bool
    warnings: tuple[str, ...]


def check_dataset_id(dataset_id: str, taken: set[str]) -> None:
    """Check a proposed dataset id is well formed and not already in use.

    Inputs: dataset_id - the proposed id; taken - ids the engine already has.
    Output: None.
    Raises: UploadValidationError naming the rule that was broken.
    """
    if not ID_PATTERN.match(dataset_id):
        raise UploadValidationError(
            f"Dataset name '{dataset_id}' is not valid. Use 2 to 40 lowercase letters, "
            "digits, hyphens or underscores, starting with a letter or digit."
        )
    if dataset_id in taken:
        raise UploadValidationError(
            f"Dataset name '{dataset_id}' is already registered. Choose another name."
        )


def _read(path: Path) -> pd.DataFrame:
    """Read the CSV, rejecting unreadable files and unusable headers.

    Inputs: path - the staged CSV.
    Output: the parsed frame.
    Raises: UploadValidationError if it cannot be parsed, has blank or
    duplicate column names, or has no data rows.
    """
    try:
        with path.open("r", newline="", encoding="utf-8-sig") as fh:
            header = next(csv.reader(fh), [])
        frame = pd.read_csv(path)
    except (UnicodeDecodeError, pd.errors.ParserError, pd.errors.EmptyDataError) as exc:
        raise UploadValidationError(f"File could not be read as a UTF-8 CSV: {exc}") from exc
    names = [h.strip() for h in header]
    if not names or any(not n for n in names):
        raise UploadValidationError("CSV header row has a blank column name.")
    duplicates = sorted({n for n in names if names.count(n) > 1})
    if duplicates:
        raise UploadValidationError(f"CSV has duplicate column names: {', '.join(duplicates)}.")
    if frame.empty:
        raise UploadValidationError("CSV has a header but no data rows.")
    return frame


def infer_task(y: pd.Series) -> str:
    """Infer the task type from a target column with no missing values.

    Inputs: y - the target column.
    Output: "classification" for text, boolean, or integer-valued targets
    with at most MAX_INFERRED_CLASSES distinct values; otherwise "regression".
    """
    if not pd.api.types.is_numeric_dtype(y) or pd.api.types.is_bool_dtype(y):
        return "classification"
    whole = bool((y == y.round()).all())
    return "classification" if whole and y.nunique() <= MAX_INFERRED_CLASSES else "regression"


def validate_csv(path: Path, target: str, task: str | None = None) -> ValidationResult:
    """Validate an uploaded CSV and settle its target and task type.

    Inputs: path - the staged CSV; target - the target column name;
    task - "classification"/"regression", or None to infer it.
    Output: a ValidationResult with the task and any non-blocking warnings.
    Raises: UploadValidationError with a specific reason on any failed check.
    """
    frame = _read(Path(path))
    if target not in frame.columns:
        columns = ", ".join(map(str, frame.columns))
        raise UploadValidationError(
            f"Target column '{target}' is not in the CSV. Columns: {columns}."
        )
    features = frame.drop(columns=[target])
    if features.shape[1] == 0:
        raise UploadValidationError("CSV has a target column but no feature columns.")
    empty = [str(c) for c in frame.columns if frame[c].isna().all()]
    if empty:
        raise UploadValidationError(f"Column(s) with no values at all: {', '.join(empty)}.")
    if features.select_dtypes(include="number").shape[1] == 0:
        raise UploadValidationError("Dataset CSV has no numeric feature columns.")
    y = frame[target]
    if y.isna().any():
        raise UploadValidationError(
            f"Target column '{target}' has {int(y.isna().sum())} missing value(s); "
            "every row needs a target."
        )
    if y.nunique() < 2:
        raise UploadValidationError(f"Target column '{target}' has only one distinct value.")
    if task is not None and task not in TASKS:
        raise UploadValidationError(f"Unknown task type '{task}'. Allowed: {', '.join(TASKS)}.")
    settled = task or infer_task(y)
    return ValidationResult(target, settled, task is None, _task_warnings(y, target, settled))


def _task_warnings(y: pd.Series, target: str, task: str) -> tuple[str, ...]:
    """Check the target suits the task; return non-blocking warnings.

    Inputs: y - the target column; target - its name; task - the settled task.
    Output: tuple of warning strings (possibly empty).
    Raises: UploadValidationError for a non-numeric regression target or a
    class with a single member.
    """
    if task == "regression":
        if not pd.api.types.is_numeric_dtype(y) or pd.api.types.is_bool_dtype(y):
            raise UploadValidationError(
                f"Target column '{target}' is not numeric, so it cannot be a regression target."
            )
        return ()
    smallest = int(y.value_counts().min())
    if smallest < 2:
        raise UploadValidationError(
            f"Target column '{target}' has a class with only one row; "
            "stratified cross-validation needs at least two per class."
        )
    if smallest < SMALL_CLASS_WARNING:
        return (f"Smallest class has {smallest} rows; cross-validation with more than "
                f"{smallest} folds will fail on this dataset.",)
    return ()
