# Pipeline Lab: A Reproducible Experimentation System for Measuring Preprocessing Effects on Tabular Model Performance

**Research report — ITRI671 Honours Research Project**
Colile Sibanda · North-West University · 16 October 2026

---

## Executive summary

This report presents **Pipeline Lab**, a purpose-built experimentation
system for measuring how preprocessing choices affect tabular model
performance, together with the empirical findings it produced across
**4,377 recorded experimental runs** over 25 datasets, four model
families and five preprocessing factors.

The system is the contribution. The findings matter, but they are
findings *of a particular kind*: they are reproducible, provenance-
tracked, leakage-proofed, and in several cases they are corrections of
results that a less rigorous instrument would have reported as true. The
central claim of this report is that **the instrument determined the
quality of the findings**, and that three of the most valuable outcomes
of the project — a withdrawn significant result, a quantified
measurement artefact, and a discovered power ceiling — were only
obtainable because the system was built to make them visible.

Headline empirical results:

- Of 167 statistical cells tested, **25 contrasts survived Holm
  correction**. Most preprocessing choices produced no detectable effect.
- **Preprocessing effects are model-specific, not pipeline-general.**
  Scaling matters for logistic regression and SVM and is irrelevant to
  tree ensembles; tuning matters for gradient boosting and almost nothing
  else.
- **Encoding produced no detectable effect anywhere** across 20 tested
  cells.
- **Hyperparameter tuning consumed 67% of all compute (54.4 of 81.4
  hours) and produced one rejected contrast.**
- A previously-reported significant result (Bayesian tuning improving the
  SVM) was **found to be an artefact and withdrawn** after the system
  exposed that random and Bayesian search had silently degenerated into
  grid search.

---

## 1. Introduction and research problem

### 1.1 Background

Applied machine learning practice on tabular data involves a sequence of
preprocessing decisions — how to encode categorical variables, how to
handle missing values, whether to scale features, whether to select a
feature subset, and whether to tune hyperparameters. These decisions are
routinely made by convention or by habit. The literature offers
guidance on individual techniques, but comparatively little systematic,
controlled evidence on *which of these decisions actually change outcomes
and by how much*, measured consistently across models and datasets.

### 1.2 Problem statement

Three difficulties make this question hard to answer credibly:

1. **Leakage.** Preprocessing fitted on the full dataset before
   cross-validation inflates scores. Much published comparison work is
   vulnerable to this, and it is invisible in the results.
2. **Confounding.** Changing several pipeline stages at once makes it
   impossible to attribute an effect to any one of them.
3. **Irreproducibility.** Without recorded environment, seed, data
   version and code version, a result cannot be re-derived or audited.

### 1.3 Research objectives

| # | Objective |
|---|---|
| O1 | Build a system that measures single-factor preprocessing effects without leakage, with full provenance, and with an append-only record |
| O2 | Apply a one-factor-at-a-time (OFAT) design across five preprocessing factors, four models and a dataset registry |
| O3 | Establish which effects are statistically supportable and which are not, using a pre-committed statistical framework |
| O4 | Quantify the computational cost of each factor against the evidence it yields |
| O5 | Determine whether results depend on the evaluation protocol |

### 1.4 Scope and delimitation

The study covers supervised learning on tabular data, classification and
regression, with four model families. It uses a one-factor-at-a-time
design and therefore **does not measure interactions between
preprocessing factors** — that is the subject of Part 2 of the research
programme. Deep learning, time-series, text and image data are out of
scope.

---

## 2. The system: Pipeline Lab

The system is the core artefact of this research. It comprises an
experimental engine, a run record, a statistical analysis layer, and a
web dashboard.

### 2.1 Architecture

```
                    ┌─────────────────────────────────────┐
                    │        Web dashboard (FastAPI)      │
                    │  11 pages · 287 tests               │
                    │  compose · run · explore · findings │
                    └──────────────┬──────────────────────┘
                                   │  engine adapter layer
            ┌──────────────────────┼──────────────────────┐
            │                      │                      │
      ┌─────▼─────┐          ┌─────▼─────┐          ┌─────▼─────┐
      │  prepfx   │          │    B2     │          │    lab    │
      │ (B1 repo) │          │ (B2 repo) │          │  (engine) │
      └───────────┘          └───────────┘          └─────┬─────┘
                                                          │
   ┌──────────────────────────────────────────────────────▼────────┐
   │                    piplab engine (342 tests)                  │
   │                                                               │
   │  config ──► datasets ──► pipelines ──► evaluation ──► storage │
   │     │          │            │              │            │     │
   │  YAML      loaders +    leakage-safe    k-fold /     89-column│
   │  OFAT      missingness  ColumnTransf.   repeated     append-  │
   │  contract  injection    + Pipeline      holdout      only DB  │
   │                                                               │
   │  components: encoding · imputation · scaling · selection ·    │
   │              tuning · models                                  │
   │  statistics: Friedman ──► Wilcoxon ──► Holm (+ effect sizes)  │
   │  provenance: environment · resources · git SHA                │
   └───────────────────────────────────────────────────────────────┘
```

### 2.2 Design principles

**Leakage safety is structural, not procedural.** Every transform is
composed inside an sklearn `Pipeline`, so scikit-learn fits it on the
training fold only:

```
ColumnTransformer( numeric:     impute → scale
                   categorical: impute → encode )
  → select
  → model
```

Two stages are deliberately *not* composed: `drop_rows` (a transformer
may not change sample count, so the evaluator applies it before folds are
built) and tuning (which wraps the whole pipeline so selection is
re-fitted inside the inner search).

This is enforced by **six dedicated leakage proofs** using a `FitSpy`
wrapper that records exactly what each transformer was fitted on,
including `test_selection_never_sees_a_test_fold`,
`test_selection_is_refitted_per_fold_not_once_globally`, and
`test_inner_fits_are_strictly_smaller_than_the_outer_training_part`.

**The OFAT contract is enforced by the configuration layer.** A config
declares one `vary` factor and a `baseline` for every other component;
the loader refuses a config whose baseline pins the varied component.
Attribution is therefore guaranteed by construction.

**The record is append-only and comprehensive.** Every run writes one row
with **89 columns**, covering not just scores but:

| Group | Examples |
|---|---|
| Identity | `run_id`, `batch_id`, `config_name`, `engine_git_sha` |
| Factor levels | `encoding`, `imputation`, `scaling`, `selection`, `tuning`, `model` |
| Protocol | `protocol`, `cv_k`, `inner_k`, `holdout_repeats`, `fold_assignment_hash` |
| Results | `accuracy_mean/sd`, `f1_mean/sd`, `rmse_mean/sd`, `fold_scores_json` |
| Data characteristics | `n_rows`, `rows_dropped`, `missing_pct`, `class_balance`, `mean_abs_correlation` |
| Cost | `wall_seconds`, `cpu_seconds_user/system`, `peak_rss_mb`, `parallel_efficiency` |
| Environment | `cpu_model`, `ram_total_gb`, `os_version`, `python_version`, all library versions |
| Outcome | `status`, `error_type`, `error_message`, `substitution_note` |

Crucially, **skipped and failed runs are recorded with their reasons**,
not silently dropped. A null result and an absent result are
distinguishable in the record.

**Statistics are pre-committed and refuse to over-report.** The analysis
layer implements Friedman → baseline-referenced Wilcoxon → Holm. Post-hoc
comparisons are *only* computed when the global test is significant; when
it is not, the API returns an explicit `skipped_reason` rather than
pairwise results the global test does not license. A `Comparison` object
**cannot be constructed without an effect size** — the API makes it
structurally impossible to report a p-value without practical magnitude.

**Substitutions are recorded, never silent.** Where a technique cannot
legally apply (chi² on a regression target, chi² on negative features,
L1 logistic regression on a multiclass target), the system substitutes a
defensible alternative and writes the reason to `substitution_note` on
the run.

### 2.3 Missingness injection

The registry's natural missingness proved nearly absent (section 4.4), so
the system includes a controlled missingness injector supporting MCAR and
MAR at specified rates. It is a **bit-identical port** of the B2
artefact's injector, verified by a test that loads the B2 implementation
by path and compares masks. Twelve tests govern it, including that the
realised rate matches the requested rate, that categorical columns are
never touched, that MAR missingness genuinely depends on a driver column
while MCAR does not, and that injecting on top of natural missingness is
refused.

### 2.4 The dashboard

An 11-page FastAPI application (287 tests) provides compose, run,
explore, trends, network, findings and results views over the record. It
opens the database strictly read-only — a test asserts that a write
actually raises — so the UI can never corrupt the record. Its Findings
page re-implements the statistical framework and is **pinned by test to
agree with the engine's own analysis**, so the interface cannot drift
from the thesis.

Through the adapter layer the dashboard drives **three engines**: the B1
repository (`prepfx`), the B2 repository (`b2`), and the new engine
(`lab`), from one interface.

---

## 3. Methodology

### 3.1 Experimental design

One-factor-at-a-time across five factors. Each run fixes every component
at its Chapter 1 baseline and varies exactly one.

| Factor | Levels | Baseline |
|---|---|---|
| Encoding | onehot, ordinal, target | onehot |
| Imputation | drop_rows, mean, median, knn | drop_rows |
| Scaling | none, standard, minmax, robust | none |
| Selection | none, chi2, mutual_info, rfe, lasso | none |
| Tuning | none, grid, random, bayesian | none |

Models: logistic regression, SVM, random forest, gradient boosting.
Seed: 671 throughout.

### 3.2 Evaluation protocols

**Primary:** stratified 10-fold cross-validation. **Secondary:** 30×
repeated 70/15/15 holdout, restricted to datasets of at least 4,000 rows
where a 15% test set is meaningful. Tuning uses nested CV with an inner
3-fold loop, so hyperparameter selection never sees the outer test fold.

### 3.3 Statistical framework

Friedman test across levels at α = 0.05; if and only if significant,
Wilcoxon signed-rank of each level against the baseline, Holm-corrected
across the family. Effect sizes (median difference, bootstrap CI at
10,000 resamples, win/loss/tie counts) accompany every comparison.

### 3.4 Record integrity

`pragma integrity_check` and a duplicate-cell query before every commit
of the database. Where a bug invalidated runs, the uncommitted database
was reverted and the sweep restarted from scratch rather than leaving
known-bad rows in an append-only record (this occurred twice; both are
documented in the process log).

---

## 4. Findings

Full statistical detail, including all six master figures, is in the
companion [FINDINGS-REPORT.md](FINDINGS-REPORT.md). This section
summarises.

### 4.1 Scope of evidence

| | |
|---|---|
| Runs recorded | 4,377 (4,105 succeeded, 236 skipped, 36 failed) |
| Datasets | 25 |
| Compute | 81.4 wall hours / 71.0 CPU hours |
| Statistical cells tested | 167 |
| Significant global tests | 28 |
| **Contrasts surviving Holm** | **25** |

### 4.2 Most preprocessing choices do not matter

| Factor | Cells | Significant | Rejected |
|---|---|---|---|
| Scaling | 26 | 2 | 1 |
| Encoding | 20 | 0 | 0 |
| Imputation | 84 | 20 | 21 |
| Selection | 20 | 5 | 0 |
| Tuning | 17 | 1 | 1 |

The imputation arm's apparent dominance is a design artefact: it was
swept at six controlled missingness settings while other factors were
swept once.

### 4.3 Effects are model-specific

**Scaling.** Logistic regression is the only model with a Holm-rejected
gain (standard vs none, Holm = 0.0410, better on 10 of 11 datasets). SVM
shows the largest raw movement in the study — macro-F1 from 0.579 to
0.787 on adult (+20.8 points) and 0.477 to 0.708 on bank-marketing
(+23.1) — but on only two datasets, so it is reported as a direct
reading, not a tested result. Tree ensembles are flat everywhere.

**A verified mechanism.** On house_16H, scaling improves LinearRegression
RMSE by 7.7%, which appears to contradict the scale-invariance of least
squares. Direct investigation found the cause: one feature has standard
deviation ≈ 66,000 while the other fifteen are below 0.34, giving a
condition number of 1.4×10⁷. scikit-learn's solver discards singular
values below `tol × largest`, so it reports **rank 9 of 16** on raw data
and 16 of 16 when scaled. Setting `tol=1e-9` on raw data restores full
rank and reproduces the scaled RMSE exactly (45,539.1 both ways).

The estimator is scale-invariant; the unscaled model simply was not the
full model. **On data with one dominant-scale feature, failing to scale
can silently remove features from a linear model, with no error raised.**

**Tuning.** Gradient boosting is the only model large-dataset tuning
reliably moves (+1.4 to +1.9 F1 points; 4.5–7.3% RMSE reduction).
Logistic regression and random forest barely move. Grid, random and
Bayesian search are indistinguishable from one another.

### 4.4 Imputation: the answer depends on the question

Read against `mean`, kNN beats mean imputation in 9 cells, concentrated
at 15% and 30% missingness; median is significantly *worse* than mean for
regression in 5 of 6 sweeps, worse on all 9 datasets in three of them.

Read against `drop_rows`, the same data appears to show that deleting
rows beats imputing on regression. **This is an artefact.** `drop_rows`
is not scored on the same data: on bodyfat at 15% MCAR it keeps 38 of 252
rows and posts RMSE 0.21 against mean imputation's 2.90 — a 14×
"advantage" earned by discarding 85% of the data and scoring on an easy
complete-case remnant. The effect is systematic across the arm.

**The natural-missingness arm tests almost nothing**: 15 of 19 datasets
have 0.00% missing values. The resulting null cannot distinguish "imputer
choice does not matter" from "imputer choice was never tested", and is
reported as the latter.

### 4.5 Cost against evidence

Tuning consumed **54.4 of 81.4 wall hours (67%)** and produced **one**
rejected contrast. A single `random_forest` tuning fit on adult measured
at 1,259–1,379 seconds depending on search strategy; the large-dataset
tuning sweep alone ran 31.2 hours for 36 runs.

This is the clearest practical finding in the programme: **for these
models and datasets, hyperparameter tuning is the most expensive factor
per unit of evidence by a wide margin.**

### 4.6 Results do not depend on the evaluation protocol

Repeated 70/15/15 holdout (30 repeats) reproduces the k-fold record in
direction and magnitude across 16 paired cells, including the house_16H
rank-deficiency signature where minmax, standard and robust give
byte-identical RMSE. The mechanism is a property of the data and solver,
not of the protocol.

---

## 5. What the system made visible that a weaker instrument would not

Three outcomes justify the investment in the instrument.

### 5.1 A significant result was withdrawn

`ofat_tuning_v2` reported Bayesian search beating no tuning for the SVM
(p = 0.0145) — at the time, the programme's second-strongest finding.
Every hyperparameter grid held 4–6 candidates while random search drew
10, so **random search exhausted the grid and became grid search on all
56 model–dataset pairs**, and Bayesian search drew from the same handful
of points.

Given real continuous search spaces, the same contrast reads p = 0.2330
and the gain reverses on two datasets. Had v2 been reported as final, the
thesis would have claimed Bayesian tuning helps the SVM. It was measuring
how well Bayesian search rediscovers a small fixed grid.

**The bug produced plausible numbers and a publishable-looking result.**
It was caught only by an explicit check for identical scores across
search strategies.

### 5.2 A power ceiling was discovered

The selection arm produced five significant global tests — one at
p = 0.0009 — and **zero surviving pairwise contrasts**. This is not a
null result; it is arithmetic.

The Wilcoxon signed-rank test on *n* paired datasets has a smallest
attainable two-sided p of 2/2ⁿ. Holm multiplies the smallest of *k*
comparisons by *k*:

| n datasets | k levels | smallest attainable Holm p | can reject at 0.05? |
|---|---|---|---|
| 7 | 3 | 0.0469 | yes, barely |
| **7** | **4** | **0.0625** | **no — impossible** |
| 9 | 4 | 0.0156 | yes |
| 11 | 4 | 0.0039 | yes |

**At 7 regression datasets with 4 selection levels, no result could be
rejected, however large the true effect.** Three of the strongest global
signals in the entire programme were structurally undetectable before any
data was collected.

### 5.3 An artefact was quantified rather than reported

The `drop_rows` regression result (section 4.4) would, taken at face
value, have supported "delete rows rather than impute" for regression —
advice that is actively harmful. The system recorded `n_rows` and
`n_rows_before_deletion` on every run, which made the attrition
mechanism directly measurable rather than merely suspected.

---

## 6. Prior iterations, and why this one is final

This is the third iteration of the research instrument. The earlier two
remain in the record and are not discarded.

| | B1 (`prepfx`) | B2 (`Research_Impact_of_Preprocess`) | Pipeline Lab (`piplab`) |
|---|---|---|---|
| Design | Pre-registered, seed 20260702 | Seed 671, k=10, 672 runs | Seed 671, OFAT contract, 4,377 runs |
| Factors | Scaling, imputation | Scaling, imputation | Five factors |
| Record | `RESULTS.md` | `results/tables/*summary*.csv` | 89-column append-only SQLite |
| Provenance | Partial | Partial | Full environment, versions, git SHA |
| Leakage proofs | No dedicated tests | No dedicated tests | Six fit-spy proofs |
| Missingness control | None | Injector (MCAR/MAR) | Injector, bit-identical port, 12 tests |
| Statistical guard | Manual | Manual | API refuses unlicensed post-hoc |
| Interface | CLI | CLI | CLI + 11-page dashboard |

**Why the earlier iterations were insufficient, not wrong.** B1 and B2
produced real, usable results — the B1 confirmatory scaling finding (SVM
standardisation vs none, +7.3 accuracy points, 95% CI 2.5–12.1) and the
B2 imputation findings remain part of the programme's evidence, and the
B1/B2 divergence on imputation is reconciled in a separate comparison
document. Their limitations were structural rather than methodological
errors:

1. **Two factors, not five.** Neither could address encoding, selection
   or tuning at all.
2. **No controlled missingness in B1.** The imputation arm could only
   observe whatever missingness the datasets happened to have — which,
   as this iteration later discovered, is effectively zero for 15 of 19
   datasets. B1's "stable null at MCAR 15%" could not have been
   distinguished from an untested comparison.
3. **No structural leakage guarantee.** Both are believed leakage-safe,
   but neither can *prove* it per run; Pipeline Lab's fit-spy tests make
   the guarantee auditable.
4. **Flat-file records.** A CSV or Markdown table cannot record 89
   columns per run, cannot distinguish a skip from a failure from an
   absence, and cannot be queried for cost-versus-evidence analysis.

**Why this iteration is final.** It subsumes the earlier ones rather than
replacing them: the dashboard drives all three engines through a common
adapter, so B1 and B2 results remain accessible and comparable. It is
final because it closes the three gaps that bounded the earlier work —
factor coverage, missingness control, and record expressiveness — and
because its instrumentation is what surfaced the three corrections in
section 5. An instrument that cannot catch its own errors cannot be the
final one.

---

## 7. Further applications of the system

The system was built for one study but is not specific to it.

### 7.1 Immediate research applications

- **Interaction studies (Part 2).** The composition layer already accepts
  arbitrary level combinations; only the OFAT *contract* restricts it to
  one varied factor. Lifting that restriction for a factorial or
  fractional-factorial design is a configuration change, not a rewrite.
- **Benchmarking new preprocessing techniques.** A new scaler, imputer or
  selector is a single factory function plus tests; it inherits leakage
  safety, provenance and statistics for free.
- **Model comparison studies.** The model list is a registry; adding
  XGBoost, LightGBM or CatBoost is a registry entry.
- **Missingness mechanism research.** MNAR injection is the obvious
  extension to the existing MCAR/MAR injector.
- **Dataset characteristic studies.** The record stores `n_rows`,
  `n_features`, `missing_pct`, `class_balance` and
  `mean_abs_correlation` per run, so "which data characteristics predict
  whether scaling helps?" is answerable from the existing 4,377 rows
  without new experiments — a meta-analysis the data already supports.

### 7.2 Methodological and pedagogical applications

- **Reproducibility case study.** The system is a worked example of
  provenance-complete experimentation and could support methods teaching
  directly.
- **Teaching leakage.** The fit-spy harness demonstrates leakage
  concretely: students can watch a transformer see data it should not.
- **Power analysis instruction.** The discreteness-floor table in section
  5.2 is a teachable result about the limits of non-parametric testing.

### 7.3 Applied and industry applications

- **Preprocessing audit tooling.** Pointed at an organisation's own
  datasets, the system answers "does our standard preprocessing pipeline
  earn its cost on our data?" empirically.
- **Compute budgeting.** The cost columns support "what does this factor
  cost per unit of accuracy?" decisions — the question section 4.5
  answers for tuning.
- **Regression testing for ML pipelines.** The append-only record plus
  the statistical layer can detect when a pipeline change degrades
  performance beyond noise.

### 7.4 Engineering extensions

| Extension | Effort | Value |
|---|---|---|
| Parallel/distributed execution | Moderate | The 81-hour serial cost is the main scaling limit |
| MNAR injection | Low | Completes the missingness taxonomy |
| Additional model families | Low | Registry entries |
| Factorial design support | Moderate | Enables Part 2 interaction work |
| Result caching / resume | Moderate | Two restarts cost ~4 hours of recomputation |
| Automated power pre-check | Low | Would have caught the section 5.2 ceiling before data collection |

---

## 8. Recommendations

### 8.1 For practitioners

1. **Scale features for distance- and gradient-based models; do not
   bother for tree ensembles.** The effect is large for SVM and real for
   logistic regression, and absent for random forest and gradient
   boosting across every sweep.
2. **Treat scaling as a correctness issue, not only a performance one,
   when feature scales differ by orders of magnitude.** The house_16H
   case shows a linear model silently losing 7 of 16 feature directions
   with no warning.
3. **Do not expect encoding choice to change outcomes on average** — but
   avoid ordinal encoding for linear models specifically, where it cost
   7–8 F1 points on both large categorical datasets.
4. **Impute rather than delete rows**, and be aware that comparisons
   favouring deletion may be measuring sample attrition rather than
   quality.
5. **Prefer kNN over mean imputation when missingness is substantial
   (≥15%); avoid median for linear regression.** At low or absent
   missingness, the choice does not measurably matter.
6. **Budget hyperparameter tuning for gradient boosting and treat it as
   optional elsewhere.** It is the most expensive factor by a wide
   margin and benefits one model family.
7. **Do not pay for Bayesian search over random search** on these problem
   sizes; no search strategy outperformed another.

### 8.2 For researchers using this system

1. **Check the discreteness floor before collecting data.** Compute
   2/2ⁿ × k and confirm it is below α. A 6-dataset design clears α = 0.05
   but fails the α/3 Holm bar.
2. **Report the baseline choice as a research decision.** The imputation
   data supports opposite conclusions depending on the reference level;
   both readings belong in the write-up.
3. **Verify mechanisms before naming them.** The house_16H effect was
   first attributed to vague "numerical conditioning"; the real cause is
   specific, different and more useful.
4. **Ensure baselines are scored on the same data.** Any comparison where
   the baseline changes the test set needs that stated at the point of
   the claim.
5. **Check that a search budget is smaller than the search space.** A
   budget that exhausts the space is not a search, and the resulting
   numbers look entirely plausible.

### 8.3 For the programme

1. **Run SVM tuning on the large datasets** — the one remaining gap in
   the five-factor design, currently unmeasured in cost.
2. **Expand the regression registry past 7 datasets** before any further
   selection or tuning analysis on regression; the current n makes
   4-level comparisons undetectable.
3. **Add datasets with substantial natural missingness**, so the natural
   arm tests something.
4. **Mine the existing record** for dataset-characteristic predictors
   before running new sweeps; 4,377 rows with data-characteristic columns
   are already collected.

---

## 9. Future research directions

**Interaction effects (Part 2, in progress).** OFAT cannot see
interactions. Scaling and selection plausibly interact (both affect
feature geometry); imputation and missingness mechanism certainly do. The
system supports this with a design-contract change.

**Dataset-characteristic meta-analysis.** With `missing_pct`,
`class_balance`, `mean_abs_correlation`, `n_rows` and `n_features`
recorded per run, the question "which properties of a dataset predict
that preprocessing choice X will matter?" is answerable from existing
data. This is the highest-value next analysis because it requires no new
compute.

**Cost-aware preprocessing recommendation.** Given measured cost and
measured benefit per factor per model, a recommender could propose a
preprocessing budget for a new dataset. The record contains both halves.

**Extending to MNAR.** The hardest and most realistic missingness
mechanism, and the only one the injector does not cover.

**Replication on a different registry.** Every finding here is
conditioned on 25 specific datasets. The strongest test of the
model-specificity thesis would be replication on an independent registry.

**Protocol sensitivity at scale.** Repeated holdout agreed with k-fold on
16 cells; extending that comparison across the full registry would
strengthen or qualify the claim.

---

## 10. Limitations

- **OFAT cannot measure interactions.** Every result holds other factors
  at baseline.
- **n = 1–2 datasets on every large-dataset arm**, so those results are
  direct readings with no significance test behind them.
- **Natural missingness was effectively absent** (15 of 19 datasets at
  0.00%), so the uninjected imputation arm tests almost nothing.
- **SVM tuning on large datasets was never run**; its cost is unmeasured.
- **Effect sizes are not commensurable across datasets** with different
  target scales; sign and win-count are the reliable parts.
- **Single machine, single seed.** All runs used seed 671 on one machine;
  seed sensitivity was not studied.
- **Registry bias.** The 25 datasets are predominantly small, clean and
  drawn from standard repositories, which is not representative of
  production data.
- **The system itself had bugs** — two of which invalidated sweeps that
  were restarted. The instrument is auditable, not infallible.

---

## 11. Conclusion

This research produced a reproducible experimentation system for
measuring preprocessing effects on tabular data, and used it to record
4,377 controlled runs across five factors, four models and 25 datasets.

The empirical answer to the research question is **largely negative, and
usefully so**: most preprocessing choices produced no detectable effect,
encoding produced none at all, and the effects that do exist are specific
to particular model families rather than general properties of
pipelines. Hyperparameter tuning — by far the most expensive factor at
67% of total compute — yielded a single supportable contrast.

The methodological contribution is of equal weight. The system withdrew
one of its own significant results after exposing a degenerate search
budget, quantified a measurement artefact that would otherwise have
supported actively harmful advice, and discovered that five of its
strongest global signals were arithmetically impossible to confirm at the
sample sizes used. None of those three outcomes was available to the
earlier iterations of this instrument.

The practical lesson for the field is that **the credibility of a
preprocessing comparison is bounded by the instrument that produced it**.
Measuring preprocessing effects well requires leakage safety that can be
proven rather than assumed, records expressive enough to distinguish a
null from an untested comparison, statistics that refuse to over-report,
and power analysis performed before data collection rather than after.

---

## Appendix A — Artefact inventory

| Component | Location | Scale |
|---|---|---|
| Engine | `pipeline-lab-engine/src/piplab/` | 27 modules, 342 tests |
| Run record | `pipeline-lab-engine/outputs/lab.db` | 4,377 rows × 89 columns |
| Configurations | `pipeline-lab-engine/configs/` | 35 config files, 23 with recorded runs |
| Dashboard | `pipeline-lab/backend/`, `frontend/` | 11 pages, 287 tests |
| Process log | `pipeline-lab/docs/PROCESS-LOG.md` | Sections 1–4za |
| Findings report | `pipeline-lab/docs/FINDINGS-REPORT.md` | 6 master figures |
| Analysis scripts | `pipeline-lab/docs/analysis/` | Regenerate all figures and statistics |

## Appendix B — The 25 rejected contrasts

| Sweep | Model | Metric | Contrast | Holm p | Datasets better |
|---|---|---|---|---|---|
| scaling_v2 | logreg | accuracy | standard vs none | 0.0410 | 10/11 |
| tuning_v3 | svm (SVR) | RMSE | grid vs none | 0.0469 | 7/7 |
| mcar05 | svm | accuracy | knn vs mean | 0.0469 | 7/9 |
| mcar05 | svm | F1 | knn vs mean | 0.0469 | 7/9 |
| mcar05 | logreg | RMSE | median vs mean | 0.0078 | 0/9 (worse) |
| mcar15 | logreg | accuracy | knn vs mean | 0.0391 | 8/9 |
| mcar15 | logreg | accuracy | median vs mean | 0.0391 | 7/9 |
| mcar15 | logreg | RMSE | knn vs mean | 0.0078 | 8/9 |
| mcar15 | logreg | RMSE | median vs mean | 0.0078 | 0/9 (worse) |
| mcar15 | random_forest | RMSE | median vs mean | 0.0078 | 0/9 (worse) |
| mcar30 | svm | accuracy | knn vs mean | 0.0312 | 7/9 |
| mcar30 | svm | F1 | knn vs mean | 0.0156 | 8/9 |
| mar05 | logreg | RMSE | median vs mean | 0.0391 | 2/9 (worse) |
| mar05 | svm | RMSE | knn vs mean | 0.0391 | 7/9 |
| mar15 | logreg | accuracy | knn vs mean | 0.0156 | 8/9 |
| mar15 | logreg | F1 | knn vs mean | 0.0156 | 8/9 |
| mar15 | svm | F1 | knn vs mean | 0.0312 | 7/9 |
| mar15 | logreg | RMSE | knn vs mean | 0.0156 | 8/9 |
| mar15 | logreg | RMSE | median vs mean | 0.0195 | 2/9 (worse) |
| mar30 | random_forest | accuracy | knn vs mean | 0.0156 | 8/9 |
| mar30 | random_forest | accuracy | median vs mean | 0.0391 | 6/9 |
| mar30 | svm | accuracy | knn vs mean | 0.0469 | 7/9 |
| mar30 | random_forest | F1 | knn vs mean | 0.0156 | 8/9 |
| mar30 | logreg | RMSE | knn vs mean | 0.0273 | 7/9 |
| mar30 | logreg | RMSE | median vs mean | 0.0078 | 0/9 (worse) |

*Injected-missingness sweeps are read against `mean` with `drop_rows`
excluded, per section 4.4.*
