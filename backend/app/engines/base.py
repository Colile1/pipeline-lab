# Engine protocol: the contract every target-repo adapter must satisfy.
from pathlib import Path
from typing import Protocol


class Engine(Protocol):
    """Read-only description of one target research codebase.

    Purpose: give the rest of this app a single, uniform way to ask an
    engine adapter for its paths, fixed technique/model lists, and run
    command, without any caller reading a target repo's files directly.
    Inputs: none (all members are adapter-supplied constants/methods).
    Output: the members below.
    """

    name: str
    root_path: Path
    configs_dir: Path
    outputs_dir: Path
    catalogue_path: Path
    user_datasets_path: Path

    def fixed_techniques(self, factor: str) -> list[str]:
        """Return the fixed technique list for one factor.

        Inputs: factor - "scaling" or "imputation".
        Output: list of technique names, in this engine's own fixed order.
        """
        ...

    def fixed_models(self) -> list[str]:
        """Return the fixed model list.

        Inputs: none.
        Output: list of model names, in this engine's own fixed order.
        """
        ...

    def valid_mechanisms(self) -> list[str]:
        """Return the missingness mechanisms this engine accepts.

        Inputs: none.
        Output: list of mechanism names, as this engine's own config
        validator spells them.
        """
        ...

    def build_config_dict(self, form) -> dict:
        """Translate a validated wizard form into this engine's config schema.

        Inputs: form - a core.form_schema.WizardForm.
        Output: a plain dict matching this engine's own YAML schema,
        field for field.
        Raises: core.errors.ConfigValidationError when the form is valid
        in general but unsupported by this engine's schema.
        """
        ...

    def run_command(self, config_path: Path) -> list[str]:
        """Build the subprocess argv that runs one config.

        Inputs: config_path - path to a YAML config for this engine.
        Output: argv list, e.g. ["python", "run_experiment.py", "--config", ...].
        """
        ...

    def log_markers(self) -> dict:
        """Return the log vocabulary this engine's run_experiment.py prints.

        Inputs: none.
        Output: dict with keys:
          "expected": regex with one capture group for the planned unit
            count, as printed near the start of a run;
          "expected_label": what that count counts, for the UI;
          "progress": regex matching one line per completed unit;
          "progress_label": what those lines count;
          "success": regex matching the line only a finished run prints;
          "warning": regex for lines that look alarming but are not
            failures (e.g. prepfx's non-fatal tracking warning).
        Every pattern is copied from that engine's own print statements —
        never guessed.
        """
        ...

    def read_achieved_missingness(self, output_dir, config: dict) -> dict | None:
        """Read the missingness this engine actually achieved, if it records one.

        Inputs: output_dir - this run's isolated output directory (None
        when the engine's schema has no outputs_dir); config - the config
        the run used.
        Output: dict with "requested", "achieved" (list of per-dataset
        values the engine itself measured) and "mechanism", or None when
        this engine never measures achieved missingness. Returning None
        is the honest answer for b2, which only echoes the requested rate
        back as an MLflow param — it must never be reported as measured.
        """
        ...

    def list_datasets(self) -> list[dict]:
        """Return this engine's registered datasets, in its own real fields.

        Inputs: none.
        Output: list of dicts, one per registered dataset, using exactly
        the fields this engine's own catalogue/registry records — never a
        dashboard-invented schema or a computed statistic this engine did
        not itself produce. User-uploaded datasets follow the engine's
        own design datasets.
        """
        ...

    def registered_ids(self) -> set[str]:
        """Return every dataset id this engine already resolves.

        Inputs: none.
        Output: set of ids/names an upload may not reuse.
        """
        ...

    def register_dataset(
        self, csv_path: Path, dataset_id: str, target: str, task: str,
        domain: str, source_name: str,
    ) -> dict:
        """Cache, characterise and register a validated CSV in this engine.

        Runs the engine's own code under the engine's own interpreter.
        Inputs: csv_path - validated CSV; dataset_id - new id; target -
        target column; task - "classification" or "regression"; domain -
        application domain; source_name - original filename.
        Output: {"registered": the engine's own record, "characteristics":
        values the engine itself computed}.
        Raises: core.errors.DatasetRegistrationError if the engine refuses.
        """
        ...

    def extract_results(self, run_dir: Path, config: dict) -> Path | None:
        """Ensure this run's results exist as a CSV under run_dir, if possible.

        Called once, right after a run is confirmed to have succeeded.
        For an engine whose run already wrote its own results file (prepfx,
        under its isolated output_dir), this is a no-op that returns None —
        api/results.py reads that file directly instead. For an engine that
        only logs to a shared store (b2, which logs every run to its one
        mlflow.db), this reads that run's own params/metrics back out by
        experiment name and writes them to run_dir/results.csv, so
        api/results.py can read a CSV for either engine without needing to
        know that b2 has no native per-run output file.
        Inputs: run_dir - this run's own directory (data/runs/<run_id>/);
        config - the config the run used (its "experiment"/"tracking.
        experiment_name" names the run's rows in whichever store the engine
        uses).
        Output: path to the written results.csv, or None when there was
        nothing to extract (prepfx) or nothing found (no matching rows).
        """
        ...
