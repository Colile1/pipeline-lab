# backend/app/uploads/

Handles a user's raw CSV upload: validate it's usable, compute the
characteristics the target engine's catalogue expects, then register it.

| File | Responsibility | Key signatures |
|---|---|---|
| `validate.py` | Structural checks before anything is registered | `validate_csv(path, target, task=None) -> ValidationResult` — checks: readable CSV with unique column names, target present with no missing values and at least two distinct values, no all-NaN column, at least one numeric feature, task type valid or inferred; `check_dataset_id(dataset_id, taken)` |
| `register.py` | Orchestrate one upload | `register_upload(engine, csv_path, dataset_id, target, task=None, domain=..., source_name=...) -> dict` — validates, then calls `engine.register_dataset(...)`. Characteristics are NOT computed here: the engine's own code computes them under the engine's own interpreter (prepfx `characterise()`, B2 `_dataset_properties()`), so values, rounding and dtype handling cannot drift from the engine's schema |

## Integration

Called only from `api/datasets.py`'s upload route. Writes go through the
target `Engine` (from `engines/`) so the catalogue file path and cache
directory are never hardcoded here. Uploads land in each engine's
user-dataset file (prepfx `data/user_datasets.csv`, B2
`datasets/user_catalogue.csv`), never in the registered design.

## Done when

A real sample CSV, uploaded through the API, produces a catalogue row
whose computed values a human can verify against `df.describe()` /
`df.corr()` by hand, and the target engine's own dataset loader can read
the registered dataset back without modification.
