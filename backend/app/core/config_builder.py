# Wizard form -> validated engine config: check against the engine's fixed
# design, let the engine name its own fields, then write the YAML.
from __future__ import annotations

import re
from pathlib import Path

import yaml

from .errors import ConfigNameConflictError, ConfigValidationError
from .form_schema import normalise_form

__all__ = [
    "ConfigValidationError", "ConfigNameConflictError", "build_config_dict",
    "build_config", "write_config", "config_filename",
]


def build_config_dict(engine, form: dict) -> dict:
    """Validate a wizard form and render it in one engine's config schema.

    Inputs: engine - an Engine adapter; form - the raw wizard dict.
    Output: a dict matching that engine's own YAML schema, field for field.
    Raises: ConfigValidationError naming the offending field.
    """
    validated = normalise_form(engine, form)
    return engine.build_config_dict(validated)


def build_config(engine, form: dict, configs_dir: Path | None = None) -> Path:
    """Validate a wizard form and write it as a YAML config for one engine.

    Inputs: engine - an Engine adapter; form - the raw wizard dict;
    configs_dir - where to write, defaulting to the engine's own
    configs directory.
    Output: path to the written YAML file.
    Raises: ConfigValidationError naming the offending field;
    ConfigNameConflictError if the slugged filename already exists.

    Writes under the engine's own configs_dir by default, which doubles
    as where its own pre-registered configs live — write_config refuses
    to overwrite an existing file there. For a dashboard-launched run, use
    core.runner (which calls write_config with an isolated outputs_dir)
    instead of calling this directly, so a run never writes into the
    engine's own outputs_dir (see runner.py for why).
    """
    config = build_config_dict(engine, form)
    target_dir = Path(configs_dir) if configs_dir is not None else Path(engine.configs_dir)
    return write_config(config, form.get("name", ""), target_dir)


def write_config(config: dict, name: str, target_dir: Path) -> Path:
    """Write an already-built config dict as YAML.

    Inputs: config - a dict from build_config_dict, optionally with
    outputs_dir overridden by the caller; name - the experiment name,
    used only to slug the filename; target_dir - directory to write into.
    Output: path to the written YAML file.
    Raises: ConfigValidationError if the name has no usable filename slug;
    ConfigNameConflictError if a file of that name already exists in
    target_dir — this never overwrites, since target_dir may be an
    engine's real configs/ directory holding pre-registered configs such
    as scaling_arm.yaml. A caller that wants a fresh name on every call
    (core.runner does, with a new run directory each launch) will not
    hit this in practice.
    """
    target_dir = Path(target_dir)
    target_dir.mkdir(parents=True, exist_ok=True)
    path = target_dir / config_filename(name)
    if path.exists():
        raise ConfigNameConflictError(
            f"A config named '{path.name}' already exists in {target_dir}. "
            "Choose a different experiment name."
        )
    path.write_text(to_yaml(config), encoding="utf-8")
    return path


def to_yaml(config: dict) -> str:
    """Render a config dict as YAML in the engine's own key order.

    Inputs: config - a dict from an engine's build_config_dict.
    Output: YAML text.
    """
    return yaml.safe_dump(config, sort_keys=False, default_flow_style=False)


def config_filename(name: str) -> str:
    """Turn an experiment name into a safe YAML filename.

    Inputs: name - the experiment name from the wizard form.
    Output: a slugged '<name>.yaml' filename.
    Raises: ConfigValidationError if nothing usable remains after slugging.
    """
    slug = re.sub(r"[^a-z0-9]+", "_", name.strip().lower()).strip("_")
    if not slug:
        raise ConfigValidationError(
            f"Experiment name {name!r} has no letters or digits to build a filename from."
        )
    return f"{slug}.yaml"
