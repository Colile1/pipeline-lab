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

## 9 November 2026

Before the repository was published, references to local planning notes were reworded
in every commit, the corresponding lines were dropped from `.gitignore`, and the sources of a
private self-assessment were removed from the history. Every commit
therefore has a new ID; messages, authors, dates and all other file contents are unchanged.
The pre-registration commit cited in the report and in `heldout_test.py` is now 4fd88d0
(previously 1f82653). The IDs in the table above resolve through this one.

| date | ID until 9 November | current ID | commit |
|---|---|---|---|
| 2026-10-13 | eb8d97c | f6f4621 | Pipeline Lab dashboard: compose, run and analyse experiments in the browser |
| 2026-10-13 | 6ec00cd | c0d5a3b | Document the four-factor sweep results and the k-sweep decision |
| 2026-10-13 | 092aa23 | 3cabb52 | Record the k-sweep implementation and the queued runs |
| 2026-10-13 | 6a89abd | bed4c79 | Record the k-sweep result: discarding features is the cost, not selecting |
| 2026-10-13 | 7de103f | 69da354 | Correct the large-dataset cost estimate with measured timings |
| 2026-10-13 | fad9431 | e2165a6 | Record large-dataset scaling results and correct the invariance claim |
| 2026-10-13 | 54eee0d | 0125e46 | Record the tuning results and the random-equals-grid limitation |
| 2026-10-13 | 5ac4a06 | 691f8e3 | Record the 5 percent MCAR imputation results |
| 2026-10-13 | cd29875 | 6d19488 | Record the 15 percent MCAR results and the change of reference level |
| 2026-10-13 | 5d270dc | 659b4c5 | Record the 30 percent MCAR results |
| 2026-10-13 | 05d43f0 | 63831e3 | Record the 5 percent MAR results |
| 2026-10-13 | d93e5ce | 1bcce02 | Record the 15 percent MAR results |
| 2026-10-13 | f4a87e5 | f95ad7f | Record the 30 percent MAR results and summarise the imputation sweeps |
| 2026-10-13 | 7a8819a | d6ac98c | Record the plan for the next three steps |
| 2026-10-13 | 4f4a2ec | 5615605 | Read injected imputation sweeps against mean on the Findings page |
| 2026-10-13 | c924082 | 91ac225 | Record the three completed steps and the regression imputation results |
| 2026-10-13 | e3aac3b | 11bef8d | Record the house_16H explanation and the skipped-row fix |
| 2026-10-14 | a99534f | 8617598 | Record the corrected tuning results: the rejected SVM finding does not hold |
| 2026-10-14 | 5037e9c | d976021 | Log SVM large-dataset result and the encoding/selection large-dataset plan |
| 2026-10-14 | 4bc0015 | 88f5973 | Log encoding effect on large categorical datasets (sec 4r) |
| 2026-10-14 | cb3659f | ec91c2a | Log chi2 sparse-input bug, fix and clean record restart (sec 4s) |
| 2026-10-14 | 960d6bc | 5daac3a | Log the rfe+svm false-stall incident on adult (sec 4t) |
| 2026-10-15 | 780e007 | bc78af5 | Log selection effect on large datasets, lasso's data-dependent pruning (sec 4u) |
| 2026-10-15 | a4cf766 | 8e7bc0d | Log the holdout_large launch (sec 4v) |
| 2026-10-15 | e8f829f | 68d6d60 | Log repeated-holdout results, agreement with k-fold record (sec 4w) |
| 2026-10-15 | 40ec48a | 601224a | Close the imputer-vs-imputer secondary analysis, a correctly-qualified null (sec 4x) |
| 2026-10-15 | 0dd5c48 | 332b535 | Measure large-dataset tuning cost, leave launch for a decision (sec 4y) |
| 2026-10-15 | aceacd7 | 493163a | Log tuning_large launch in full, accepted multi-day cost (sec 4z) |
| 2026-10-16 | 5fdc128 | b957117 | Log tuning_large results: gradient_boosting is the one model it helps (sec 4za) |
| 2026-10-16 | faace72 | a3eada5 | Add programme findings report, master figures and analysis scripts |
| 2026-10-16 | 0cf848d | f65a4af | Add full research report centred on the Pipeline Lab system |
| 2026-10-16 | 5d31748 | d714c84 | Add dataset-characteristic meta-analysis with sensitivity map and figures |
| 2026-10-17 | b6f679e | e30393c | Add research summary page with figures and live record numbers |
| 2026-10-17 | cb99d9a | e5207cc | Add poster build and layout-check scripts |
| 2026-10-17 | ba82a95 | 4b5cd76 | Log the n=8 regression re-run and its four new findings |
| 2026-10-17 | 5cb27e2 | cc9ee59 | Log seed replication: scaling result holds in direction, not in significance |
| 2026-10-17 | 3fa10de | 13ad88b | Add seed reliability threshold, cost scaling and meta-analysis re-run |
| 2026-10-17 | 99abb4c | a9dedc2 | Log the registry widening and imputation seed test |
| 2026-10-17 | 9fa5f91 | f77dec1 | Log the scaling arm at n=16: result moves from logreg to svm |
| 2026-10-17 | c75726a | 3903738 | Log two monitoring errors and the drop_rows skip asymmetry between seeds |
| 2026-10-17 | c0bd0b8 | 0b907aa | Recheck all classification arms at n=16; encoding null is untested, not null |
| 2026-10-17 | a8e7eff | b4cf0f7 | Scope the no-op problem across arms; scaling no-ops are invariance, not a gap |
| 2026-10-17 | 9502233 | 7422295 | Add single-source recount of report figures; catch drop_rows reintroduction |
| 2026-10-17 | 2f84518 | bb92f35 | Regenerate figures; compute fig2 caption from data and fix clipped axis |
| 2026-10-17 | 1dfdf63 | 45f29cd | Update meta-analysis to 31-dataset registry; keep oscillating correlation withdrawn |
| 2026-10-17 | 5e92890 | 260d782 | Imputation replication at MCAR: 50 percent reproduction, fix gate-blind comparison |
| 2026-10-18 | 86201e5 | 76e6e41 | Imputation replication complete: 35 percent reproduction across six sweeps |
| 2026-10-18 | 575edaa | 5239ca4 | Correct replication timeline from run timestamps: 2.6h continuous, no sleep |
| 2026-10-18 | 512ccc9 | ec565ff | Verify reported compute excludes idle time: 89.8h compute in 128.1h calendar |
| 2026-10-18 | 08466aa | 342a2be | Rebuild report on final record and package v3 |
| 2026-10-18 | 7a45d58 | 5192ce2 | Add feature_scale_ratio, widen imputation arm, log duplicate-row mistake |
| 2026-10-18 | 1f82653 | 4fd88d0 | Pre-register the held-out scaling confirmation before running it |
| 2026-10-18 | 8519986 | 578d0cb | Held-out test: prediction not confirmed, 3 of 5 at p=0.3125 |
| 2026-10-18 | 716aaec | b7d5e46 | Add deduplicating seed comparison for the widened imputation arm |
| 2026-10-18 | c5de5a8 | f033788 | Interim widened-imputation reading; correct duplicate count from full check |
| 2026-10-18 | 249bed6 | 05ae9a8 | All MCAR widened-imputation pairs complete: 60 percent reproduction so far |
| 2026-10-19 | 48e909e | 6fff86f | Log the deleted-class guard bug and its single contaminated run |
| 2026-10-19 | d19695e | 92847ec | Widened arm at 62 percent; correct the 5r reading on gate agreement |
| 2026-10-19 | fc3d1d8 | 61fa4db | Commit the sweep queue runners and config generators |
| 2026-10-19 | ec541db | 4d3b69c | Widened imputation arm complete: 35 to 59 per cent reproduction |
| 2026-10-19 | 2392ef1 | a2690dd | Rebuild report with widened arm and held-out test; separate replication from experimental totals |
| 2026-10-19 | 777b2c5 | 30000a7 | Three-seed imputation analysis: only 8 per cent survive all three draws |
| 2026-10-19 | bc2c83f | e052f51 | Add the report verification gate, with its own two false positives fixed |
| 2026-10-19 | 7a68873 | be32af5 | Renumber tables 4.1-4.13, fix verification false positives, package v5 |
| 2026-10-19 | 805adbd | dc128e4 | Add the internal grading report and its builder |
| 2026-10-25 | 5f1c45d | 6c8e74e | Move report sources into the repo; v6 edits, timeline figure, appendices |
| 2026-10-25 | 70c93c7 | 9e67604 | Read analysis paths from environment variables so the scripts run on Colab |
| 2026-10-25 | 5e17e99 | 9c7a634 | Add the Colab re-run bundle: notebook, runner, comparison and analyses |
| 2026-10-25 | 6252d6d | 06fce95 | Package v6 with ethics appendices and the Colab bundle |
| 2026-10-25 | b04a741 | 48c7597 | Log v6 and the Colab bundle; add results ingestion for v7 |
| 2026-10-25 | 94adb61 | d0a42ed | Map earlier commit IDs; keep the grading report out of packages |
| 2026-10-25 | 0730dab | 6671676 | Reword a planning note; leave repository housekeeping out of the bundle |
