# /api/experiments - list one engine's fixed choices for a factor, and
# build+validate a wizard form into that engine's own config YAML.
from fastapi import APIRouter, HTTPException, Query

from ..core.config_builder import build_config
from ..core.errors import ConfigNameConflictError, ConfigValidationError
from ..core.form_schema import FACTORS
from ..engines.registry import get_engine

router = APIRouter(prefix="/api/experiments", tags=["experiments"])


@router.get("/choices")
def list_choices(
    engine: str = Query(..., description="prepfx or b2"),
    factor: str = Query(..., description="scaling or imputation"),
) -> dict:
    """Return one engine's fixed techniques, models and mechanisms for a factor.

    Inputs: engine - query param, "prepfx" or "b2"; factor - query param,
    "scaling" or "imputation".
    Output: dict with "techniques" (that factor's fixed list),
    "models" and "mechanisms" (always that engine's full fixed lists,
    since every run picks from them regardless of factor).
    Raises: HTTPException 400 for an unknown engine or factor.
    """
    adapter = get_engine(engine)
    if factor not in FACTORS:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown factor '{factor}'. Allowed: {', '.join(FACTORS)}.",
        )
    return {
        "techniques": adapter.fixed_techniques(factor),
        "models": adapter.fixed_models(),
        "mechanisms": adapter.valid_mechanisms(),
    }


@router.post("")
def create_experiment(form: dict) -> dict:
    """Validate a wizard form and write it as a YAML config for its engine.

    Inputs: form - the wizard payload; must include "engine" ("prepfx" or
    "b2") alongside the fields core.form_schema.normalise_form expects
    (name, factor, techniques, datasets, models, k, seed, and, for the
    imputation factor, missingness_rates/missingness_mechanisms).
    Output: dict with "engine" and "config_path" (the written YAML's path,
    under that engine's own configs/ directory).
    Raises: HTTPException 400 if "engine" is missing or unknown, 422 with
    the specific reason if the form fails validation, 409 if the
    experiment name's filename already exists for that engine.
    """
    engine_name = form.get("engine")
    if not engine_name:
        raise HTTPException(status_code=400, detail="Field 'engine' is required.")
    adapter = get_engine(engine_name)
    wizard_form = {k: v for k, v in form.items() if k != "engine"}
    try:
        path = build_config(adapter, wizard_form)
    except ConfigNameConflictError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except ConfigValidationError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return {"engine": engine_name, "config_path": str(path)}
