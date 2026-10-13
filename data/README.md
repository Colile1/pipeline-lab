# data/

Local staging area for this app's own working files — not a research
output location.

| Folder | Role |
|---|---|
| `uploads/` | Temporary home for a user's CSV between upload and successful registration into the target engine's own dataset cache. Cleared after registration; never a permanent dataset store. |
| `runs/<run-id>/` | Everything one dashboard-launched run writes: `config.yaml` (as sent to the engine), `run.log` (captured stdout/stderr), and, for engines whose schema has an `outputs_dir` field (prepfx), `outputs/` — that run's own results/figures/mlruns, isolated here specifically so a dashboard run can never overwrite the engine's own `outputs/` (prepfx's real B1 confirmatory results live there, filed by arm name only, and would otherwise be overwritten by any run of the same arm). See `core/runner.py`. |

Nothing in this folder is ever read by the two target research
codebases directly — once a dataset is registered it lives in that
engine's own cache directory, per that engine's own conventions. A run's
own output directory under `runs/<run-id>/outputs/` is the one exception
the engine does read from, because the dashboard tells the engine to
write there in the first place via that run's own config.
