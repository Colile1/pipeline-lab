# lab (Pipeline Lab) adapter: the five-component OFAT engine from
# Chapter_1_Colile.docx, plus encoding as a sixth factor by amendment.
#
# Unlike prepfx and b2, this engine's fixed lists are IMPORTED from the
# engine itself rather than copied here. A copied list is how the
# dashboard's PrepfxEngine ended up claiming "logreg" when prepfx's own
# key is "logistic" -- a bug that survived three build steps because
# nothing executed a real run. Importing makes that class of drift
# impossible.
import sys
from pathlib import Path

from ..core.errors import ConfigValidationError

# The engine lives beside the two research repos, not inside this app.
REPO_ROOT = Path(__file__).resolve().parents[5] / "pipeline-lab-engine"


def _engine_src() -> str:
    """Return the engine's src/ path, adding it to sys.path once."""
    src = str(REPO_ROOT / "src")
    if src not in sys.path:
        sys.path.insert(0, src)
    return src


def _engine_config():
    """Import the engine's own config module.

    Inputs: none.
    Output: the piplab.config module, so the fixed lists below are the
    engine's real ones rather than a copy that can drift.
    Raises: ImportError if the engine is not present beside this app.
    """
    _engine_src()
    from piplab import config as engine_config

    return engine_config


class LabEngine:
    """Adapter for the pipeline-lab-engine (the full Chapter 1 design).

    Purpose: expose the lab engine's six components, its own config
    schema and its run command to the rest of this app.
    Inputs: none (constructed with no arguments).
    Output: an Engine-shaped object (see engines/base.py).
    """

    name = "lab"
    root_path = REPO_ROOT
    configs_dir = REPO_ROOT / "configs"
    outputs_dir = REPO_ROOT / "outputs"
    catalogue_path = REPO_ROOT / "src" / "piplab" / "datasets" / "loaders.py"
    # This engine registers no user datasets yet: uploads are a step-6
    # feature of the original dashboard, not yet wired to this engine.
    user_datasets_path = REPO_ROOT / "data" / "user_datasets.csv"

    # Six components, where prepfx and b2 vary two. core/form_schema.py
    # reads this via supported_factors() rather than assuming.
    @property
    def factors(self) -> tuple[str, ...]:
        """Return the components this engine can vary."""
        return _engine_config().COMPONENTS

    def fixed_techniques(self, factor: str) -> list[str]:
        """Return the engine's own technique list for one component.

        The first entry is Chapter 1's baseline for that component.
        Inputs: factor - one of the six components.
        Output: list of technique names, baseline first.
        Raises: ValueError naming the valid components.
        """
        techniques = _engine_config().TECHNIQUES
        if factor not in techniques:
            raise ValueError(
                f"lab has no component '{factor}'; expected one of {list(techniques)}"
            )
        return list(techniques[factor])

    def fixed_models(self) -> list[str]:
        """Return the engine's own model list."""
        return list(_engine_config().MODELS)

    def valid_mechanisms(self) -> list[str]:
        """Return the missingness mechanisms this engine accepts.

        Inputs: none.
        Output: an empty list. This engine injects no missingness: it
        uses each dataset's natural missingness and compares imputation
        strategies against row deletion, per Chapter 1's table. The
        wizard should therefore offer no mechanism control for `lab`.
        """
        return []

    def baselines(self) -> dict:
        """Return Chapter 1's baseline technique per component.

        Inputs: none.
        Output: {component: baseline technique}, which the composer
        pre-fills its baseline column with.
        """
        return dict(_engine_config().BASELINES)

    def build_config_dict(self, form) -> dict:
        """Translate a wizard form into this engine's own config schema.

        A third shape alongside prepfx's `arm` and b2's `factor`: this
        engine names the swept component `vary`, lists its levels in
        `techniques`, and holds every other component at `baseline`.
        Inputs: form - a core.form_schema.WizardForm.
        Output: dict matching piplab's config schema.
        Raises: ConfigValidationError when the form asks for something
        this engine's schema cannot express.
        """
        engine_config = _engine_config()
        if form.factor not in engine_config.COMPONENTS:
            raise ConfigValidationError(
                f"lab varies one of {', '.join(engine_config.COMPONENTS)}; "
                f"got {form.factor!r}."
            )
        if form.missingness_rates or form.missingness_mechanisms:
            raise ConfigValidationError(
                "The lab engine injects no missingness: it uses each dataset's "
                "natural missingness and compares imputation against row deletion. "
                "Remove the missingness rate and mechanism, or choose prepfx or b2."
            )
        baseline = {
            component: level
            for component, level in engine_config.BASELINES.items()
            if component != form.factor
        }
        return {
            "name": form.name,
            "vary": form.factor,
            "techniques": list(form.techniques),
            "baseline": baseline,
            "datasets": list(form.datasets),
            "models": list(form.models),
            "seed": form.seed,
            "evaluation": {"protocol": "kfold", "cv_k": form.k},
            "outputs_dir": "outputs/",
        }

    def run_command(self, config_path: Path) -> list[str]:
        """Build the argv that runs one lab config.

        Inputs: config_path - path to a YAML config.
        Output: argv matching this engine's README commands section.
        core/runner.py substitutes the engine's own .venv interpreter.
        """
        return ["python", "run_experiment.py", "--config", str(config_path)]

    def log_markers(self) -> dict:
        """Return the log vocabulary run_experiment.py prints.

        Every pattern is copied from a real print statement in
        pipeline-lab-engine/run_experiment.py.
        Inputs: none.
        Output: see engines/base.py::Engine.log_markers.
        """
        return {
            # print(f"Total runs: {total}")
            "expected": r"^Total runs:\s*(\d+)\s*$",
            "expected_label": "runs",
            # print(f"Run complete: dataset=..., ...") - one per combination
            "progress": r"^Run complete:\s*\S+",
            "progress_label": "runs completed",
            # print(f"Runs completed: {completed}")
            "success": r"^Runs completed:\s*(\d+)\s*$",
            # This CLI prints no non-fatal warnings of its own; a skipped
            # run is reported per-run and counted in "Runs skipped".
            "warning": r"^Run skipped:",
        }

    def read_achieved_missingness(self, output_dir, config: dict) -> dict | None:
        """Report that this engine measures no achieved missingness.

        It injects none: missingness is whatever each dataset naturally
        has, and the imputation component compares strategies for
        handling it. There is therefore no requested rate to confirm.
        Inputs: output_dir, config - unused.
        Output: always None.
        """
        return None

    def list_datasets(self) -> list[dict]:
        """Return the engine's registered datasets, from its own registry.

        Inputs: none.
        Output: list of dicts with the DatasetSpec fields.
        Raises: ImportError if the engine is not importable.
        """
        _engine_src()
        from piplab.datasets import REGISTRY

        return [
            {"id": spec.name, "source": spec.source, "ref": spec.ref, "task": spec.task}
            for spec in REGISTRY.values()
        ]

    def registered_ids(self) -> set[str]:
        """Return every dataset id this engine resolves."""
        _engine_src()
        from piplab.datasets import REGISTRY

        return set(REGISTRY)

    def register_dataset(self, csv_path: Path, dataset_id: str, target: str,
                         task: str, domain: str, source_name: str) -> dict:
        """Dataset upload is not wired to this engine yet.

        Raises: ConfigValidationError explaining the limit, rather than
        pretending to register and failing later at run time.
        """
        raise ConfigValidationError(
            "Uploading a dataset to the lab engine is not implemented yet. "
            "Its registry is code (src/piplab/datasets/loaders.py); upload "
            "support would need the same additive user-dataset hook the "
            "other two engines got. Use prepfx or b2 for uploads."
        )

    def extract_results(self, run_dir: Path, config: dict) -> Path | None:
        """Point at the run record this engine already wrote.

        Unlike b2 there is no MLflow indirection and no subprocess: the
        engine writes lab.db directly, so results are read from there.
        Inputs: run_dir - this run's directory; config - unused.
        Output: path to lab.db when it exists, else None.
        """
        for candidate in (Path(run_dir) / "outputs" / "lab.db", Path(run_dir) / "lab.db"):
            if candidate.is_file():
                return candidate
        return None

    def read_run_rows(self, db_path: Path, batch_id: str | None = None) -> list[dict]:
        """Read recorded runs out of a lab.db.

        Inputs: db_path - the run record; batch_id - optional filter.
        Output: list of row dicts, newest first.
        """
        _engine_src()
        from piplab.storage import open_db, read_runs

        with open_db(db_path) as connection:
            return read_runs(connection, batch_id=batch_id)
