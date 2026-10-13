# The one place that maps an engine name from the UI/API to its adapter
# class, so every router resolves "prepfx"/"b2" the same way and a third
# engine would only need to be added here.
from fastapi import HTTPException

from .b2 import B2Engine
from .lab import LabEngine
from .prepfx import PrepfxEngine

ENGINES = {"prepfx": PrepfxEngine, "b2": B2Engine, "lab": LabEngine}


def get_engine(name: str):
    """Construct the adapter for an engine name.

    Inputs: name - "prepfx", "b2" or "lab".
    Output: a constructed Engine adapter.
    Raises: HTTPException 400 for any other name.
    """
    if name not in ENGINES:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown engine '{name}'. Allowed: {', '.join(sorted(ENGINES))}.",
        )
    return ENGINES[name]()
