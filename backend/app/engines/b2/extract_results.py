# Runs under B2's OWN interpreter (not the dashboard's): reads back one
# experiment's logged runs from B2's own shared mlflow.db (via B2's own
# tracking.store.default_tracking_uri, so the store path is never
# hardcoded here) and writes them as a plain CSV for the dashboard to
# read without ever querying MLflow itself.
import argparse
import json
import sys
from pathlib import Path


def _parse_args() -> argparse.Namespace:
    """Parse the extraction arguments.

    Inputs: none (reads sys.argv).
    Output: namespace with src, experiment and out.
    """
    parser = argparse.ArgumentParser(description="Extract one experiment's logged runs from B2's MLflow store.")
    for name in ("src", "experiment", "out"):
        parser.add_argument(f"--{name}", required=True)
    return parser.parse_args()


# Every column search_runs() can return for a run this app launches (see
# mlflow_logger.py's _log_params/_log_fold_metrics/_log_mean_metrics/tags).
# Fold-level metrics (metrics.accuracy etc, logged at step=fold_idx) are
# the last-step value in search_runs()'s one-row-per-run view, which is
# of limited use on its own — mean_* is what a results page should show,
# so only the mean_* metrics and the run's own params/tags are kept.
_PARAM_COLUMNS = ["dataset", "factor", "technique", "model", "k", "seed", "missing_rate", "mechanism"]
_METRIC_COLUMNS = ["mean_accuracy", "mean_f1", "mean_rmse"]


def main() -> None:
    """Read one experiment's runs from B2's mlflow.db and write them as a CSV.

    Inputs: command-line arguments (see _parse_args).
    Output: None; prints {"results_path": the written CSV, "rows": row
    count} as one JSON line. Writes no file and prints rows=0 when the
    experiment does not exist or has no runs — never invents a row.
    """
    args = _parse_args()
    sys.path.insert(0, args.src)
    import mlflow
    import pandas as pd
    from research_impact_of_preprocess.tracking.store import default_tracking_uri

    mlflow.set_tracking_uri(default_tracking_uri())
    experiment = mlflow.get_experiment_by_name(args.experiment)
    if experiment is None:
        print(json.dumps({"results_path": None, "rows": 0}))
        return

    runs = mlflow.search_runs(experiment_ids=[experiment.experiment_id])
    if runs.empty:
        print(json.dumps({"results_path": None, "rows": 0}))
        return

    out_rows = []
    for _, run in runs.iterrows():
        row = {"run_id": run.get("run_id"), "status": run.get("status")}
        for col in _PARAM_COLUMNS:
            value = run.get(f"params.{col}")
            row[col] = None if pd.isna(value) else value
        for col in _METRIC_COLUMNS:
            value = run.get(f"metrics.{col}")
            row[col] = None if pd.isna(value) else float(value)
        row["git_commit"] = run.get("tags.git_commit")
        out_rows.append(row)

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(out_rows).to_csv(out_path, index=False)
    print(json.dumps({"results_path": str(out_path), "rows": len(out_rows)}))


if __name__ == "__main__":
    main()
