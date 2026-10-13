# Runs under prepfx's OWN interpreter (not the dashboard's): caches an uploaded
# CSV as parquet where prepfx's fetch() looks, records its DatasetSpec in
# prepfx's user-dataset file, and characterises it with prepfx's own
# characterise(). Prints one JSON line on stdout for the dashboard to read.
import argparse
import csv
import json
import sys
from dataclasses import asdict
from pathlib import Path

LICENCE_NOTE = "user upload (experiment-dashboard)"


def _parse_args() -> argparse.Namespace:
    """Parse the registration arguments.

    Inputs: none (reads sys.argv).
    Output: namespace with src, csv, id, target, task, source_name,
    user_datasets and cache_dir.
    """
    parser = argparse.ArgumentParser(description="Register a user CSV with prepfx.")
    for name in ("src", "csv", "id", "target", "task", "source-name",
                 "user-datasets", "cache-dir"):
        parser.add_argument(f"--{name}", required=True)
    return parser.parse_args()


def _append_spec(path: Path, spec) -> None:
    """Append one DatasetSpec row to the user-dataset CSV, creating it if needed.

    Inputs: path - the user-dataset CSV; spec - the DatasetSpec to record.
    Output: None; writes one row (and the header on first use).
    """
    fields = list(type(spec).__dataclass_fields__)
    is_new = not path.is_file()
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=fields, lineterminator="\n")
        if is_new:
            writer.writeheader()
        writer.writerow(asdict(spec))


def _jsonable(profile: dict) -> dict:
    """Replace NaN (prepfx's class_balance on regression) with None for JSON.

    Inputs: profile - a DatasetProfile as a dict.
    Output: the same dict with NaN floats as None.
    """
    return {k: (None if isinstance(v, float) and v != v else v) for k, v in profile.items()}


def main() -> None:
    """Cache, characterise and register one uploaded CSV using prepfx's own code.

    Inputs: command-line arguments (see _parse_args).
    Output: None; prints {"registered": spec, "characteristics": profile}.
    Raises: SystemExit with a specific message if the id is taken or a
    stale cache file already exists under that id.
    """
    args = _parse_args()
    sys.path.insert(0, args.src)
    import pandas as pd
    from prepfx.datasets import registry
    from prepfx.datasets.characterise import characterise
    from prepfx.datasets.fetch import fetch, load_xy

    user_path, cache_dir = Path(args.user_datasets), Path(args.cache_dir)
    reserved = {**registry.DATASETS, **registry.LARGE_DATASETS, **registry.MONSTER_DATASETS}
    if args.id in reserved or args.id in registry.load_user_datasets(user_path):
        sys.exit(f"Error: dataset id '{args.id}' is already registered in prepfx")
    parquet = cache_dir / f"{args.id}.parquet"
    if parquet.exists():
        sys.exit(f"Error: a cached file already exists for id '{args.id}': {parquet}")

    frame = pd.read_csv(args.csv)
    frame.columns = [str(c) for c in frame.columns]  # parquet needs string names
    spec = registry.DatasetSpec(
        args.id, "local", args.source_name, args.task, args.target, LICENCE_NOTE
    )
    cache_dir.mkdir(parents=True, exist_ok=True)
    frame.to_parquet(parquet)
    try:
        cached = fetch(spec, cache_dir)  # prepfx's own loader reads it back
        X, y = load_xy(spec, cached)
        if X.shape != (frame.shape[0], frame.shape[1] - 1) or len(y) != len(frame):
            raise RuntimeError("cached dataset does not match the uploaded CSV shape")
        profile = characterise(cached, spec)
        _append_spec(user_path, spec)
        if registry.load_user_datasets(user_path).get(spec.id) != spec:
            raise RuntimeError("registered spec does not read back as written")
    except BaseException:
        parquet.unlink(missing_ok=True)
        raise
    print(json.dumps({"registered": asdict(spec), "characteristics": _jsonable(asdict(profile))}))


if __name__ == "__main__":
    main()
