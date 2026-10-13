# /api/datasets - list an engine's registered datasets, and upload a new CSV
# into an engine's own dataset records.
import uuid
from pathlib import Path

from fastapi import APIRouter, File, Form, HTTPException, Query, UploadFile

from ..core.errors import DatasetRegistrationError, UploadValidationError
from ..engines.registry import get_engine
from ..uploads.register import register_upload

router = APIRouter(prefix="/api/datasets", tags=["datasets"])

# Temporary home for an upload between receipt and registration (data/README.md).
STAGING_DIR = Path(__file__).resolve().parents[3] / "data" / "uploads"


@router.get("")
def list_datasets(engine: str = Query(..., description="prepfx or b2")) -> list[dict]:
    """Return one engine's registered datasets, in that engine's own fields.

    Inputs: engine - query param, "prepfx" or "b2".
    Output: list of dicts from that engine's list_datasets(), unmodified.
    Raises: HTTPException 400 for an unknown engine name, 404 if that
    engine's catalogue has not been created yet.
    """
    adapter = get_engine(engine)
    try:
        return adapter.list_datasets()
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/upload")
def upload_dataset(
    file: UploadFile = File(...),
    engine: str = Form(...),
    dataset_id: str = Form(...),
    target: str = Form(...),
    task: str | None = Form(None),
    domain: str = Form("unspecified"),
) -> dict:
    """Validate an uploaded CSV and register it in the chosen engine.

    Inputs: file - the CSV; engine - "prepfx" or "b2"; dataset_id - name to
    register under; target - target column; task - optional task type
    (inferred when omitted); domain - application domain (B2's catalogue).
    Output: the registration summary from uploads.register.register_upload.
    Raises: HTTPException 400 for an unknown engine, 422 with the specific
    reason for an unusable CSV or name, 500 with the engine's own error
    line if the engine's registration step fails.
    """
    adapter = get_engine(engine)
    STAGING_DIR.mkdir(parents=True, exist_ok=True)
    staged = STAGING_DIR / f"{uuid.uuid4().hex}.csv"
    try:
        staged.write_bytes(file.file.read())
        return register_upload(
            adapter, staged, dataset_id.strip(), target, task or None,
            domain.strip() or "unspecified", Path(file.filename or "upload.csv").name,
        )
    except UploadValidationError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except DatasetRegistrationError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    finally:
        staged.unlink(missing_ok=True)
