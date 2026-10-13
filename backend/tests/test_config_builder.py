# Confirms a wizard form becomes a config structurally identical to a real
# example in each engine's own configs/ folder, per build-order.md step 4.
import pytest
import yaml

from app.core.config_builder import build_config, build_config_dict, config_filename
from app.core.errors import ConfigValidationError
from app.engines.b2 import B2Engine
from app.engines.prepfx import PrepfxEngine

B2_DATASETS = [
    "credit-g", "adult", "bank-marketing", "wdbc", "heart-c",
    "credit-approval", "colic", "house_16H", "abalone", "concrete",
    "energy-efficiency", "autoMpg",
]
B2_IMPUTATION_DATASETS = [
    "bank-marketing", "wdbc", "house_16H", "abalone", "concrete",
    "energy-efficiency",
]
B2_MODELS = ["logreg", "random_forest", "svm", "gradient_boosting"]
# prepfx's pipelines/models.py key is "logistic", not b2's "logreg" — the
# two engines name this model differently.
PREPFX_MODELS = ["logistic", "svm", "random_forest", "gradient_boosting"]
PREPFX_IMPUTATION_DATASETS = ["iris", "wine", "breast_cancer", "digits"]


def real_config(engine, filename):
    """Load a real example config from the target engine's own configs/ folder."""
    path = engine.configs_dir / filename
    assert path.is_file(), f"missing real example config: {path}"
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def test_b2_scaling_form_matches_the_real_scaling_config():
    engine = B2Engine()
    built = build_config_dict(engine, {
        "name": "scaling",
        "factor": "scaling",
        "techniques": ["standard", "minmax", "robust", "none"],
        "datasets": B2_DATASETS,
        "models": B2_MODELS,
        "k": 10,
        "seed": 671,
    })
    assert built == real_config(engine, "scaling.yaml")


def test_b2_imputation_form_matches_the_real_imputation_config():
    engine = B2Engine()
    built = build_config_dict(engine, {
        "name": "imputation",
        "factor": "imputation",
        "techniques": ["mean", "median", "knn"],
        "datasets": B2_IMPUTATION_DATASETS,
        "models": B2_MODELS,
        "k": 10,
        "seed": 671,
        "missingness_rates": [0.05, 0.15, 0.30],
        "missingness_mechanisms": ["mcar", "mar"],
    })
    assert built == real_config(engine, "imputation.yaml")


def test_prepfx_imputation_form_matches_the_real_smoke_imputation_config():
    engine = PrepfxEngine()
    built = build_config_dict(engine, {
        "name": "smoke_imputation",
        "factor": "imputation",
        "techniques": ["mean", "median", "knn"],
        "datasets": PREPFX_IMPUTATION_DATASETS,
        "models": PREPFX_MODELS,
        "k": 3,
        "seed": 20260702,
        "missingness_rates": [0.15],
        "missingness_mechanisms": ["mcar"],
    })
    expected = real_config(engine, "smoke_imputation.yaml")
    # The real file omits models, which prepfx treats as "all registered
    # models"; the wizard always states them, so compare the rest field-wise.
    assert built["models"] == PREPFX_MODELS
    assert {k: v for k, v in built.items() if k != "models"} == expected


def test_prepfx_scaling_form_matches_the_real_smoke_config():
    engine = PrepfxEngine()
    built = build_config_dict(engine, {
        "name": "smoke",
        "factor": "scaling",
        "techniques": ["standard", "minmax", "robust", "none"],
        "datasets": ["iris", "wine"],
        "models": PREPFX_MODELS,
        "k": 3,
        "seed": 20260702,
    })
    expected = real_config(engine, "smoke.yaml")
    assert {k: v for k, v in built.items() if k != "models"} == expected
    assert "missingness" not in built


def test_prepfx_uses_its_own_field_names_not_b2s():
    engine = PrepfxEngine()
    built = build_config_dict(engine, {
        "name": "arm_check",
        "factor": "scaling",
        "techniques": ["standard", "minmax", "robust", "none"],
        "datasets": ["iris"],
        "models": ["logistic"],
        "k": 5,
        "seed": 20260702,
    })
    assert built["arm"] == "scaling"
    assert "factor" not in built and "techniques" not in built


def test_b2_renames_the_factor_to_its_own_vocabulary():
    engine = B2Engine()
    built = build_config_dict(engine, {
        "name": "f",
        "factor": "imputation",
        "techniques": ["mean"],
        "datasets": ["wdbc"],
        "models": ["logreg"],
        "k": 10,
        "seed": 671,
        "missingness_rates": [0.15],
        "missingness_mechanisms": ["mcar"],
    })
    assert built["factor"] == "imputer"


# --- rejected combinations -------------------------------------------------

def test_rejects_a_technique_outside_the_factors_fixed_list():
    engine = B2Engine()
    with pytest.raises(ConfigValidationError, match="mean"):
        build_config_dict(engine, {
            "name": "bad", "factor": "scaling",
            "techniques": ["standard", "mean"],
            "datasets": ["wdbc"], "models": ["logreg"], "k": 10, "seed": 671,
        })


def test_rejects_a_model_outside_the_fixed_list():
    engine = B2Engine()
    with pytest.raises(ConfigValidationError, match="xgboost"):
        build_config_dict(engine, {
            "name": "bad", "factor": "scaling", "techniques": ["standard"],
            "datasets": ["wdbc"], "models": ["xgboost"], "k": 10, "seed": 671,
        })


def test_rejects_missingness_on_the_scaling_factor():
    engine = B2Engine()
    with pytest.raises(ConfigValidationError, match="imputation factor"):
        build_config_dict(engine, {
            "name": "bad", "factor": "scaling", "techniques": ["standard"],
            "datasets": ["wdbc"], "models": ["logreg"], "k": 10, "seed": 671,
            "missingness_rates": [0.15], "missingness_mechanisms": ["mcar"],
        })


def test_rejects_mnar_for_b2_which_does_not_support_it():
    engine = B2Engine()
    with pytest.raises(ConfigValidationError, match="mnar"):
        build_config_dict(engine, {
            "name": "bad", "factor": "imputation", "techniques": ["mean"],
            "datasets": ["wdbc"], "models": ["logreg"], "k": 10, "seed": 671,
            "missingness_rates": [0.15], "missingness_mechanisms": ["mnar"],
        })


def test_prepfx_accepts_mnar_which_its_own_validator_allows():
    engine = PrepfxEngine()
    built = build_config_dict(engine, {
        "name": "mnar_run", "factor": "imputation",
        "techniques": ["mean", "median", "knn"],
        "datasets": ["iris"], "models": ["logistic"], "k": 5, "seed": 20260702,
        "missingness_rates": [0.15], "missingness_mechanisms": ["mnar"],
    })
    assert built["missingness"] == {"proportion": 0.15, "mechanism": "mnar"}


def test_rejects_a_missingness_rate_outside_zero_to_one():
    engine = B2Engine()
    with pytest.raises(ConfigValidationError, match="fraction"):
        build_config_dict(engine, {
            "name": "bad", "factor": "imputation", "techniques": ["mean"],
            "datasets": ["wdbc"], "models": ["logreg"], "k": 10, "seed": 671,
            "missingness_rates": [15], "missingness_mechanisms": ["mcar"],
        })


def test_rejects_imputation_without_both_missingness_fields():
    engine = B2Engine()
    with pytest.raises(ConfigValidationError, match="requires both"):
        build_config_dict(engine, {
            "name": "bad", "factor": "imputation", "techniques": ["mean"],
            "datasets": ["wdbc"], "models": ["logreg"], "k": 10, "seed": 671,
            "missingness_rates": [0.15],
        })


def test_rejects_k_below_two():
    engine = B2Engine()
    with pytest.raises(ConfigValidationError, match="at least 2"):
        build_config_dict(engine, {
            "name": "bad", "factor": "scaling", "techniques": ["standard"],
            "datasets": ["wdbc"], "models": ["logreg"], "k": 1, "seed": 671,
        })


def test_rejects_an_unknown_factor():
    engine = B2Engine()
    with pytest.raises(ConfigValidationError, match="factor"):
        build_config_dict(engine, {
            "name": "bad", "factor": "encoding", "techniques": ["standard"],
            "datasets": ["wdbc"], "models": ["logreg"], "k": 10, "seed": 671,
        })


def test_rejects_an_unknown_form_field():
    engine = B2Engine()
    with pytest.raises(ConfigValidationError, match="metric"):
        build_config_dict(engine, {
            "name": "bad", "factor": "scaling", "techniques": ["standard"],
            "datasets": ["wdbc"], "models": ["logreg"], "k": 10, "seed": 671,
            "metric": "roc_auc",
        })


def test_rejects_a_technique_subset_for_prepfx_which_sweeps_whole_arms():
    engine = PrepfxEngine()
    with pytest.raises(ConfigValidationError, match="whole scaling arm"):
        build_config_dict(engine, {
            "name": "bad", "factor": "scaling", "techniques": ["standard"],
            "datasets": ["iris"], "models": ["logistic"], "k": 5, "seed": 20260702,
        })


def test_rejects_multiple_missingness_rates_for_prepfx():
    engine = PrepfxEngine()
    with pytest.raises(ConfigValidationError, match="exactly"):
        build_config_dict(engine, {
            "name": "bad", "factor": "imputation",
            "techniques": ["mean", "median", "knn"],
            "datasets": ["iris"], "models": ["logistic"], "k": 5, "seed": 20260702,
            "missingness_rates": [0.05, 0.15], "missingness_mechanisms": ["mcar"],
        })


def test_rejects_an_empty_dataset_list():
    engine = B2Engine()
    with pytest.raises(ConfigValidationError, match="datasets"):
        build_config_dict(engine, {
            "name": "bad", "factor": "scaling", "techniques": ["standard"],
            "datasets": [], "models": ["logreg"], "k": 10, "seed": 671,
        })


# --- writing ---------------------------------------------------------------

def test_config_filename_slugs_the_experiment_name():
    assert config_filename("Scaling Arm 2") == "scaling_arm_2.yaml"


def test_build_config_writes_yaml_matching_the_real_smoke_config(tmp_path):
    engine = B2Engine()
    path = build_config(engine, {
        "name": "Dashboard Smoke", "factor": "scaling",
        "techniques": ["standard", "minmax"],
        "datasets": ["credit-g", "house_16H"],
        "models": ["logreg", "random_forest"], "k": 5, "seed": 671,
    }, configs_dir=tmp_path)
    assert path.name == "dashboard_smoke.yaml"
    reloaded = yaml.safe_load(path.read_text(encoding="utf-8"))
    expected = dict(real_config(engine, "smoke.yaml"))
    expected["experiment"] = "Dashboard Smoke"
    assert reloaded == expected


def test_build_config_writes_keys_in_the_engines_own_order(tmp_path):
    engine = B2Engine()
    path = build_config(engine, {
        "name": "order", "factor": "scaling", "techniques": ["standard"],
        "datasets": ["wdbc"], "models": ["logreg"], "k": 10, "seed": 671,
    }, configs_dir=tmp_path)
    lines = path.read_text(encoding="utf-8").splitlines()
    keys = [ln.split(":")[0] for ln in lines if ":" in ln and not ln.startswith((" ", "-"))]
    assert keys[:3] == ["experiment", "factor", "techniques"]
