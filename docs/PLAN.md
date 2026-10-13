# Pipeline Lab — design plan

A drag-and-drop pipeline composer for the **original, non-simplified**
research scope, with exhaustive run provenance so trends can be mined
later.

Primary sources (the March set is the authoritative, most specific one):
- `31 Maarch analysis/Chapter_1_Colile.docx` §1.7 — the five components,
  their **named baselines**, 15-20 datasets, OFAT artefact spec
- `31 Maarch analysis/methodology_analysis_Colile.docx` — the selected
  methodology: controlled experiment, OFAT, stratified k-fold **k=10**,
  Friedman + Wilcoxon/Bonferroni, accuracy+F1/RMSE
- `30 March/research_proposal_rewritten_Colile.docx`
- `research proposal Colile 21 April .docx` §1.6.2 (later, slightly less specific)

This document is the plan only. Nothing is built yet. Read
`docs/SCOPE-DECISIONS.md` for the three questions that must be answered
before step 1, because two of them change what the artefact *is*.

---

## 1. Where this differs from `experiment-dashboard/`

`experiment-dashboard/` is a finished control surface for the two
**simplified** artefacts (B1 prepfx, B2). It varies two factors only:
scaling and imputation, one at a time (OFAT), scored by k-fold CV on
accuracy/F1/RMSE.

The April proposal's Table 1 planned **five** components. Verified
against both codebases on 2026-10-09:

| Component | Techniques (**baseline** per Chapter 1 §1.7) | In B1/B2 today? |
|---|---|---|
| Feature scaling | **no scaling**, Standard, MinMax, Robust | **Yes** |
| Missing value imputation | **row deletion**, mean, median, KNN | Partly — **row deletion absent** |
| **Feature selection** | **no selection**, Chi-square, mutual info, RFE, LASSO | **No — absent from both** |
| Model type | logreg, RF, SVM, GB (no baseline; all compared) | **Yes** |
| **Hyperparameter tuning** | **no tuning**, random search, grid search, Bayesian | **No — absent from both** |
| **Categorical encoding** | **onehot**, ordinal, target — see §2b: a deliberate amendment | Hardcoded OneHot, never varied |

Chapter 1 names a baseline for each component, which the April version
did not. Those baselines are what the composer's first column is
pre-filled with, and they are what OFAT varies against.

Encoding is the one row here that goes **beyond** the March documents —
it is a deliberate amendment, recorded as such in §2b below.

Evidence for the "No" rows: `grep -rln "SelectKBest|chi2|mutual_info|RFE|Lasso"`
and `grep -rln "GridSearchCV|RandomizedSearchCV|optuna"` across both
`src/` trees return nothing but two `friedman.py` false positives
(statistical tests, not selection). `optuna` is not installed in either
`.venv`. sklearn is 1.9.0, so GridSearchCV/RandomizedSearchCV are
available without new dependencies; Optuna would need installing.

**So this is not a UI project.** Roughly 60% of the work is new
experimental capability that neither research codebase has. That is the
central fact the scope decisions turn on.

---

## 2. Architecture decision: a third engine

The design notes forbid the dashboard from holding experimental logic, and
B1/B2 are frozen research records (B1 pre-registered, seed 20260702; B2
672 completed runs). Adding feature selection and tuning to either would
alter a pre-registered design and break comparability with results
already written into chapters.

Therefore: a **new third engine**, `engines/lab.py`, backed by a new
standalone package `pipeline-lab-engine/` that lives beside the other two
research repos and owns all new experimental logic. B1 and B2 adapters
stay in place, untouched, so the existing dashboard behaviour and every
existing test keep working.

```
671 Research June/
├── preprocessing-effects-framework/    (B1 — frozen, untouched)
├── Artefact/Research_Impact_of_Preprocess/  (B2 — frozen, untouched)
├── pipeline-lab-engine/                (NEW: the 5-component engine)
│   ├── src/piplab/
│   │   ├── components/   scaling, imputation, selection, tuning, encoding
│   │   ├── pipelines/    composes a full 5-stage sklearn Pipeline
│   │   ├── evaluation/   k-fold CV + (optionally) holdout split
│   │   ├── provenance/   resource + environment capture
│   │   └── storage/      the run record (SQLite)
│   ├── run_experiment.py  (same CLI contract as B1/B2: --config <yaml>)
│   └── requirements.txt
└── pipeline-lab/                       (this repo — UI + control surface)
```

The engine keeps the same `python run_experiment.py --config <yaml>`
contract, so `core/runner.py`, `core/run_status.py` and the whole
isolation/validation apparatus built in steps 7–11 are reused as-is.

---

## 2b. Encoding as a sixth factor — AMENDMENT 2026-10-09

Added at Colile's instruction. This is an **amendment to the registered
design**, not a recovery of something already planned, and it is
recorded that way so the chapter can state it honestly.

### What the March sources actually say

Encoding appears three times in `Chapter_1_Colile.docx` — at §1.2.1,
§1.2.1 again and §1.3 — every time as *descriptive prose* about what a
pipeline contains ("categorical variables are encoded into a numerical
representation that the model can process"). It never appears in the
"Pipeline Component / Candidate Techniques" table, which lists five
components only. Searching both `methodology_analysis_Colile.docx` and
`Chapter_3_Colile.docx` for `one-hot`, `ordinal` or `target encod`
returns **zero matches**: no encoding technique is named anywhere in the
March set.

So the honest position is: the original design treated encoding as a
*necessary pipeline stage* but not an *experimental factor*. Promoting it
is a new decision.

### Why it is defensible anyway

The study's own primary research question is "how do individual machine
learning pipeline design choices affect predictive performance" — and
encoding is unambiguously such a choice. It sits in the same
preprocessing stage as scaling and imputation, which *are* factors, and
SQ2 (preprocessing × model interaction) has a strong theoretical
prediction for it: tree ensembles tolerate ordinal encoding of unordered
categories far better than linear models and SVMs do, because they can
recover the partition by splitting repeatedly, whereas a linear model
reads the integer codes as a magnitude. That is exactly the kind of
mechanism SQ4 asks for.

### The techniques

All three are native to scikit-learn 1.9.0 (verified), so no new
dependency:

| Level | Technique | Note |
|---|---|---|
| **onehot** (baseline) | `OneHotEncoder(handle_unknown="ignore")` | Current behaviour in all three engines; keeps the amendment backward-compatible |
| ordinal | `OrdinalEncoder(handle_unknown="use_encoded_value", unknown_value=-1)` | Imposes a false ordering on unordered categories — the point is to measure how much that costs, per model family |
| target | `TargetEncoder` | Replaces a category with a target statistic |

### Leakage: target encoding is the dangerous one

Target encoding uses **y** to build the feature, so fitted naively it
leaks the target directly into the training matrix and inflates scores
badly. sklearn's `TargetEncoder` has internal cross-fitting (`cv`
parameter, default 5) precisely for this, and sits inside the pipeline
so it is also fitted per outer fold.

This means encoding joins selection and tuning as a **leakage-critical**
component, and `tests/test_leakage.py` must cover it: the existing
fit-spy proof is extended to the encoder, and a dedicated test asserts
that target encoding on a pure-noise feature does not beat chance (if it
does, y has leaked).

### Cost

Encoding only varies on datasets that *have* categorical features. Of
B2's 12 catalogued datasets, 8 have at least one categorical column
(`adult` 8, `credit-approval` 9, `colic` 19, `credit-g` 13,
`bank-marketing` 9, `heart-c` 7, `autoMpg` 3, `abalone` 1); `wdbc`,
`concrete`, `energy-efficiency` and `house_16H` are all-numeric and the
component is a no-op there. The composer should flag an encoding sweep
restricted to all-numeric datasets as pointless rather than run it and
report a null.

An encoding OFAT sweep is therefore ~8 datasets × 4 models × 3 levels =
**96 runs** — the cheapest of the six sweeps.

### Scope note for the write-up

Full factorial now includes a sixth component: 4 scaling × 4 imputation
× 5 selection × 4 tuning × **3 encoding** × 4 models × ~17 datasets ≈
**65,280 runs**, which strengthens rather than weakens the case for OFAT.

## 3. The composer UI (your card grid)

### Wireframe: Compose tab

Column 1 is data. Columns 2+ are **named configurations** the user adds.
Rows are the pipeline stages. Each cell holds the option cards chosen for
that stage in that configuration. Cards drag between cells.

```
┌──────────────────────────────────────────────────────────────────────────────────┐
│  Pipeline Lab          Compose │ Runs │ Network │ Trends            [Run all ▶]  │
├──────────────────────────────────────────────────────────────────────────────────┤
│  PALETTE (drag from here)                                                        │
│  Encode:    [onehot*][ordinal][target]               * = baseline                │
│  Scaling:   [none*][standard][minmax][robust]                                    │
│  Impute:    [drop-rows*][mean][median][knn]                                      │
│  Select:    [none*][chi2][mutual-info][rfe][lasso]                               │
│  Model:     [logreg][rand-forest][svm][grad-boost]   (all four always compared)  │
│  Tuning:    [none*][random][grid][bayesian]                                      │
├───────────────┬──────────────────┬──────────────────┬──────────────────┬─────────┤
│               │  BASELINE        │  OFAT: scaling   │  OFAT: selection │   [+]   │
│               │  (all baselines) │  (vary scaling)  │  (vary select)   │         │
├───────────────┼──────────────────┼──────────────────┼──────────────────┼─────────┤
│ DATA          │  17 datasets     │  17 datasets     │  17 datasets     │         │
│ (shared)      │  [edit list...]  │  (same)          │  (same)          │         │
├───────────────┼──────────────────┼──────────────────┼──────────────────┼─────────┤
│ 1 ENCODING    │ ▢ onehot *       │ ▢ onehot *       │ ▢ onehot *       │         │
├───────────────┼──────────────────┼──────────────────┼──────────────────┼─────────┤
│ 2 IMPUTATION  │ ▢ drop-rows *    │ ▢ drop-rows *    │ ▢ drop-rows *    │         │
├───────────────┼──────────────────┼──────────────────┼──────────────────┼─────────┤
│ 3 SCALING     │ ▢ none *         │ ▢ none *         │ ▢ none *         │         │
│               │                  │ ▢ standard       │                  │         │
│               │                  │ ▢ minmax         │   ← only ONE row │         │
│               │                  │ ▢ robust         │     varies, per  │         │
├───────────────┼──────────────────┼──────────────────┤     OFAT         ┼─────────┤
│ 4 SELECTION   │ ▢ none *         │ ▢ none *         │ ▢ none *         │         │
│               │                  │                  │ ▢ chi2           │         │
│               │                  │                  │ ▢ mutual-info    │         │
│               │                  │                  │ ▢ rfe            │         │
│               │                  │                  │ ▢ lasso          │         │
├───────────────┼──────────────────┼──────────────────┼──────────────────┼─────────┤
│ 5 MODEL       │ ▢ logreg ▢ svm   │ ▢ logreg ▢ svm   │ ▢ logreg ▢ svm   │         │
│               │ ▢ rf     ▢ gb    │ ▢ rf     ▢ gb    │ ▢ rf     ▢ gb    │         │
├───────────────┼──────────────────┼──────────────────┼──────────────────┼─────────┤
│ 6 TUNING      │ ▢ none *         │ ▢ none *         │ ▢ none *         │         │
├───────────────┼──────────────────┼──────────────────┼──────────────────┼─────────┤
│ EVALUATION    │ stratified k=10  │ stratified k=10  │ stratified k=10  │         │
│               │ seed 671         │ seed 671         │ seed 671         │         │
│               │ split 70/15/15   │ split 70/15/15   │ split 70/15/15   │         │
│               │  (recorded only) │  (recorded only) │  (recorded only) │         │
├───────────────┼──────────────────┼──────────────────┼──────────────────┼─────────┤
│ ⟶ START       │ 68 runs   [▶]    │ 272 runs  [▶]    │ 340 runs  [▶]    │         │
│   TRAINING    │ ~6 min est.      │ ~25 min est.     │ ~35 min est.     │         │
└───────────────┴──────────────────┴──────────────────┴──────────────────┴─────────┘
         Total across selected configs: 680 runs · ~66 min estimated
         ⚠ A column with 2+ varied rows leaves OFAT — confirmation required
```

The three columns above are the real OFAT shape your Chapter 1 §1.7.3
specifies: a baseline column holding every baseline technique, then one
column per component being varied against it. "Vary one component,
hold the rest at baseline" is enforced by default — a column that varies
two or more rows at once is flagged, because that is no longer OFAT and
the attribution of any effect becomes ambiguous.

Behaviour:
- A cell with several cards = that stage is **swept** (cartesian product).
  The per-column run count updates live, so a user sees "24 runs" become
  "96 runs" before committing, not after.
- Dragging a card from the palette to a cell adds it; dragging a card out
  removes it; dragging between columns copies it.
- **Duplicate-column button** on each config header — the common case is
  "same as B but one thing changed".
- A column is invalid (red header, Run disabled) if a stage is empty or a
  combination is impossible; the reason shows inline, from the engine's
  own validator, never a guess.
- Keyboard-accessible alternative to drag for every action (a11y, and
  faster for power use): click cell → menu of that stage's options.

### Wireframe: Network tab

Your "inspiration from a neural network": configurations as a layered
graph. Each pipeline stage is a layer; each chosen technique is a node;
edges are the configurations that pass through them. Edge thickness =
how many runs took that path; node colour = mean score of runs through
it. This makes "which paths did I actually explore, and which won"
visible at a glance.

```
┌──────────────────────────────────────────────────────────────────────────────────┐
│  Compose │ Runs │ ●Network │ Trends        Colour by: [mean accuracy ▾]          │
├──────────────────────────────────────────────────────────────────────────────────┤
│   ENCODE      IMPUTE       SCALE        SELECT       MODEL       TUNE            │
│                                                                                  │
│   ┌──────┐   ┌──────┐    ┌──────┐     ┌──────┐    ┌──────┐   ┌──────┐           │
│   │onehot│═══│median│════│ none │─────│ none │────│logreg│───│ none │  0.88      │
│   └──────┘╲  └──────┘ ╲  └──────┘╲   ╱└──────┘╲  ╱└──────┘╲  └──────┘           │
│            ╲ ┌──────┐  ╲ ┌──────┐ ╲ ╱ ┌──────┐ ╳  ┌──────┐ ╲ ┌──────┐           │
│             ╲│ knn  │   ╲│standrd│══╳══│mutinf│══╱ ╲│ svm  │══│ grid │  0.94 ★   │
│              └──────┘    └──────┘ ╱ ╲ └──────┘    ╱└──────┘  └──────┘           │
│                          ┌──────┐╱   ╲┌──────┐   ╱                               │
│                          │robust│     │ rfe  │──╱            ┌──────┐           │
│                          └──────┘     └──────┘               │random│           │
│                                                              └──────┘           │
│   ▬▬▬ thick edge = many runs    ■ dark node = higher score   ★ best path         │
│   Hover a node → runs through it, mean ± sd, median wall-time                    │
│   Click an edge → filtered run list in the Runs tab                              │
└──────────────────────────────────────────────────────────────────────────────────┘
```

This is a legitimate visualisation of real sweep data, not decoration:
the layered structure *is* the pipeline, and every number on it comes
from recorded runs.

### Wireframe: Runs tab

```
┌──────────────────────────────────────────────────────────────────────────────────┐
│  Compose │ ●Runs │ Network │ Trends     [filter ▾] [compare selected] [export ⤓] │
├──────────────────────────────────────────────────────────────────────────────────┤
│ ☐ run_id    when          config    dataset  model   score   wall   cpu%  mem    │
│ ☑ 7f3a..    09-10 14:22   tuned     wine     svm     0.944   38.2s  412%  610MB  │
│ ☑ 2b91..    09-10 14:21   baseline  wine     svm     0.911    2.1s  104%  180MB  │
│ ☐ 55c0..    09-10 14:19   baseline  iris     logreg  0.973    0.8s   99%  142MB  │
│   ⋮                                                                              │
├──────────────────────────────────────────────────────────────────────────────────┤
│  2 selected ▸ side-by-side diff: config · metrics · resources · environment      │
└──────────────────────────────────────────────────────────────────────────────────┘
```

Clicking one run opens the full record (§4) — every field, copyable,
with the exact config YAML and a link to its raw log.

---

## 4. The run record — what gets stored

One row per (config × dataset × model × technique-combination), in
SQLite at `data/lab.db`. Written by the engine, read by the UI. Designed
for `GROUP BY`-style trend mining, so everything is a typed column, not
JSON blobs (except `config_yaml`, kept verbatim for reproducibility).

**Identity & timing** — `run_id`, `batch_id` (one "Run all" press),
`config_name`, `started_at`, `ended_at`, `wall_seconds`,
`cpu_seconds_user`, `cpu_seconds_system`, `queue_seconds`.

**Resources** (psutil 7.0.0, verified available) — `peak_rss_mb`,
`mean_cpu_percent`, `peak_cpu_percent`, `n_threads_peak`,
`disk_read_mb`, `disk_write_mb`.

**Machine & environment** — `hostname`, `cpu_model`, `cpu_cores_physical`
(8 here), `cpu_cores_logical` (12), `ram_total_gb` (15.75),
`os_name`, `os_version`, `python_version`, and pinned versions of
`sklearn` (1.9.0), `numpy`, `pandas`, `scipy`, plus `engine_git_sha`.
Resource numbers are only comparable within a machine, so the machine is
recorded on every row rather than assumed.

**Pipeline configuration** — one column per stage so each is directly
groupable: `encoding`, `imputation`, `scaling`, `selection`,
`selection_k`, `model`, `tuning`, `tuning_budget`, plus `seed`,
`cv_k`, and the split fields below.

**Evaluation** — `cv_k` (default **10**, per your methodology §6.3),
`cv_strategy` (`stratified_kfold`), per-fold score arrays, and
`fold_assignment_hash` so two runs can be proven to have used identical
folds. Plus `split_train`/`split_val`/`split_test` (default 70/15/15,
user-editable), `split_applied` (**false** — k-fold is what runs) and
`split_note` citing methodology §6.1's rejection of single splits. The
split fields are recorded because you asked for them; they are never
presented as having produced a metric.

**Metrics** — exactly the set your methodology §2/§9 selected:
`accuracy` and `f1` for classification, `rmse` for regression. Each
stored as **mean and standard deviation across the 10 folds**, plus the
full per-fold array. Also `n_features_in` and `n_features_selected`, so
feature selection's actual effect is measurable rather than inferred.

No other model metric is recorded, because §9 of your methodology
deliberately selected this set (accuracy alone is misleading under class
imbalance; F1 addresses it; RMSE for regression). Adding ROC-AUC or
precision/recall would be an amendment to that section — see
`SCOPE-DECISIONS.md` Decision 2.

**Dataset characteristics** (copied onto every row, so trends don't need
a join) — `n_rows`, `n_features`, `n_numeric`, `n_categorical`,
`missing_pct`, `class_balance`, `mean_abs_correlation`, `task_type`.

**Outcome** — `status` (succeeded/failed/skipped), `error_type`,
`error_message`, `log_path`, `config_yaml`.

That is ~60 recorded fields per run, every one of them either measured
or copied from the engine's own output. Nothing derived or estimated is
stored as if measured.

### Trends tab

Because every field above is a real column, the Trends tab is mostly
"pick x, pick y, pick grouping":

```
┌──────────────────────────────────────────────────────────────────────────────────┐
│  Compose │ Runs │ Network │ ●Trends                                              │
├──────────────────────────────────────────────────────────────────────────────────┤
│  x: [selection method ▾]  y: [mean accuracy ▾]  group: [model ▾]                 │
│  filter: dataset=[all ▾] task=[classification ▾] machine=[this one ▾]            │
├──────────────────────────────────────────────────────────────────────────────────┤
│  0.95┤                      ╭── grad-boost                                       │
│      │        ╭─────────────╯                                                    │
│  0.90┤   ╭────╯        ╭──── random-forest                                       │
│      │╭──╯      ╭──────╯                                                         │
│  0.85┤╯    ╭────╯  ────────── logreg                                             │
│      └──────────────────────────────────────                                     │
│       none  chi2  mutinf  rfe  lasso                                             │
├──────────────────────────────────────────────────────────────────────────────────┤
│  Preset views:  accuracy vs wall-time (cost/benefit)  ·  tuning gain by model     │
│                 scaling effect by model family  ·  selection effect by n_features │
│                 does imputation matter more as missing_pct rises?                 │
└──────────────────────────────────────────────────────────────────────────────────┘
```

The "accuracy vs wall-time" preset is the one your resource-recording
requirement unlocks: it answers *was the tuning worth the compute*,
which the current artefacts cannot ask at all.

---

## 5. Evaluation design — SETTLED 2026-10-09

Decided against your four secondary research questions
(`Chapter_1_Colile.docx` §1.6) and your methodology analysis §6/§9.
`SCOPE-DECISIONS.md` Decision 1 has the full reasoning.

### Primary protocol: stratified k-fold, k = 10

This is what executes. Chosen because three of your four secondary
questions cannot be answered without a variance estimate:

| Your question | Requires | Why a single split fails |
|---|---|---|
| SQ1 — greatest and **most consistent** impact | spread, not just a mean | "consistent" is a claim about variance |
| SQ2 — preprocessing × model interaction | reliable per-cell estimates | noisy on small n |
| SQ3 — effects **moderated by sample size** | comparable estimates on *small* datasets | 15% of iris = 22 rows; 1 error = 4.55 points, while the real effect to detect is +7.3 (CI 2.5-12.1) |
| SQ4 — **mechanisms** (critical realist layer) | effects stable enough to explain | cannot separate a real effect from partition luck |

SQ3 is decisive: dataset size is itself one of your variables, so a
protocol that degrades on small datasets would conflate "the effect
really vanishes on small data" with "my measurement got noisy" — the
opposite conclusions. Friedman + Wilcoxon (methodology §2) also need
repeated per-dataset measurements, which one split cannot supply.

Recorded per run: per-fold score arrays, mean **and sd** for each of
accuracy / F1 (classification) and RMSE (regression), `cv_k = 10`,
`cv_strategy = stratified_kfold`, and `fold_assignment_hash`.

### Hyperparameter tuning: nested CV (inner k = 3)

The one genuine overfitting risk in this design. Tuning on the folds
that are also reported selects hyperparameters *to fit those folds* —
optimistically biased even though no individual fold leaked. So:

```
outer fold 1..10          (reporting — scores the winner)
  └─ training 90% → inner CV 1..3   (tuning only)
                      └─ pick best hyperparameters
     → refit on the full 90% with those params
     → score on the held-out 10%    ← honest, never seen by tuning
```

Cost: 30 fits per configuration instead of 10. `inner_k` is recorded so
this cost is visible in the trend data (the "was tuning worth the
compute" question). Feature selection has the same leakage risk and is
handled the same way — fitted strictly inside the training fold, proven
by a fit-spy test (step 3).

### Your 70/15/15, honoured two ways without misleading

**(a) Recorded on every run as declared metadata.** `split_train`,
`split_val`, `split_test` (default 70/15/15, editable in the composer),
with `split_applied = false` and a `split_note` citing methodology §6.1.
The fields exist for your trend mining; no metric is ever shown that no
run computed.

**(b) Available as a labelled secondary protocol, gated to datasets
where it is statistically defensible.** Repeated holdout, 30 x
70/15/15, on datasets with **n >= 4,000** only:

| Dataset | n | 15% test | Defensible? |
|---|---|---|---|
| adult | 48,842 | ~7,326 | yes |
| bank-marketing | 45,211 | ~6,782 | yes |
| house_16H | 22,784 | ~3,418 | yes |
| abalone | 4,177 | ~627 | yes |
| credit-g | 1,000 | 150 | no — below gate |
| iris | 150 | 22 | no — below gate |

30 repeats answer §6.1's actual objection (which was to a *single*
split, not to holdout as such) and still yield a mean +/- sd, so this is
a genuine robustness check that *supports* Chapter 1 rather than
contradicting it. Runs carry `protocol = repeated_holdout_30`,
`split_applied = true`, and are never pooled with k-fold runs in the
same comparison.

### Statistical design — SETTLED 2026-10-09

**Friedman + Wilcoxon signed-rank with Holm correction**, per
`methodology_analysis_Colile.docx` §7.2, which works through Demsar
(2006) and Fernandez-Delgado et al. (2014). Nemenyi appears **zero
times** in that 73KB document; the Nemenyi critical differences in the
existing B1/B2 artefacts came from the simplified build, not from this
plan.

Why Wilcoxon suits this design specifically:

- **OFAT compares against a named baseline**, not all pairs. The
  question is "does standard scaling beat *no scaling*?", so the test
  should be baseline-referenced. Nemenyi spends power on comparisons the
  design does not ask for (minmax vs robust), and its conservatism is
  why B1's scaling result needed a 1.271 gap to clear a 0.957 CD.
- **It preserves per-dataset pairing**, which SQ4 (the critical-realist
  mechanism layer) needs: you can ask *which* datasets drove a
  difference. Nemenyi collapses everything to mean ranks and discards
  that structure.

**Holm, not Bonferroni.** §7.2's body permits either ("Bonferroni or
Holm procedure"); only the summary table shortens it to Bonferroni. Holm
is uniformly more powerful, controls family-wise error identically,
is what Demsar recommends, and is already what B2's reported results
use. At 10 pairs (the selection sweep) Bonferroni tests everything at
0.005 while Holm steps 0.005, 0.0056, 0.00625 - which decides borderline
findings across 17 datasets.

```
Friedman across the component's levels        (global: do these differ?)
  └─ if significant:
       Wilcoxon signed-rank, each level vs the Chapter 1 BASELINE
         └─ Holm correction across those comparisons
       + effect size (median paired difference + 95% CI) on every result
```

Two deliberate choices:

- **Baseline-referenced by default.** 5 selection levels means 4
  comparisons against `none`, not 10 all-pairs - which halves the
  correction burden and matches what OFAT asks. All-pairs remains
  available as a secondary view.
- **Effect sizes are mandatory.** §7.2 identifies the real weakness of
  rank tests, that "a 10-percentage-point difference and a
  0.1-percentage-point difference contribute equally to the rank", and
  requires practical effect size as the remedy. The run record stores the
  median paired difference and its CI, and no p-value is displayed
  without one.

## 6. Build order

Each step is independently verifiable, mirroring how
`experiment-dashboard` was built. ⚠ = correctness-critical.

| # | Step | Verification |
|---|---|---|
| 1 | `pipeline-lab-engine/` skeleton + config schema + `run_experiment.py --config` CLI | A minimal config runs end to end and writes one row |
| 2 ⚠ | `components/` — scaling, imputation (incl. **drop-rows**, the Ch.1 baseline), **encoding (onehot/ordinal/target)**, **selection**, **tuning** as sklearn-compatible factories | Unit test per technique: fits inside a CV fold, no leakage (fit-spy assertion, as prepfx proves its own). **Target encoding additionally: a pure-noise feature must not beat chance** |
| 3 ⚠ | `pipelines/compose.py` — build a leakage-safe 6-stage Pipeline from a config | Test: selection sees only training-fold data; tuning's inner CV nests inside the outer fold |
| 4 ⚠ | `provenance/` — resource + environment capture | Run a known-cost workload; wall/cpu/peak-RSS within sane bounds; all env fields non-null |
| 5 ⚠ | `storage/` — SQLite schema + writer | Schema matches §4 exactly; one row per combination; re-running appends, never overwrites |
| 6 ⚠ | `evaluation/` — stratified k=10; **nested CV (inner k=3) for tuning**; repeated-holdout secondary protocol behind the n>=4,000 gate | Per-fold arrays + sd recorded; `fold_assignment_hash` identical for identical seeds; nested test proves tuning never sees the outer fold; holdout refuses a dataset below the gate |
| 6b ⚠ | `statistics/` — Friedman, then baseline-referenced Wilcoxon signed-rank with **Holm** correction, plus median paired difference + 95% CI | Reproduces a known worked example; Holm rejects a superset of Bonferroni on the same input; no p-value is returned without an effect size |
| 7 | `engines/lab.py` adapter in this repo (log markers, choices, results) | Reuses `core/runner.py` unchanged; `run_status` correctly reports a deliberately broken config as failed |
| 8 | `GET/POST /api/lab/*` — sweep expansion, cost estimate, launch batch | POST a 3-column composer payload → correct run count, correct YAML per run |
| 9 | Compose tab (drag-and-drop grid) | Browser: build 3 configs, see live run counts, launch; invalid column blocks with the engine's own reason |
| 10 | Runs tab + full run record view + compare | Browser: two runs side by side; every §4 field present and non-null |
| 11 | Network tab | Browser: layered graph matches the real sweep; node/edge stats match a direct DB query |
| 12 | Trends tab + presets + CSV export | Each preset's plotted numbers match a direct SQL query over `lab.db` |
| 13 | End-to-end: compose → run → network → trend, fresh install | Fresh venv, `start.bat`, full walkthrough, no manual edits |

Estimated: steps 1–6 are the bulk (new experimental code, needs careful
leakage testing); 7–13 reuse this repo's existing, tested machinery.

---

## 7. Risks and honesty constraints

- **Combinatorial blow-up — already solved by your own design choice.**
  Full factorial is 4 scaling × 4 impute × 5 select × 4 model × 4 tune ×
  ~17 datasets ≈ **21,760 runs**: weeks of compute on a machine that has
  already hit 0 bytes free disk and runs at ~2 GB free RAM. Your
  methodology §4 selected **OFAT** precisely to avoid this, and OFAT is
  ~272 runs per component sweep (~1,400 for all five) — feasible.
  The composer therefore defaults to OFAT and *flags* any column that
  varies more than one component. Full factorial stays reachable but
  behind an explicit cost confirmation. Also: live run-count/time
  estimate before launch, a max-runs-per-batch guard, and resumable
  batches so an interrupted sweep is not lost.
- **Leakage is the real correctness risk.** Feature selection and
  hyperparameter tuning are exactly the two stages that leak if fitted
  outside the fold. Tuning needs *nested* CV. Step 2/3 tests must prove
  this with a fit-spy, the way prepfx already proves its own.
- **Nothing fabricated.** If a metric or a split did not actually run, it
  is recorded as not-run with a reason, never shown as a number. The
  split question in Decision 1 exists precisely so this stays true.
- **The frozen record stays frozen.** No file under
  `preprocessing-effects-framework/` or
  `Artefact/Research_Impact_of_Preprocess/` is modified. New capability
  lives in `pipeline-lab-engine/`.
- **Statistical post-hoc differs from the existing artefacts.** Your
  methodology §2 selects Friedman + **Wilcoxon post-hoc with Bonferroni**;
  both existing engines implement Friedman + **Nemenyi** instead, and the
  chapters already report Nemenyi critical differences. The new engine
  should follow one or the other deliberately, not by accident — see
  `SCOPE-DECISIONS.md`.

- **Thesis implications are yours, not mine.** This engine implements the
  *original five-component* design, which is broader than the two-factor
  arms already written up. Whether and how its results enter the thesis
  is a supervisor conversation; the artefact will keep them clearly
  separable from the frozen B1/B2 record.

- **The 70/15/15 request conflicts with your Chapter 1.** Flagged
  prominently in `SCOPE-DECISIONS.md` Decision 1 rather than silently
  resolved either way. The plan as written keeps k-fold as the real
  protocol and records the split ratios as metadata; option B there
  (repeated holdout as a labelled secondary protocol) is the path that
  would genuinely satisfy both your request and §6.1's objection.
