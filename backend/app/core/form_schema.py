# Engine-agnostic wizard form: normalise and check it against an engine's
# fixed design, before any engine-specific field naming happens.
from __future__ import annotations

from dataclasses import dataclass

from .errors import ConfigValidationError

# The factors the two original engines vary. The lab engine supports
# six (it implements the full Chapter 1 design), so the validator asks
# the engine rather than assuming this tuple -- see supported_factors().
FACTORS = ("scaling", "imputation")


def supported_factors(engine) -> tuple[str, ...]:
    """Return the factors one engine can actually vary.

    Inputs: engine - an Engine adapter.
    Output: the engine's own `FACTORS` when it declares one, else the
    two-factor default the original engines use. Asking the engine means
    a new engine with more components needs no change here.
    """
    declared = getattr(engine, "factors", None)
    return tuple(declared) if declared else FACTORS


@dataclass(frozen=True)
class WizardForm:
    """One validated wizard submission, in engine-neutral terms.

    Purpose: a single shape every engine adapter can translate into its
    own config schema, so no caller has to know whether an engine calls
    the factor "arm" or "factor".
    Inputs: see fields.
    Output: a frozen, already-validated form.
    """

    name: str
    factor: str
    techniques: tuple[str, ...]
    datasets: tuple[str, ...]
    models: tuple[str, ...]
    k: int
    seed: int
    missingness_rates: tuple[float, ...]
    missingness_mechanisms: tuple[str, ...]


def normalise_form(engine, form: dict) -> WizardForm:
    """Validate a raw wizard dict against one engine's fixed design.

    Inputs: engine - an Engine adapter; form - the raw dict from the UI
    with keys name, factor, techniques, datasets, models, k, seed and,
    for the imputation factor, missingness_rates/missingness_mechanisms.
    Output: a WizardForm.
    Raises: ConfigValidationError naming the offending field.
    """
    _reject_unknown_keys(form)
    name = _require_name(form)
    factor = _require_factor(form, supported_factors(engine))
    techniques = _require_techniques(engine, form, factor)
    datasets = _require_str_list(form, "datasets")
    models = _require_models(engine, form)
    k = _require_int(form, "k", minimum=2)
    seed = _require_int(form, "seed", minimum=0)
    rates, mechanisms = _require_missingness(form, factor)
    return WizardForm(
        name=name,
        factor=factor,
        techniques=techniques,
        datasets=datasets,
        models=models,
        k=k,
        seed=seed,
        missingness_rates=rates,
        missingness_mechanisms=mechanisms,
    )


ALLOWED_KEYS = {
    "name", "factor", "techniques", "datasets", "models", "k", "seed",
    "missingness_rates", "missingness_mechanisms",
}


def _reject_unknown_keys(form: dict) -> None:
    unknown = sorted(set(form) - ALLOWED_KEYS)
    if unknown:
        raise ConfigValidationError(
            f"Unknown form field(s): {', '.join(unknown)}. "
            f"Allowed: {', '.join(sorted(ALLOWED_KEYS))}."
        )


def _require_name(form: dict) -> str:
    name = form.get("name")
    if not isinstance(name, str) or not name.strip():
        raise ConfigValidationError("Field 'name' must be a non-empty experiment name.")
    return name.strip()


def _require_factor(form: dict, allowed: tuple[str, ...] = FACTORS) -> str:
    factor = form.get("factor")
    if factor not in allowed:
        raise ConfigValidationError(
            f"Field 'factor' must be one of {', '.join(allowed)}; got {factor!r}."
        )
    return factor


def _require_techniques(engine, form: dict, factor: str) -> tuple[str, ...]:
    allowed = engine.fixed_techniques(factor)
    chosen = _require_str_list(form, "techniques")
    bad = [t for t in chosen if t not in allowed]
    if bad:
        raise ConfigValidationError(
            f"Invalid technique(s) for factor '{factor}': {', '.join(bad)}. "
            f"Allowed: {', '.join(allowed)}."
        )
    if len(set(chosen)) != len(chosen):
        raise ConfigValidationError("Field 'techniques' must not repeat a technique.")
    return chosen


def _require_models(engine, form: dict) -> tuple[str, ...]:
    allowed = engine.fixed_models()
    chosen = _require_str_list(form, "models")
    bad = [m for m in chosen if m not in allowed]
    if bad:
        raise ConfigValidationError(
            f"Invalid model(s): {', '.join(bad)}. Allowed: {', '.join(allowed)}."
        )
    if len(set(chosen)) != len(chosen):
        raise ConfigValidationError("Field 'models' must not repeat a model.")
    return chosen


def _require_str_list(form: dict, field: str) -> tuple[str, ...]:
    value = form.get(field)
    if not isinstance(value, list) or not value:
        raise ConfigValidationError(f"Field '{field}' must be a non-empty list.")
    if not all(isinstance(v, str) and v.strip() for v in value):
        raise ConfigValidationError(f"Field '{field}' must contain non-empty names.")
    return tuple(v.strip() for v in value)


def _require_int(form: dict, field: str, minimum: int) -> int:
    value = form.get(field)
    if not isinstance(value, int) or isinstance(value, bool):
        raise ConfigValidationError(f"Field '{field}' must be a whole number.")
    if value < minimum:
        raise ConfigValidationError(f"Field '{field}' must be at least {minimum}; got {value}.")
    return value


def _require_missingness(form: dict, factor: str) -> tuple[tuple[float, ...], tuple[str, ...]]:
    """Check the missingness pair, which only the imputation factor may carry.

    Inputs: form - raw wizard dict; factor - the validated factor.
    Output: (rates, mechanisms), both empty for the scaling factor.
    Raises: ConfigValidationError naming the offending field.
    """
    has_rates = "missingness_rates" in form
    has_mechs = "missingness_mechanisms" in form
    if factor != "imputation":
        if has_rates or has_mechs:
            raise ConfigValidationError(
                "Fields 'missingness_rates' and 'missingness_mechanisms' apply "
                "only to the imputation factor."
            )
        return (), ()
    if not has_rates or not has_mechs:
        raise ConfigValidationError(
            "The imputation factor requires both 'missingness_rates' and "
            "'missingness_mechanisms'."
        )
    rates = form["missingness_rates"]
    if not isinstance(rates, list) or not rates:
        raise ConfigValidationError("Field 'missingness_rates' must be a non-empty list.")
    bad = [r for r in rates if isinstance(r, bool) or not isinstance(r, (int, float)) or not 0 < r < 1]
    if bad:
        raise ConfigValidationError(
            f"Invalid missingness rate(s): {bad}. Each must be a fraction between 0 and 1, "
            "such as 0.15 for 15%."
        )
    mechanisms = _require_str_list(form, "missingness_mechanisms")
    return tuple(float(r) for r in rates), mechanisms
