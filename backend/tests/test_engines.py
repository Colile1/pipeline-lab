# Confirms each engine adapter's fixed lists and run command match that
# target repo's own design notes, per docs/build-order.md step 3's "Done when".
from pathlib import Path

from app.engines.b2 import B2Engine
from app.engines.prepfx import PrepfxEngine

SCALING = ["standard", "minmax", "robust", "none"]
IMPUTATION = ["mean", "median", "knn"]
# The two engines name the logistic/linear-regression model differently:
# prepfx's pipelines/models.py key is "logistic"; b2's is "logreg". Never
# assume these lists match between engines.
PREPFX_MODELS = ["logistic", "svm", "random_forest", "gradient_boosting"]
B2_MODELS = ["logreg", "svm", "random_forest", "gradient_boosting"]


def test_prepfx_fixed_lists_match_its_design_notes():
    engine = PrepfxEngine()
    assert engine.fixed_techniques("scaling") == SCALING
    assert engine.fixed_techniques("imputation") == IMPUTATION
    assert sorted(engine.fixed_models()) == sorted(PREPFX_MODELS)


def test_prepfx_run_command_matches_its_readme():
    engine = PrepfxEngine()
    config = Path("configs/smoke.yaml")
    assert engine.run_command(config) == [
        "python", "run_experiment.py", "--config", str(config),
    ]


def test_prepfx_rejects_unknown_factor():
    engine = PrepfxEngine()
    try:
        engine.fixed_techniques("bogus")
        assert False, "expected ValueError for an unknown factor"
    except ValueError:
        pass


def test_b2_fixed_lists_match_its_design_notes():
    engine = B2Engine()
    assert engine.fixed_techniques("scaling") == SCALING
    assert engine.fixed_techniques("imputation") == IMPUTATION
    assert sorted(engine.fixed_models()) == sorted(B2_MODELS)


def test_the_two_engines_name_logistic_regression_differently():
    assert "logistic" in PrepfxEngine().fixed_models()
    assert "logreg" not in PrepfxEngine().fixed_models()
    assert "logreg" in B2Engine().fixed_models()
    assert "logistic" not in B2Engine().fixed_models()


def test_b2_run_command_matches_its_readme():
    engine = B2Engine()
    config = Path("configs/smoke.yaml")
    assert engine.run_command(config) == [
        "python", "run_experiment.py", "--config", str(config),
    ]


def test_b2_rejects_unknown_factor():
    engine = B2Engine()
    try:
        engine.fixed_techniques("bogus")
        assert False, "expected ValueError for an unknown factor"
    except ValueError:
        pass


def test_engine_paths_point_at_the_real_target_repos():
    prepfx = PrepfxEngine()
    b2 = B2Engine()
    assert prepfx.root_path.name == "preprocessing-effects-framework"
    assert prepfx.root_path.is_dir()
    assert b2.root_path.name == "Research_Impact_of_Preprocess"
    assert b2.root_path.is_dir()
    assert b2.catalogue_path.is_file()


def test_prepfx_list_datasets_matches_its_own_registry():
    engine = PrepfxEngine()
    rows = engine.list_datasets()
    assert len(rows) == 24
    iris = next(r for r in rows if r["id"] == "iris")
    assert iris == {
        "id": "iris", "source": "sklearn", "ref": "load_iris",
        "task": "classification", "target": "target",
        "licence": "sklearn bundled (public domain)",
    }


def test_b2_list_datasets_matches_its_own_catalogue_csv():
    engine = B2Engine()
    rows = engine.list_datasets()
    assert len(rows) == 12
    wdbc = next(r for r in rows if r["dataset"] == "wdbc")
    assert wdbc["n_rows"] == 569
    assert wdbc["n_classes"] == 2
    abalone = next(r for r in rows if r["dataset"] == "abalone")
    assert abalone["n_classes"] is None
