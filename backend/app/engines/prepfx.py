# prepfx (B1) adapter: mirrors the preprocessing-effects-framework design notes exactly.
import csv
import sys
from pathlib import Path

from ..core.errors import ConfigValidationError
from .registration import run_register_script

REPO_ROOT = Path(__file__).resolve().parents[4] / "preprocessing-effects-framework"

FIXED_TECHNIQUES = {
    "scaling": ["standard", "minmax", "robust", "none"],
    "imputation": ["mean", "median", "knn"],
}
# src/prepfx/pipelines/models.py MODELS keys. Note: prepfx's key is
# "logistic", not "logreg" — b2 uses "logreg" for the same model. The two
# engines name this model differently; never assume the lists match.
FIXED_MODELS = ["logistic", "svm", "random_forest", "gradient_boosting"]
# src/prepfx/common/config.py VALID_MECHANISMS.
VALID_MECHANISMS = ["mcar", "mar", "mnar"]
# src/prepfx/common/config.py: outputs_dir is required and every real
# config in configs/ sets it to this value.
OUTPUTS_DIR_VALUE = "outputs/"


class PrepfxEngine:
    """Adapter for the prepfx (B1) target repo.

    Purpose: expose prepfx's fixed design, paths, and run command to the
    rest of this app, matching the preprocessing-effects-framework design notes
    and its configs/ examples field-for-field.
    Inputs: none (constructed with no arguments).
    Output: an Engine-shaped object (see engines/base.py).
    """

    name = "prepfx"
    root_path = REPO_ROOT
    configs_dir = REPO_ROOT / "configs"
    outputs_dir = REPO_ROOT / "outputs"
    catalogue_path = REPO_ROOT / "src" / "prepfx" / "datasets" / "registry.py"
    # registry.py USER_DATASETS_PATH, and the cache dir run_experiment.py
    # passes to fetch() ("data/raw", relative to the repo root).
    user_datasets_path = REPO_ROOT / "data" / "user_datasets.csv"
    cache_dir = REPO_ROOT / "data" / "raw"

    def fixed_techniques(self, factor: str) -> list[str]:
        """Return prepfx's fixed technique list for one factor.

        Inputs: factor - "scaling" or "imputation".
        Output: list of technique names; raises ValueError for any other factor.
        """
        if factor not in FIXED_TECHNIQUES:
            raise ValueError(f"prepfx has no factor '{factor}'; expected one of {list(FIXED_TECHNIQUES)}")
        return list(FIXED_TECHNIQUES[factor])

    def fixed_models(self) -> list[str]:
        """Return prepfx's fixed model list.

        Inputs: none.
        Output: list of model names.
        """
        return list(FIXED_MODELS)

    def valid_mechanisms(self) -> list[str]:
        """Return the missingness mechanisms prepfx accepts.

        Inputs: none.
        Output: list of mechanism names from prepfx's own
        src/prepfx/common/config.py VALID_MECHANISMS.
        """
        return list(VALID_MECHANISMS)

    def build_config_dict(self, form) -> dict:
        """Translate a wizard form into prepfx's own config schema.

        prepfx names the factor `arm`, sweeps that arm's full fixed
        technique list itself (there is no `techniques` field), and takes
        a single missingness proportion/mechanism pair rather than lists.
        Inputs: form - a core.form_schema.WizardForm.
        Output: dict with prepfx's keys, ready to dump as YAML.
        Raises: ConfigValidationError when the form asks for something
        prepfx's schema cannot express.
        """
        self._reject_technique_subset(form)
        config: dict = {
            "arm": form.factor,
            "seed": form.seed,
            "cv": {"k": form.k},
            "datasets": list(form.datasets),
        }
        if form.factor == "imputation":
            config["missingness"] = self._single_missingness(form)
        config["models"] = list(form.models)
        config["tracking"] = {"experiment_name": form.name}
        config["outputs_dir"] = OUTPUTS_DIR_VALUE
        return config

    def _reject_technique_subset(self, form) -> None:
        """Reject a partial technique list, which prepfx cannot express.

        Inputs: form - a WizardForm.
        Output: None.
        Raises: ConfigValidationError if the chosen techniques are not the
        arm's complete fixed list.
        """
        expected = self.fixed_techniques(form.factor)
        if sorted(form.techniques) != sorted(expected):
            raise ConfigValidationError(
                f"prepfx runs the whole {form.factor} arm and has no per-technique "
                f"setting, so all of {', '.join(expected)} must be selected. "
                "Choose the b2 engine to run a subset."
            )

    def _single_missingness(self, form) -> dict:
        """Collapse the form's missingness lists into prepfx's single pair.

        Inputs: form - a WizardForm with the imputation factor.
        Output: dict with prepfx's proportion/mechanism keys.
        Raises: ConfigValidationError on more than one rate or mechanism,
        or on a mechanism prepfx does not accept.
        """
        if len(form.missingness_rates) != 1 or len(form.missingness_mechanisms) != 1:
            raise ConfigValidationError(
                "prepfx runs one missingness setting per config, so choose exactly "
                "one rate and one mechanism. Choose the b2 engine to sweep several."
            )
        mechanism = form.missingness_mechanisms[0]
        if mechanism not in VALID_MECHANISMS:
            raise ConfigValidationError(
                f"Invalid missingness mechanism for prepfx: {mechanism}. "
                f"Allowed: {', '.join(VALID_MECHANISMS)}."
            )
        return {"proportion": form.missingness_rates[0], "mechanism": mechanism}

    def run_command(self, config_path: Path) -> list[str]:
        """Build the argv that runs one prepfx config.

        Inputs: config_path - path to a YAML config under configs_dir.
        Output: argv list matching `python run_experiment.py --config <path>`
        from the preprocessing-effects-framework design notes (Commands section).
        """
        return ["python", "run_experiment.py", "--config", str(config_path)]

    def log_markers(self) -> dict:
        """Return the log vocabulary prepfx's run_experiment.py prints.

        Every pattern below is copied from a real print statement in
        preprocessing-effects-framework/run_experiment.py and checked
        against a real run log (outputs/imputation_run.log).
        Inputs: none.
        Output: see engines/base.py::Engine.log_markers.
        """
        return {
            # print(f"Grid configurations: {grid}") — matches the count that
            # "Configurations evaluated" reports at the end, so the two are
            # directly comparable. "Total fold fits" is grid * k, a different
            # unit, and is deliberately not used as the expected count.
            "expected": r"^Grid configurations:\s*(\d+)\s*$",
            "expected_label": "grid configurations",
            # print(f"Dataset done: {ds_id} ({task})") — one per dataset, so
            # progress is counted in datasets, not configurations.
            "progress": r"^Dataset done:\s*\S+",
            "progress_label": "datasets completed",
            # print(f"Configurations evaluated: {len(summaries)}")
            "success": r"^Configurations evaluated:\s*(\d+)\s*$",
            # print(f"Tracking warning: could not start experiment: {exc}") —
            # caught and non-fatal; the run continues without MLflow.
            "warning": r"^Tracking warning:",
        }

    def read_achieved_missingness(self, output_dir, config: dict) -> dict | None:
        """Read the missingness prepfx actually measured, from its own catalogue.

        prepfx's characterise() records the realised missing_proportion and
        missing_mechanism per dataset into
        <outputs_dir>/results/<arm>_catalogue.csv. Those are measured
        values, so they can be compared against what the config requested.
        Inputs: output_dir - this run's isolated outputs directory;
        config - the config the run used.
        Output: dict with requested/achieved/mechanism, or None when this
        was not an imputation run or the catalogue is not there.
        """
        requested = (config.get("missingness") or {}).get("proportion")
        if requested is None or output_dir is None:
            return None
        catalogue = Path(output_dir) / "results" / f"{config.get('arm')}_catalogue.csv"
        if not catalogue.is_file():
            return None
        achieved, mechanisms = [], set()
        with catalogue.open("r", newline="", encoding="utf-8") as fh:
            for row in csv.DictReader(fh):
                value = (row.get("missing_proportion") or "").strip()
                if value:
                    achieved.append({"dataset": row.get("dataset_id"), "proportion": float(value)})
                mechanism = (row.get("missing_mechanism") or "").strip()
                if mechanism:
                    mechanisms.add(mechanism)
        if not achieved:
            return None
        return {
            "requested": float(requested),
            "achieved": achieved,
            "mechanism": sorted(mechanisms),
            "source": str(catalogue),
        }

    def list_datasets(self) -> list[dict]:
        """Return prepfx's registered datasets from its own registry module.

        prepfx has no precomputed characteristics catalogue (those are a
        per-run output, under outputs/results/*_catalogue.csv); its
        registered dataset list is the DATASETS dict in
        src/prepfx/datasets/registry.py — the 24-dataset design, not the
        optional large/monster sets outside the registered design —
        followed by any user-uploaded datasets (source "local").
        Inputs: none.
        Output: list of dicts, one per dataset, with the DatasetSpec
        fields (id, source, ref, task, target, licence).
        Raises: ImportError if prepfx's package cannot be found under
        root_path / "src".
        """
        registry = self._registry()
        datasets = {**registry.DATASETS, **registry.load_user_datasets(self.user_datasets_path)}
        return [
            {
                "id": spec.id,
                "source": spec.source,
                "ref": spec.ref,
                "task": spec.task,
                "target": spec.target,
                "licence": spec.licence,
            }
            for spec in datasets.values()
        ]

    def registered_ids(self) -> set[str]:
        """Return every dataset id prepfx already resolves.

        Inputs: none.
        Output: ids of the registered design, the optional large/monster
        sets, and existing user uploads.
        """
        registry = self._registry()
        return {
            *registry.DATASETS, *registry.LARGE_DATASETS, *registry.MONSTER_DATASETS,
            *registry.load_user_datasets(self.user_datasets_path),
        }

    def register_dataset(
        self, csv_path: Path, dataset_id: str, target: str, task: str,
        domain: str, source_name: str,
    ) -> dict:
        """Register a validated CSV with prepfx, using prepfx's own code.

        Inputs: csv_path - validated CSV; dataset_id - new id; target -
        target column; task - task type; domain - unused (DatasetSpec has
        no domain field); source_name - original filename, stored as ref.
        Output: {"registered": DatasetSpec fields, "characteristics":
        prepfx's own DatasetProfile for the dataset}.
        Raises: DatasetRegistrationError if prepfx's registration fails.
        """
        script = Path(__file__).resolve().parent / "prepfx" / "register_dataset.py"
        return run_register_script(self.root_path, script, {
            "src": self.root_path / "src", "csv": csv_path, "id": dataset_id,
            "target": target, "task": task, "source-name": source_name or "upload.csv",
            "user-datasets": self.user_datasets_path, "cache-dir": self.cache_dir,
        })

    def _registry(self):
        """Import and return prepfx's own registry module.

        Inputs: none.
        Output: the prepfx.datasets.registry module.
        Raises: ImportError if prepfx's src/ package is not importable.
        """
        src_dir = str(self.root_path / "src")
        if src_dir not in sys.path:
            sys.path.insert(0, src_dir)
        from prepfx.datasets import registry

        return registry

    def extract_results(self, run_dir: Path, config: dict) -> Path | None:
        """No-op: prepfx already writes its own results CSVs.

        A prepfx run's tables/{arm}_summary.csv and {arm}_verdicts.csv live
        under the run's isolated output_dir, written by run_experiment.py
        itself — nothing needs extracting from a separate store.
        Inputs: run_dir - unused; config - unused.
        Output: always None.
        """
        return None
