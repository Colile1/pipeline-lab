# Confirms the dashboard reads the engine's run record correctly, and
# that what the UI states agrees with what the engine's own analyse.py
# states. A UI that quietly disagreed with the thesis would be worse
# than one that showed nothing.
import sqlite3

import pytest

from app.core import catalogue, findings

# These tests read the REAL record rather than a fixture. That is
# deliberate: the bug they guard against is the dashboard and the engine
# disagreeing about real data, which a synthetic fixture cannot catch.
# They skip rather than fail when no sweep has been run yet, so a fresh
# clone is not red for a reason the reader cannot act on.
record_exists = pytest.mark.skipif(
    not catalogue.db_path().exists(),
    reason="no lab.db yet; run a sweep first",
)


@record_exists
def test_the_record_opens_read_only():
    """The dashboard must never be able to write to the record.

    Non-vacuous: it asserts a write actually raises, not merely that we
    asked for mode=ro.
    """
    with catalogue.connect() as c:
        with pytest.raises(sqlite3.OperationalError):
            c.execute("delete from runs")


@record_exists
def test_overview_counts_every_recorded_run():
    o = catalogue.overview()
    assert o["total_runs"] > 0
    assert o["succeeded"] + o["failed"] + o["skipped"] == o["total_runs"]
    assert o["compute_seconds"] >= 0


@record_exists
def test_sweeps_include_runs_this_dashboard_never_launched():
    """The point of the catalogue: CLI sweeps are first-class.

    Every row so far was written by run_experiment.py, not by the UI, so
    an empty list here means the UI is still blind to real results.
    """
    rows = catalogue.sweeps()
    assert rows
    assert all(r["runs"] >= 1 for r in rows)
    assert all(r["config_name"] for r in rows)


@record_exists
def test_a_sweeps_run_counts_add_up():
    for sweep in catalogue.sweeps():
        total = sweep["succeeded"] + sweep["failed"] + sweep["skipped"]
        assert total == sweep["runs"], sweep["config_name"]


@record_exists
def test_aggregate_matches_a_direct_query():
    """The plotted number must be the recorded number."""
    sweep = catalogue.sweeps()[0]["config_name"]
    # Pick a metric this sweep actually recorded: a regression sweep has
    # no accuracy at all, and a classification sweep has no RMSE.
    with catalogue.connect() as c:
        metric = next(
            m for m in catalogue.METRICS
            if c.execute(
                f"select count({m}) from runs where config_name = ? "
                f"and status = 'succeeded'", (sweep,)
            ).fetchone()[0] > 0
        )
    result = catalogue.aggregate("dataset", metric, "none", config_name=sweep)
    assert not result["empty_reason"]
    points = {p["x"]: p for p in result["series"]["all"]}
    with catalogue.connect() as c:
        rows = c.execute(
            f"select dataset, avg({metric}) m, count(*) n from runs "
            f"where config_name = ? and status = 'succeeded' "
            f"and {metric} is not null group by dataset",
            (sweep,),
        ).fetchall()
    for row in rows:
        assert points[row["dataset"]]["mean"] == pytest.approx(row["m"])
        assert points[row["dataset"]]["n"] == row["n"]


@record_exists
def test_aggregate_excludes_runs_that_never_produced_a_score():
    """A skipped run has a reason, not a number; averaging it in would
    bias every series it touches."""
    result = catalogue.aggregate("scaling", "accuracy_mean", "none")
    counted = sum(p["n"] for p in result["series"]["all"])
    with catalogue.connect() as c:
        succeeded = c.execute(
            "select count(*) from runs where status = 'succeeded' "
            "and accuracy_mean is not null"
        ).fetchone()[0]
    assert counted == succeeded


@record_exists
def test_a_metric_no_run_recorded_explains_itself():
    """Asking for accuracy on a regression sweep is a normal mistake;
    the answer should say why it is empty, not just be empty."""
    result = catalogue.aggregate(
        "scaling", "accuracy_mean", "none",
        config_name="ofat_scaling_regression",
    )
    assert result["series"] == {}
    assert "regression" in result["empty_reason"]


@pytest.mark.parametrize("bad", ["run_id; drop table runs", "nonsense", "1=1"])
def test_an_unknown_dimension_is_refused(bad):
    """Column names reach SQL, so they are checked against the schema."""
    with pytest.raises(catalogue.CatalogueError):
        catalogue.aggregate(bad, "accuracy_mean")


def test_an_unknown_metric_is_refused():
    with pytest.raises(catalogue.CatalogueError):
        catalogue.aggregate("scaling", "definitely_not_a_column")


@record_exists
def test_dimensions_only_offer_values_that_were_actually_run():
    dims = catalogue.dimensions()
    assert "scaling" in dims["dimensions"]
    with catalogue.connect() as c:
        real = {
            r[0] for r in c.execute(
                "select distinct scaling from runs where scaling is not null"
            )
        }
    assert set(dims["dimensions"]["scaling"]) == real


# --- findings: the UI must agree with the engine -------------------------

needs_scipy = pytest.mark.skipif(
    not findings.scipy_available(), reason="scipy not installed"
)


def test_the_holm_adjustment_matches_a_worked_example():
    """Holm steps down: smallest p times k, next times k-1, and the
    sequence never decreases."""
    adjusted = findings.holm_adjust([0.01, 0.04, 0.03])
    assert adjusted[0] == pytest.approx(0.03)
    assert adjusted[2] == pytest.approx(0.06)
    assert adjusted[1] == pytest.approx(0.06)


def test_holm_is_never_less_powerful_than_bonferroni():
    raw = [0.001, 0.02, 0.04]
    holm = findings.holm_adjust(raw)
    bonferroni = [min(1.0, p * len(raw)) for p in raw]
    assert all(h <= b + 1e-12 for h, b in zip(holm, bonferroni))


@pytest.mark.parametrize("n,expected", [
    (5, 0.0625), (6, 0.03125), (7, 0.015625), (8, 0.0078125),
])
def test_the_wilcoxon_floor_is_the_known_discrete_limit(n, expected):
    assert findings.wilcoxon_floor(n) == pytest.approx(expected)


def test_six_datasets_clear_alpha_but_not_the_holm_bar():
    """The trap that made the engine's first power warning wrong."""
    assert findings.wilcoxon_floor(6) < 0.05
    assert findings.wilcoxon_floor(6) > 0.05 / 3
    assert findings.datasets_needed(0.05 / 3) == 7


@record_exists
@needs_scipy
def test_the_dashboard_finding_matches_the_engines_own_analysis():
    """The agreement that matters.

    These exact numbers come from running the engine's analyse.py on the
    same record (PROGRESS.md, 2026-10-12). If the dashboard ever drifts
    from the engine, the UI would contradict the thesis.
    """
    result = findings.analyse(
        "ofat_scaling_full", "accuracy_mean", "classification", "logreg"
    )
    assert result["available"]
    assert result["n_datasets"] == 11
    assert result["dropped_datasets"] == ["adult"]
    assert result["friedman"]["statistic"] == pytest.approx(9.1415, abs=1e-3)
    assert result["friedman"]["p_value"] == pytest.approx(0.027467, abs=1e-5)
    assert result["friedman"]["significant"]

    by_level = {c["level"]: c for c in result["comparisons"]}
    standard = by_level["standard"]
    assert standard["p_value"] == pytest.approx(0.013672, abs=1e-5)
    assert standard["p_adjusted"] == pytest.approx(0.041016, abs=1e-5)
    assert standard["rejected"]
    assert standard["effect"]["n_improved"] == 10
    assert standard["effect"]["n_pairs"] == 11
    assert not by_level["minmax"]["rejected"]
    assert not by_level["robust"]["rejected"]


@record_exists
@needs_scipy
def test_a_non_significant_global_test_blocks_the_post_hoc():
    """No pairwise result is reported that the global test does not
    license. The regression arm at n=8 is the real example."""
    result = findings.analyse(
        "ofat_scaling_regression", "rmse_mean", "regression", "svm"
    )
    assert result["available"]
    if not result["friedman"]["significant"]:
        assert result["comparisons"] == []
        assert result["skipped_reason"]


@record_exists
@needs_scipy
def test_every_reported_comparison_carries_an_effect_size():
    """Methodology 7.2: no p-value without a practical effect size."""
    for finding in findings.headline("ofat_scaling_full"):
        for comparison in finding["comparisons"]:
            effect = comparison["effect"]
            assert "median_difference" in effect
            assert effect["n_pairs"] >= 2
            assert (effect["n_improved"] + effect["n_worsened"]
                    + effect["n_tied"]) == effect["n_pairs"]


# --- the reference level for injected-missingness sweeps -----------------


def test_a_sweep_without_injection_keeps_the_declared_baseline():
    rows = [{"injected_rate": None}, {"injected_rate": None}]
    assert findings.reference_for("imputation", rows) == (None, (), "")
    assert findings.reference_for("scaling", rows) == (None, (), "")


def test_an_injected_imputation_sweep_is_read_against_mean():
    """drop_rows is skipped or scored on different rows under injection,
    so it cannot be the reference. The note must explain the departure."""
    rows = [{"injected_rate": 0.15}]
    reference, excluded, note = findings.reference_for("imputation", rows)
    assert reference == "mean"
    assert excluded == ("drop_rows",)
    assert "mean imputation" in note and "departs" in note


def test_injection_does_not_change_the_reference_for_other_factors():
    """Only the imputation baseline is broken by injected gaps."""
    assert findings.reference_for("scaling", [{"injected_rate": 0.15}])[0] is None


@record_exists
@needs_scipy
def test_the_injected_finding_matches_the_engines_analysis():
    """Numbers from analyse.py --baseline mean --exclude drop_rows on the
    same record (PROCESS-LOG.md section 4k, 30% MCAR). If the page drifted
    it would contradict the written result."""
    with catalogue.connect() as c:
        present = c.execute(
            "select count(*) from runs where config_name = 'ofat_imputation_mcar30'"
        ).fetchone()[0]
    if not present:
        pytest.skip("the 30% MCAR sweep is not in this record")

    result = findings.analyse(
        "ofat_imputation_mcar30", "accuracy_mean", "classification", "svm"
    )
    assert result["available"]
    assert result["baseline"] == "mean"
    assert result["declared_baseline"] == "drop_rows"
    assert not result["uses_declared_baseline"]
    assert result["reference_note"]
    assert result["n_datasets"] == 9
    assert result["friedman"]["statistic"] == pytest.approx(7.8235, abs=1e-3)
    assert result["friedman"]["p_value"] == pytest.approx(0.02001, abs=1e-4)

    by_level = {c["level"]: c for c in result["comparisons"]}
    assert set(by_level) == {"knn", "median"}, "drop_rows must not be compared"
    assert by_level["knn"]["p_value"] == pytest.approx(0.015625, abs=1e-5)
    assert by_level["knn"]["p_adjusted"] == pytest.approx(0.03125, abs=1e-5)
    assert by_level["knn"]["rejected"]
    assert by_level["knn"]["effect"]["n_improved"] == 7
    assert not by_level["median"]["rejected"]


@record_exists
@needs_scipy
def test_an_ordinary_sweep_reports_that_it_uses_the_declared_baseline():
    result = findings.analyse(
        "ofat_scaling_full", "accuracy_mean", "classification", "logreg"
    )
    assert result["uses_declared_baseline"]
    assert result["reference_note"] == ""
    assert result["excluded_levels"] == []
