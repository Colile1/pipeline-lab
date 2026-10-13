# b2 (B2) adapter: mirrors the Research_Impact_of_Preprocess design notes exactly.
import csv
from pathlib import Path

from ..core.errors import ConfigValidationError, ResultsExtractionError
from .registration import run_engine_script, run_register_script

# datasets/catalogue.csv columns that hold numbers; blank cells (e.g.
# n_classes/imbalance_ratio/var_ratio_log10 on regression rows) become None
# rather than an invented 0 or a NaN that json cannot serialise.
_NUMERIC_COLUMNS = {
    "openml_id", "n_rows", "n_features", "n_numeric", "n_categorical",
    "missing_pct", "n_classes", "imbalance_ratio", "var_ratio_log10",
    "mean_abs_corr",
}

REPO_ROOT = Path(__file__).resolve().parents[4] / "Artefact" / "Research_Impact_of_Preprocess"

FIXED_TECHNIQUES = {
    "scaling": ["standard", "minmax", "robust", "none"],
    "imputation": ["mean", "median", "knn"],
}
FIXED_MODELS = ["logreg", "random_forest", "svm", "gradient_boosting"]
# utils/config.py VALID_MECHANISMS — B2 has no mnar.
VALID_MECHANISMS = ["mcar", "mar"]
# utils/config.py VALID_FACTORS; B2 names the factors differently to prepfx.
FACTOR_NAMES = {"scaling": "scaler", "imputation": "imputer"}


class B2Engine:
    """Adapter for the b2 (B2) target repo.

    Purpose: expose B2's fixed design, paths, and run command to the rest
    of this app, matching the Research_Impact_of_Preprocess design notes
    and its configs/ examples field-for-field.
    Inputs: none (constructed with no arguments).
    Output: an Engine-shaped object (see engines/base.py).
    """

    name = "b2"
    root_path = REPO_ROOT
    configs_dir = REPO_ROOT / "configs"
    outputs_dir = REPO_ROOT / "results"
    catalogue_path = REPO_ROOT / "datasets" / "catalogue.csv"
    # data/registry.py USER_CATALOGUE_PATH, and data/loaders.py _DATASETS_DIR.
    user_datasets_path = REPO_ROOT / "datasets" / "user_catalogue.csv"
    datasets_dir = REPO_ROOT / "datasets"

    def fixed_techniques(self, factor: str) -> list[str]:
        """Return B2's fixed technique list for one factor.

        Inputs: factor - "scaling" or "imputation".
        Output: list of technique names; raises ValueError for any other factor.
        """
        if factor not in FIXED_TECHNIQUES:
            raise ValueError(f"b2 has no factor '{factor}'; expected one of {list(FIXED_TECHNIQUES)}")
        return list(FIXED_TECHNIQUES[factor])

    def fixed_models(self) -> list[str]:
        """Return B2's fixed model list.

        Inputs: none.
        Output: list of model names.
        """
        return list(FIXED_MODELS)

    def valid_mechanisms(self) -> list[str]:
        """Return the missingness mechanisms B2 accepts.

        Inputs: none.
        Output: list of mechanism names from B2's own
        utils/config.py VALID_MECHANISMS.
        """
        return list(VALID_MECHANISMS)

    def build_config_dict(self, form) -> dict:
        """Translate a wizard form into B2's own config schema.

        B2 names the factor `scaler`/`imputer`, takes an explicit
        `techniques` list, and sweeps missingness as two parallel lists
        that are valid only for the imputer factor.
        Inputs: form - a core.form_schema.WizardForm.
        Output: dict with B2's keys, ready to dump as YAML.
        Raises: ConfigValidationError when the form asks for something
        B2's schema cannot express.
        """
        config: dict = {
            "experiment": form.name,
            "factor": FACTOR_NAMES[form.factor],
            "techniques": list(form.techniques),
            "datasets": list(form.datasets),
            "models": list(form.models),
            "k": form.k,
            "seed": form.seed,
        }
        if form.factor == "imputation":
            config["missingness_rates"] = [float(r) for r in form.missingness_rates]
            config["missingness_mechanisms"] = self._mechanisms(form)
        return config

    def _mechanisms(self, form) -> list[str]:
        """Check the form's mechanisms against B2's accepted set.

        Inputs: form - a WizardForm with the imputation factor.
        Output: list of mechanism names.
        Raises: ConfigValidationError naming any mechanism B2 rejects.
        """
        bad = [m for m in form.missingness_mechanisms if m not in VALID_MECHANISMS]
        if bad:
            raise ConfigValidationError(
                f"Invalid missingness mechanism(s) for b2: {', '.join(bad)}. "
                f"Allowed: {', '.join(VALID_MECHANISMS)}."
            )
        return list(form.missingness_mechanisms)

    def run_command(self, config_path: Path) -> list[str]:
        """Build the argv that runs one B2 config.

        Inputs: config_path - path to a YAML config under configs_dir.
        Output: argv list matching `python run_experiment.py --config <path>`
        from the Research_Impact_of_Preprocess design notes (Commands section).
        """
        return ["python", "run_experiment.py", "--config", str(config_path)]

    def log_markers(self) -> dict:
        """Return the log vocabulary B2's run_experiment.py prints.

        Every pattern below is copied from a real print statement in
        Research_Impact_of_Preprocess/run_experiment.py.
        Inputs: none.
        Output: see engines/base.py::Engine.log_markers.
        """
        return {
            # print(f"Combinations: {total}")
            "expected": r"^Combinations:\s*(\d+)\s*$",
            "expected_label": "combinations",
            # print(f"Run complete: {desc}") — one per (technique, dataset,
            # model[, rate, mechanism]) combination.
            "progress": r"^Run complete:\s*\S+",
            "progress_label": "combinations completed",
            # print(f"Completed: {total} runs logged to MLflow experiment ...")
            "success": r"^Completed:\s*(\d+)\s+runs logged",
            # b2's run_experiment.py has no try/except at all, so it prints
            # no non-fatal warnings of its own; anything alarming in its log
            # is a real traceback.
            "warning": None,
        }

    def read_achieved_missingness(self, output_dir, config: dict) -> dict | None:
        """Report that B2 does not measure achieved missingness.

        B2 logs `missing_rate` to MLflow as a parameter — the requested
        rate echoed back, not a measured one — and inject_missing() returns
        only the frame, recording no realised rate anywhere readable. There
        is therefore nothing to compare, and reporting the requested rate
        as if it were achieved would be a false confirmation.
        Inputs: output_dir - always None for b2; config - unused.
        Output: always None.
        """
        return None

    def list_datasets(self) -> list[dict]:
        """Return B2's registered datasets exactly as datasets/catalogue.csv records them.

        User-uploaded datasets (datasets/user_catalogue.csv, blank
        openml_id) follow the generated catalogue's rows, in the same columns.
        Inputs: none.
        Output: list of dicts, one per catalogue row, with numeric fields
        parsed to int/float and blank cells (e.g. n_classes on a
        regression row) as None.
        Raises: FileNotFoundError if the catalogue has not been created yet.
        """
        if not self.catalogue_path.is_file():
            raise FileNotFoundError(f"B2 catalogue not found: {self.catalogue_path}")
        rows = self._read_rows(self.catalogue_path)
        columns = list(rows[0]) if rows else []
        user_rows = [{c: row[c] for c in columns} for row in self._read_rows(self.user_datasets_path)]
        return [self._parse_catalogue_row(row) for row in [*rows, *user_rows]]

    def registered_ids(self) -> set[str]:
        """Return every dataset name B2 already resolves.

        Inputs: none.
        Output: names in the generated catalogue (B2's REGISTRY) and in
        the user catalogue.
        """
        paths = (self.catalogue_path, self.user_datasets_path)
        return {row["dataset"] for path in paths for row in self._read_rows(path)}

    def register_dataset(
        self, csv_path: Path, dataset_id: str, target: str, task: str,
        domain: str, source_name: str,
    ) -> dict:
        """Register a validated CSV with B2, using B2's own code.

        Inputs: csv_path - validated CSV; dataset_id - new dataset name;
        target - target column; task - task type; domain - catalogue
        domain; source_name - unused (B2's catalogue records no filename).
        Output: {"registered": the user-catalogue row, "characteristics":
        the catalogue columns B2's own _dataset_properties computed}.
        Raises: DatasetRegistrationError if B2's registration fails.
        """
        script = Path(__file__).resolve().parent / "b2" / "register_dataset.py"
        return run_register_script(self.root_path, script, {
            "src": self.root_path / "src", "csv": csv_path, "name": dataset_id,
            "target": target, "task": task, "domain": domain,
            "user-catalogue": self.user_datasets_path, "datasets-dir": self.datasets_dir,
        })

    def extract_results(self, run_dir: Path, config: dict) -> Path | None:
        """Read a run's own experiment back out of B2's shared mlflow.db.

        B2 logs every run's params/metrics into one mlflow.db shared across
        all experiments, namespaced by the config's "experiment" name — the
        same name this run's wizard form supplied. Reads that experiment's
        rows with B2's own mlflow client, under B2's own interpreter, and
        writes them to run_dir/results.csv.
        Inputs: run_dir - this run's own directory; config - the config the
        run used (its "experiment" key names the MLflow experiment).
        Output: path to the written CSV, or None if the experiment has no
        logged runs (e.g. the run failed before logging anything).
        Raises: ResultsExtractionError if B2's own extraction script fails.
        """
        script = Path(__file__).resolve().parent / "b2" / "extract_results.py"
        out_path = Path(run_dir) / "results.csv"
        result = run_engine_script(
            self.root_path, script,
            {"src": self.root_path / "src", "experiment": config.get("experiment", ""), "out": out_path},
            ResultsExtractionError, "Result extraction",
        )
        return Path(result["results_path"]) if result.get("results_path") else None

    def _read_rows(self, path: Path) -> list[dict]:
        """Read a catalogue-style CSV into raw row dicts.

        Inputs: path - the CSV to read.
        Output: list of raw string dicts; empty if the file does not exist.
        """
        if not path.is_file():
            return []
        with path.open("r", newline="", encoding="utf-8") as fh:
            return list(csv.DictReader(fh))

    def _parse_catalogue_row(self, row: dict) -> dict:
        """Parse one raw CSV row into typed values.

        Inputs: row - dict of column name -> raw string from the CSV.
        Output: dict with numeric columns as int/float/None, others as-is.
        """
        parsed: dict = {}
        for key, raw in row.items():
            if key not in _NUMERIC_COLUMNS:
                parsed[key] = raw
                continue
            if raw is None or raw.strip() == "":
                parsed[key] = None
            elif raw.strip().lstrip("-").isdigit():
                parsed[key] = int(raw)
            else:
                parsed[key] = float(raw)
        return parsed
