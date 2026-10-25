# Commit IDs

On 25 October 2026 the commit messages in this repository were shortened to a single line.
Shortening a message gives a commit a new ID, and every later commit a new ID with it. The
file contents of every commit are unchanged, and so are the dates.

Some records made before that date cite the earlier IDs: the run record's `engine_git_sha`
column, comments in two re-run configs, and the manifests of submission packages v1 to v6.
This table resolves each earlier ID to the commit that now holds the same files.

| date | earlier ID | current ID | commit |
|---|---|---|---|
| 2026-10-18 | df05e80 | c5de5a8 | Interim widened-imputation reading; correct duplicate count from full check |
| 2026-10-18 | 7675b5d | 249bed6 | All MCAR widened-imputation pairs complete: 60 percent reproduction so far |
| 2026-10-19 | 1ea31a1 | 48e909e | Log the deleted-class guard bug and its single contaminated run |
| 2026-10-19 | e3f88cc | d19695e | Widened arm at 62 percent; correct the 5r reading on gate agreement |
| 2026-10-19 | 1dfe389 | fc3d1d8 | Commit the sweep queue runners and config generators |
| 2026-10-19 | f9414db | ec541db | Widened imputation arm complete: 35 to 59 per cent reproduction |
| 2026-10-19 | 0e234d2 | 2392ef1 | Rebuild report with widened arm and held-out test; separate replication from experimental totals |
| 2026-10-19 | 7762b0c | 777b2c5 | Three-seed imputation analysis: only 8 per cent survive all three draws |
| 2026-10-19 | edd1d51 | bc2c83f | Add the report verification gate, with its own two false positives fixed |
| 2026-10-19 | 98925cd | 7a68873 | Renumber tables 4.1-4.13, fix verification false positives, package v5 |
| 2026-10-19 | b55d138 | 805adbd | Add the internal grading report and its builder |
| 2026-10-25 | 2b50d60 | 5f1c45d | Move report sources into the repo; v6 edits, timeline figure, appendices |
| 2026-10-25 | 702a2f0 | 70c93c7 | Read analysis paths from environment variables so the scripts run on Colab |
| 2026-10-25 | 2d7d854 | 5e17e99 | Add the Colab re-run bundle: notebook, runner, comparison and analyses |
| 2026-10-25 | f03e8b6 | 6252d6d | Package v6 with ethics appendices and the Colab bundle |
| 2026-10-25 | 9b27182 | b04a741 | Log v6 and the Colab bundle; add results ingestion for v7 |
