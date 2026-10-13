# Runs under B2's OWN interpreter (not the dashboard's): caches an uploaded CSV
# as X.parquet/y.parquet where B2's loader looks, computes the catalogue row
# with B2's own _dataset_properties(), and records it in B2's user catalogue.
# Prints one JSON line on stdout for the dashboard to read.
import argparse
import csv
import json
import shutil
import sys
from pathlib import Path


def _parse_args() -> argparse.Namespace:
    """Parse the registration arguments.

    Inputs: none (reads sys.argv).
    Output: namespace with src, csv, name, target, task, domain,
    user_catalogue and datasets_dir.
    """
    parser = argparse.ArgumentParser(description="Register a user CSV with B2.")
    for name in ("src", "csv", "name", "target", "task", "domain",
                 "user-catalogue", "datasets-dir"):
        parser.add_argument(f"--{name}", required=True)
    return parser.parse_args()


def _append_row(path: Path, fields: list[str], row: dict) -> None:
    """Append one row to the user catalogue CSV, creating it if needed.

    Inputs: path - the user catalogue; fields - its column order; row - the
    values keyed by column.
    Output: None; writes one row (and the header on first use).
    """
    is_new = not path.is_file()
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=fields, lineterminator="\n")
        if is_new:
            writer.writeheader()
        writer.writerow(row)


def _remove_row(path: Path, name: str) -> None:
    """Drop a dataset's row from the user catalogue (rollback of _append_row).

    Inputs: path - the user catalogue; name - the dataset whose row goes.
    Output: None; rewrites the file without that row.
    """
    if not path.is_file():
        return
    with path.open("r", newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        fields, rows = reader.fieldnames, [r for r in reader if r["dataset"] != name]
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    """Cache, characterise and register one uploaded CSV using B2's own code.

    Inputs: command-line arguments (see _parse_args).
    Output: None; prints {"registered": user-catalogue row, "characteristics":
    catalogue-column values} where blank catalogue cells are None.
    Raises: SystemExit with a specific message if the name is taken or a
    stale cache directory already exists under that name.
    """
    args = _parse_args()
    sys.path.insert(0, args.src)
    import pandas as pd
    from research_impact_of_preprocess.data import loaders, registry
    from research_impact_of_preprocess.data.catalogue import (
        _CATALOGUE_COLUMNS, _dataset_properties,
    )

    user_catalogue = Path(args.user_catalogue)
    registry.USER_CATALOGUE_PATH = user_catalogue
    loaders._DATASETS_DIR = Path(args.datasets_dir)
    name = args.name
    if name in registry.REGISTRY or name in registry.load_user_datasets():
        sys.exit(f"Error: dataset name '{name}' is already registered in b2")
    cache = loaders._cache_dir(name)
    if cache.exists():
        sys.exit(f"Error: a cache directory already exists for '{name}': {cache}")

    frame = pd.read_csv(args.csv)
    cache.mkdir(parents=True)
    appended = False
    try:
        frame.drop(columns=[args.target]).to_parquet(cache / "X.parquet", index=False)
        pd.DataFrame({"y": frame[args.target]}).to_parquet(cache / "y.parquet", index=False)
        X, y = loaders._load_from_cache(name)  # characterise what B2 will actually load
        meta = registry.DatasetMeta(
            openml_id=0, task_type=args.task, target_col=args.target, domain=args.domain
        )
        row = _dataset_properties(name, X, y, meta)
        row["openml_id"] = ""  # no OpenML source for a user upload
        _append_row(user_catalogue, [*_CATALOGUE_COLUMNS, "target_col"],
                    {**row, "target_col": args.target})
        appended = True
        X_back, y_back, _ = loaders.load_dataset(name)  # B2's own entry point
        if X_back.shape != (frame.shape[0], frame.shape[1] - 1) or len(y_back) != len(frame):
            raise RuntimeError("registered dataset does not match the uploaded CSV shape")
    except BaseException:
        shutil.rmtree(cache, ignore_errors=True)
        if appended:
            _remove_row(user_catalogue, name)
        raise
    clean = {k: (None if v == "" else v) for k, v in row.items()}
    registered = {**clean, "target_col": args.target}
    print(json.dumps({"registered": registered, "characteristics": clean}))


if __name__ == "__main__":
    main()
