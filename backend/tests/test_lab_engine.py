# Confirms the lab adapter reports the ENGINE's own fixed lists rather
# than a copy, builds the engine's config schema, and keys its log
# markers on run_experiment.py's real print statements.
#
# The "import, don't copy" property is the point of several of these
# tests: the dashboard's PrepfxEngine once claimed the model key
# "logreg" when prepfx's own key is "logistic", and that bug survived
# three build steps because nothing executed a real run.
import re

import pytest

from app.core.errors import ConfigValidationError
from app.core.form_schema import FACTORS, normalise_form, supported_factors
from app.engines.lab import LabEngine
from app.engines.registry import ENGINES, get_engine


@pytest.fixture
def lab():
    return LabEngine()


def form(**overrides) -> dict:
    base = {
        "name": "lab_test", "factor": "selection",
        "techniques": ["none", "mutual_info"],
        "datasets": ["iris", "wine"], "models": ["logreg"],
        "k": 10, "seed": 671,
    }
    base.update(overrides)
    return base


# --- registered alongside the other two -----------------------------------

def test_lab_is_registered_without_disturbing_the_others():
    assert sorted(ENGINES) == ["b2", "lab", "prepfx"]
    assert isinstance(get_engine("lab"), LabEngine)


def test_the_engine_repo_is_found_beside_the_research_repos(lab):
    assert lab.root_path.name == "pipeline-lab-engine"
    assert lab.root_path.is_dir(), "the engine must sit beside this app"
    assert (lab.root_path / "run_experiment.py").is_file()


# --- lists come FROM the engine, not a copy -------------------------------

def test_fixed_lists_match_the_engines_own_constants(lab):
    """If these ever diverge, the UI has drifted from the engine."""
    import sys
    sys.path.insert(0, str(lab.root_path / "src"))
    from piplab.config import BASELINES, COMPONENTS, MODELS, TECHNIQUES

    assert lab.factors == COMPONENTS
    assert lab.fixed_models() == list(MODELS)
    assert lab.baselines() == dict(BASELINES)
    for component in COMPONENTS:
        assert lab.fixed_techniques(component) == list(TECHNIQUES[component])


def test_the_five_ofat_components_are_exposed(lab):
    assert set(lab.factors) == {"encoding", "imputation", "scaling", "selection", "tuning"}


def test_chapter1_baselines_are_first_in_each_technique_list(lab):
    """The composer pre-fills its baseline column from position 0."""
    baselines = lab.baselines()
    for component, baseline in baselines.items():
        assert lab.fixed_techniques(component)[0] == baseline


def test_selection_and_tuning_levels_are_the_new_capability(lab):
    """Neither exists in prepfx or b2 at all."""
    assert lab.fixed_techniques("selection") == ["none", "chi2", "mutual_info", "rfe", "lasso"]
    assert lab.fixed_techniques("tuning") == ["none", "random", "grid", "bayesian"]


def test_row_deletion_is_the_imputation_baseline(lab):
    assert lab.fixed_techniques("imputation")[0] == "drop_rows"


def test_an_unknown_component_is_rejected_by_name(lab):
    with pytest.raises(ValueError, match="bogus"):
        lab.fixed_techniques("bogus")


# --- six factors where the originals have two -----------------------------

def test_the_validator_asks_the_engine_rather_than_assuming_two_factors(lab):
    from app.engines.b2 import B2Engine

    assert supported_factors(lab) == lab.factors
    # The original engines keep the two-factor default untouched.
    assert supported_factors(B2Engine()) == FACTORS == ("scaling", "imputation")


def test_a_lab_only_factor_validates_for_lab(lab):
    validated = normalise_form(lab, form(factor="tuning", techniques=["none", "grid"]))
    assert validated.factor == "tuning"


def test_a_lab_only_factor_is_still_refused_for_b2():
    """The original engines must not silently gain components."""
    from app.engines.b2 import B2Engine

    with pytest.raises(ConfigValidationError, match="factor"):
        normalise_form(B2Engine(), form(factor="selection", techniques=["none"]))


# --- the engine's config schema: a third shape ----------------------------

def test_build_config_uses_vary_and_baseline_not_arm_or_factor(lab):
    config = lab.build_config_dict(normalise_form(lab, form()))
    assert config["vary"] == "selection"
    assert config["techniques"] == ["none", "mutual_info"]
    # prepfx's key is `arm`, b2's is `factor`; this engine uses neither.
    assert "arm" not in config and "factor" not in config


def test_the_baseline_holds_every_component_except_the_varied_one(lab):
    config = lab.build_config_dict(normalise_form(lab, form(factor="scaling",
                                                            techniques=["none", "standard"])))
    assert "scaling" not in config["baseline"]
    assert config["baseline"] == {
        "encoding": "onehot", "imputation": "drop_rows",
        "selection": "none", "tuning": "none",
    }


def test_k_reaches_the_engines_evaluation_block(lab):
    config = lab.build_config_dict(normalise_form(lab, form(k=10)))
    assert config["evaluation"] == {"protocol": "kfold", "cv_k": 10}


def test_the_generated_config_is_accepted_by_the_engines_own_validator(lab):
    """The strongest check: the engine itself must parse what we emit."""
    import sys
    sys.path.insert(0, str(lab.root_path / "src"))
    from piplab.config import parse_config

    config = lab.build_config_dict(normalise_form(lab, form()))
    parsed = parse_config(config)
    assert parsed.vary == "selection"
    assert parsed.run_count() == 2 * 1 * 2  # datasets x models x techniques
    assert parsed.evaluation.cv_k == 10


def test_missingness_is_refused_with_an_explanation(lab):
    """This engine injects none, so silently ignoring the field would
    misrepresent what ran."""
    wizard = normalise_form(lab, form(factor="imputation",
                                      techniques=["drop_rows", "median"],
                                      missingness_rates=[0.15],
                                      missingness_mechanisms=["mcar"]))
    with pytest.raises(ConfigValidationError, match="injects no missingness"):
        lab.build_config_dict(wizard)


def test_no_mechanism_control_is_offered(lab):
    assert lab.valid_mechanisms() == []


def test_achieved_missingness_is_none_because_none_is_injected(lab):
    assert lab.read_achieved_missingness(None, {}) is None


# --- log markers match the real CLI ---------------------------------------

def test_log_markers_match_run_experiment_py_s_actual_output(lab):
    """Patterns are checked against the CLI's real print statements."""
    markers = lab.log_markers()
    source = (lab.root_path / "run_experiment.py").read_text(encoding="utf-8")
    # Each marker must correspond to a print in the engine's CLI.
    assert 'print(f"Total runs: {total}")' in source
    assert 'print(f"Runs completed: {completed}")' in source
    assert "Run complete: dataset=" in source
    assert "Run skipped: dataset=" in source

    assert re.match(markers["expected"], "Total runs: 120")
    assert re.match(markers["progress"], "Run complete: dataset=iris, scaling=none, model=logreg")
    assert re.match(markers["success"], "Runs completed: 120")
    assert re.match(markers["warning"], "Run skipped: dataset=iris, tuning=grid, model=svm (reason)")


def test_expected_and_success_markers_capture_the_same_unit(lab):
    """Both count runs, so "4 of 4" is meaningful rather than mixing units."""
    markers = lab.log_markers()
    assert re.match(markers["expected"], "Total runs: 4").group(1) == "4"
    assert re.match(markers["success"], "Runs completed: 4").group(1) == "4"
    assert markers["expected_label"] == "runs"


def test_run_command_matches_the_engines_documented_invocation(lab):
    from pathlib import Path

    # str(Path) uses the platform separator, so compare against that
    # rather than a forward-slash literal.
    config = Path("configs/smoke.yaml")
    assert lab.run_command(config) == [
        "python", "run_experiment.py", "--config", str(config),
    ]


# --- datasets and the limits that are stated plainly ----------------------

def test_datasets_come_from_the_engines_registry(lab):
    """The adapter must mirror the engine's registry, not restate it.

    Counts the engine's own registry rather than a literal: the list
    grows as datasets are added (cpu_small and kin8nm were added to
    lift the regression arm over its power bar), and a hardcoded number
    would fail for a change that is entirely correct.
    """
    datasets = lab.list_datasets()
    ids = {d["id"] for d in datasets}
    assert ids == lab.registered_ids()
    assert len(datasets) == len(lab.registered_ids())
    assert len(datasets) >= 20, "Chapter 1 asks for at least 20 datasets"
    assert {"iris", "wine", "adult", "house_16H"} <= ids


def test_upload_is_refused_with_a_usable_explanation(lab):
    """Better than pretending to register and failing at run time."""
    from pathlib import Path

    with pytest.raises(ConfigValidationError, match="not implemented yet"):
        lab.register_dataset(Path("x.csv"), "new", "target", "classification", "d", "x.csv")


def test_extract_results_points_at_the_engines_own_database(lab, tmp_path):
    """No MLflow indirection here: the engine writes lab.db directly."""
    assert lab.extract_results(tmp_path, {}) is None
    outputs = tmp_path / "outputs"
    outputs.mkdir()
    (outputs / "lab.db").write_bytes(b"")
    assert lab.extract_results(tmp_path, {}) == outputs / "lab.db"


# --- the real proof: the dashboard's own machinery runs this engine ------

def test_the_dashboard_runner_launches_a_real_lab_run(tmp_path, monkeypatch):
    """Step 7's point: reuse, not reimplementation.

    core/runner.py and core/run_status.py are unchanged from the
    original build; this asserts they drive a third engine correctly,
    including parsing its log markers into a progress count.
    """
    import time

    from app.core import runner as runner_module
    from app.core.config_builder import build_config_dict
    from app.core.run_status import SUCCEEDED, summarise_validation

    monkeypatch.setattr(runner_module, "RUNS_DIR", tmp_path / "runs")
    lab = LabEngine()
    config = build_config_dict(lab, form(
        factor="scaling", techniques=["none", "standard"],
        datasets=["iris", "wine"], models=["logreg"], k=3,
    ))
    handle = runner_module.start_run(lab, config, "adapter_proof")

    deadline = time.monotonic() + 300
    while time.monotonic() < deadline and handle.poll() is None:
        time.sleep(0.5)
    assert handle.poll() is not None, "the lab run did not finish in time"

    summary = summarise_validation(handle, lab)
    assert summary.state == SUCCEEDED, summary.notes + summary.errors
    assert summary.exit_code == 0
    # The log markers must parse into a real progress count.
    assert summary.expected == 4
    assert summary.completed == 4
    assert summary.errors == []
    # The engine wrote its run record inside the isolated run directory.
    assert any(name.endswith("lab.db") for name in summary.outputs)
