# Pipeline Lab: process log

What was built, what was found, what broke, and what is still open.
Written 2026-10-12. Covers the whole arc from the first dashboard build
to the analysis UI.

This is a working record, not a chapter. It is written so that a
supervisor, an examiner or a future maintainer can see not only what
the system does but **why each decision was taken and what evidence
forced it**. Where something was wrong and later corrected, both the
error and the correction are kept, because the correction is usually
the more useful half.

---

## 1. What exists now

Three codebases, deliberately separated so the two frozen research
artefacts are never modified:

| Component | Location | Role |
|---|---|---|
| **Engine** | `ITRI671 Project/pipeline-lab-engine/` | Runs experiments, writes the record. 262 tests |
| **Dashboard** | `671 Research June/pipeline-lab/` | Web UI for composing, running and reading results. 250 tests |
| **Frozen artefacts** | `preprocessing-effects-framework/`, `Artefact/Research_Impact_of_Preprocess/` | B1 and B2. Read and driven, never modified |

The record: **201 runs** in `pipeline-lab-engine/outputs/lab.db`, one
row each, 86 typed columns.

| Sweep | Runs | Datasets | Status |
|---|---|---|---|
| `ofat_scaling_full` | 97 | 13 classification | 89 succeeded, 8 skipped, adult partial |
| `ofat_scaling_regression` | 64 | 8 regression | all succeeded |
| `ofat_scaling_offline` | 40 | 5 bundled | all succeeded, first smoke sweep |

---

## 2. The design, and why it is shaped this way

### Five components, one varies at a time

The study measures five preprocessing decisions: **encoding,
imputation, scaling, feature selection, hyperparameter tuning**. Each
sweep varies exactly one and holds the other four at a declared
baseline. That is what makes an observed difference attributable.

The known cost is stated rather than hidden: **OFAT cannot see
interactions**. A full factorial would be roughly 65,280 runs, which is
not feasible on one laptop. The trade is deliberate and recorded in
`docs/PLAN.md`.

### k-fold, not a single split

The original request was for a 70/15/15 train/validation/test split.
That **contradicted Chapter 1**: `methodology_analysis_Colile.docx`
section 6.1 examines the single split and rejects it, citing Lones et
al. (2024) and Arlot and Celisse (2010), and section 6.3 selects
stratified k-fold at k = 10.

Rather than silently following either, the conflict was surfaced and
resolved with the user's own numbers: 15% of iris is 22 rows, so one
misclassification moves the score 4.55 points, against a real effect of
+7.3 points (95% CI 2.5 to 12.1). On that arithmetic a single split
cannot measure what the study is trying to measure.

**Resolution:** k = 10 is what executes. The split ratios are still
recorded on every run as declared metadata, with `split_applied = false`
and a `split_note` citing section 6.1, so the fields exist for trend
mining without any metric being shown that no run computed. Repeated
holdout (30 x 70/15/15) is built as a labelled secondary protocol,
gated to datasets with n >= 4,000.

### Statistics: Friedman, then Wilcoxon against baseline, Holm

Settled 2026-10-09 after the user asked which post-hoc fits the March
goals. **Nemenyi was rejected**: it appears zero times in the 73 KB
methodology document, it spends power on all-pairs comparisons the OFAT
design does not ask, and it discards the per-dataset pairing that SQ4's
mechanistic layer needs.

**Holm over Bonferroni**: section 7.2's body permits either, Holm is
uniformly more powerful at the same family-wise error guarantee, and
B2's reported results already use it.

Effect sizes are mandatory. Section 7.2 identifies the real weakness of
rank tests, that "a 10-percentage-point difference and a
0.1-percentage-point difference contribute equally to the rank". No
p-value is displayed anywhere without its effect size.

### Leakage proven, not asserted

Feature selection and tuning are where pipelines leak most easily, and
a leak inflates accuracy without raising an error. A `FitSpy` wraps each
stage and records the row identities, row count and a target
fingerprint at every fit. The tests are **non-vacuous**: a deliberately
leaky pipeline is built alongside the correct one, and the suite fails
if the spy does not catch it.

---

## 3. What the experiments found

### Classification: the one rejected result

`ofat_scaling_full`, 11 complete datasets, logistic regression,
accuracy:

| | value |
|---|---|
| Friedman | chi2 = 9.1415, **p = 0.0275** |
| standard vs none | p = 0.0137, **Holm 0.0410, rejected** |
| effect | median +0.0061, 95% CI [+0.0015, +0.0228] |
| wins | **better on 10 of 11 datasets** |

minmax reached p = 0.0537 raw but did not survive Holm (0.1074); robust
did not come close (0.2061).

**The SVM is the more interesting case.** Its per-dataset gains are far
larger than logistic regression's (wine +30.3 accuracy points,
credit-approval +20.8, heart-c +18.3), yet Friedman sits at p = 0.0530
and licenses nothing. This is the rank-test weakness section 7.2 names,
observed live: the test counts how often a thing wins, not by how much.

### Regression: more data removed the effect, and explained why

At **n = 6** the SVR result looked strong: Friedman p = 0.0169, robust
scaling better on 6 of 6 datasets. Two datasets were then added to
reach n = 8, and Friedman fell to **p = 0.2561**.

That is not noise. The raw numbers say why:

| dataset | std ratio | none | standard | minmax | robust | best |
|---|---|---|---|---|---|---|
| diabetes | 1.0 | 69.706 | 69.712 | 70.638 | 69.368 | robust |
| kin8nm | **1.0** | 0.0797 | 0.0798 | 0.0797 | 0.0798 | **none** |
| abalone | 11.7 | 2.266 | 2.157 | 2.292 | 2.169 | standard |
| concrete | 17.5 | 14.391 | 9.695 | 10.211 | **8.568** | robust |
| autoMpg | 307 | 4.351 | 3.398 | 3.635 | 3.417 | standard |
| energy-efficiency | 833 | 5.349 | 2.716 | 2.765 | **2.633** | robust |
| cpu_small | **170,204** | 7.464 | 7.765 | **4.336** | 4.451 | minmax |
| house_16H | 12,915,192 | 55348 | 55109 | 55301 | 55337 | standard |

"std ratio" is the largest feature standard deviation over the smallest.

- **kin8nm's features are already on one scale** (ratio 1.0), so scaling
  has nothing to correct: all four options agree to four decimals.
- **cpu_small's span 170,000x**, where scaling matters hugely, but
  **minmax wins, not robust**, breaking the clean sweep.

Robust's gain tracks feature spread, not anything about the scaler:
-0.19% and +0.48% on the flat-scale datasets, against +40%, +51% and
+40% where features are spread.

**This is a better finding than "robust wins" would have been.** The
rank test reports no global difference, but the mechanism is legible:
whether scaling matters depends on whether the features were on
comparable scales to begin with, which is a property of the data rather
than of the technique. That is the critical-realist layer SQ4 asks for,
and a rank test alone could not produce it; it needed the per-dataset
effect sizes the record stores. `house_16H` is the caution: a std ratio
of 13 million with a 0.02% effect, so spread alone does not guarantee
scaling pays.

### Honest notes

- **colic was skipped, all 8 runs.** 20% missingness against the
  `drop_rows` baseline leaves 7 of 368 rows, fewer than 10 folds. The
  engine refused with that reason rather than fabricating a CV.
- **Row deletion bit elsewhere**: adult 48,842 -> 45,222 (7.41%),
  credit-approval 5.36%, heart-c 2.31%.
- `logreg` on regression resolves to `LinearRegression`, which is
  invariant to affine rescaling, so its scaling contrast is necessarily
  null. Every such row carries a substitution note saying so.

---

## 4. The discreteness trap, and getting it wrong twice

The most instructive sequence in the project.

**First observation.** The regression arm at n = 5 reported
"no difference" for a contrast that won on 5 of 5 datasets. The
Wilcoxon signed-rank test is discrete: with n pairs the smallest
attainable two-sided p is `2 / 2**n`. At n = 5 that floor is **0.0625**,
so nothing can reach alpha = 0.05 however large the effect. Reporting
that as a null presents an arithmetic limit as evidence.

**First fix, which was wrong.** A warning was added comparing the floor
against alpha. It said six datasets would be enough.

**Second observation.** Finishing `house_16H` took the arm to n = 6, and
`robust vs none` landed exactly on the floor at p = 0.03125, won on 6 of
6, and was still not rejected. The warning had not fired.

**Why.** Holm tests the smallest of k comparisons at **alpha/k**, not
alpha. With three contrasts the bar is 0.0167, and the n = 6 floor of
0.03125 does not clear it.

| datasets | floor | clears alpha? | clears alpha/3? |
|---|---|---|---|
| 5 | 0.06250 | no | no |
| 6 | 0.03125 | **yes** | **no** |
| 7 | 0.01562 | yes | yes |

**Seven, not six, is the real minimum** for a three-level contrast. The
warning now derives the bar from the actual comparison count and names
the required n. Two datasets were added to reach n = 8 so the arm clears
with margin rather than sitting on the boundary.

Tests cover the n = 6 case specifically, and check the floor against
**what scipy actually returns** for a perfect-separation input rather
than against the formula itself, so the test cannot agree with a wrong
formula.

---

## 4b. What a full programme costs, measured

Measured 2026-10-12 by running all five sweeps end to end on one small
dataset, rather than extrapolating.

**One dataset, all five factors, 4 models, k = 10:**

| | |
|---|---|
| Runs | **80** (3 + 4 + 4 + 5 + 4 levels, x 4 models) |
| Model fits | **3,860** |
| Measured wall time (sonar, 208 rows) | **12.8 minutes** |

Per sweep, measured on sonar:

| sweep | runs | wall time |
|---|---|---|
| encoding | 12 | 14 s |
| imputation | 16 | 18 s |
| scaling | 16 | 19 s |
| selection | 20 | 27 s |
| **tuning** | 16 | **690 s** |

**Tuning is 90% of the bill.** Nested cross-validation turns one
configuration into 30 fits instead of 10, and the tree models under
tuning cost 111 to 134 s each against about 5 s for logistic regression
and SVM. The other four factors together are 78 seconds.

Scaled to larger datasets, using the per-fit timings in the record
(tree cost grows roughly linearly with rows, SVM quadratically; a
blended n^1.3 fits the observed points):

| dataset | rows | full programme |
|---|---|---|
| sonar, iris | ~200 | **13 min** (measured) |
| credit-g | 1,000 | ~1.6 hours |
| digits | 1,797 | ~3.4 hours |
| abalone | 4,177 | ~10 hours |
| cpu_small | 8,192 | ~1 day |
| house_16H | 22,784 | ~4 days |
| adult | 45,222 | ~9 days |

The practical reading: **the four non-tuning factors are nearly free**
even on mid-size data, and tuning is what makes a programme expensive.
Running the other four factors across all 20 datasets is a matter of
hours; adding tuning to the large datasets is not feasible on this
hardware.

### A real bug this exposed

The cost run failed 4 of 16 tuning runs with
`ImportError: Bayesian tuning needs optuna ... pip install optuna`,
while `import optuna` worked fine and `PROGRESS.md` recorded
"optuna 4.6.0 installed".

**Cause:** `OptunaSearchCV` moved out of the optuna package in 4.x and
now lives in the separate `optuna-integration` package. The error
message sent the reader to check a package that was already present.

**Fix:** pinned `optuna-integration[sklearn]==5.0.0` in the engine's
`requirements.txt`, and rewrote the error to name the right package and
say explicitly that having optuna alone is not enough. Re-ran the
sweep: **16 of 16 succeeded**.

This is the second time a dependency problem hid behind a passing local
environment, after the sklearn-in-the-dashboard leak. Both were found
only by executing real work.

---

## 4c. The four-factor programme, and a structural limit on imputation

Launched 2026-10-12 at 19:57. Four sweeps run in sequence: imputation,
encoding, scaling, selection. **1,216 runs** over 19 datasets (every
registry entry under 20,000 rows) and all four models at k = 10.
Estimated 7.7 hours, of which `cpu_small`, `kin8nm` and `abalone` are
81% because SVM is quadratic in rows.

Tuning is excluded on the measured 90/10 split from section 4b.

### A limit found before the results, not after

Checking the dataset characteristics while the sweep ran showed that
**only 4 of the 19 datasets have any missing values at all**:

| dataset | missing |
|---|---|
| colic | 20.14% |
| credit-approval | 0.65% |
| autoMpg | 0.22% |
| heart-c | 0.18% |

The other 15 are complete, so every imputation level returns an
identical score on them. Verified directly: on iris all four levels
agree to six decimal places, which is the correct behaviour (imputation
is a no-op when there is nothing to impute) but means those datasets
contribute exact ties.

Wilcoxon discards tied pairs, so the effective n for the imputation
post-hoc is **4, not 19**. The floor at n = 4 is 0.125 against a Holm
bar of 0.0167: **no imputation contrast can be rejected**, whatever the
effect. Friedman is weakened too, since ties shrink the statistic.

**Why this happens here and not in B1/B2.** Those studies *inject*
synthetic missingness (MCAR at 15% and so on). The lab engine
deliberately does not: it uses only naturally-occurring missing values.
That is a defensible choice, and it is also why the imputation arm
cannot reach significance on this dataset collection.

**This is reported, not worked around.** The sweep still produces valid
per-dataset effects, and the most useful one needs no significance test
at all:

> On colic, the Chapter 1 baseline `drop_rows` **destroys the dataset**:
> 368 rows become 7, fewer than the 10 folds requested, so all four
> models skip. Mean and median imputation both run and reach 0.83 to
> 0.87 accuracy. A baseline that cannot produce a score on a fifth of a
> dataset's values is itself the finding.

### What the imputation arm actually showed

Confirmed against the data once 279 of 304 runs had landed: **exactly 4
of 18 completed datasets show any variation across imputation levels**,
and they are precisely the four with missing values. The other 14 tie to
eight decimal places, as the mechanism requires.

On the three datasets with trivial missingness the choice barely
matters. On colic it is decisive:

| dataset | missing | drop_rows | mean | median | knn |
|---|---|---|---|---|---|
| colic (logreg) | 20.14% | **SKIP** | 0.8291 | 0.8345 | 0.8400 |
| colic (random_forest) | 20.14% | **SKIP** | 0.8673 | 0.8673 | 0.8616 |
| credit-approval (logreg) | 0.65% | 0.8606 | 0.8551 | 0.8580 | 0.8565 |
| heart-c (logreg) | 0.18% | 0.8413 | 0.8286 | 0.8318 | 0.8286 |
| autoMpg (svm, RMSE) | 0.22% | 4.3509 | 4.3316 | 4.3316 | 4.3315 |

The spread between mean, median and kNN is 0.1 to 2 percentage points
with no consistent winner across models. The spread between **having a
usable baseline and not** is the whole dataset.

**The finding this arm supports:** which imputation technique you pick
matters far less than whether your baseline can cope with the
missingness at all. That is a claim about the design choice rather than
about the techniques, and it needs no significance test, which is
fortunate because at an effective n of 4 none is available.

### Three further findings from the same arm

**1. kNN imputation is not expensive.** The common assumption is that
kNN costs far more than mean or median. Measured across 295 succeeded
runs it does not:

| level | runs | median wall time | total |
|---|---|---|---|
| drop_rows | 72 | 2.48 s | 671.8 s |
| mean | 76 | 2.08 s | 710.3 s |
| median | 75 | 2.06 s | 687.9 s |
| **knn** | 72 | **2.54 s** | **622.2 s** |

kNN's median run is 0.46 s slower than mean, and its *total* is the
lowest of the four because it never produced the pathological slow
cases the others did. On datasets of this size the cost argument
against kNN does not hold, which matters because B2 found kNN
significantly best for regression at low missingness. If it is both
better and no dearer, the case for it as a default is stronger than
the literature's usual framing.

**2. Only colic ever skipped.** 4 skipped runs, all colic, all
`drop_rows`, across all four models. No other dataset lost enough rows
to fall below the fold count. The baseline is safe on 18 of 19
datasets and catastrophic on the nineteenth, which is a sharper way to
state the risk than an average over all of them.

**3. The models disagree about the baseline.** On heart-c, `drop_rows`
is the *best* option for logistic regression (0.8413 against 0.8286 for
mean) and the *worst* for gradient boosting (0.7802 against 0.8024).
Dropping 7 rows of 303 helped one model and hurt another. At that
scale this is noise rather than mechanism, and it is a useful caution
against reading a single dataset-model cell as a result: it is exactly
the kind of difference the paired design across many datasets exists
to average out.

### Arm complete: the prediction held exactly

Finished 20:44, **304 of 304 runs in 2,832 s (47 minutes)**: 300
succeeded, 0 failed, 4 skipped, all 19 datasets reached. The 4 skips
were colic under `drop_rows`, across all four models, as expected.

Every one of the twelve testable cells came back non-significant:

| task | model | metric | Friedman p |
|---|---|---|---|
| classification | random_forest | accuracy | 0.8520 |
| classification | gradient_boosting | accuracy / F1 | 0.4936 |
| classification | logreg | accuracy / F1 | 0.1196 |
| classification | svm | accuracy / F1 | (same pattern) |
| regression | all four models | RMSE | **0.3916 for every model** |

The regression row is the tell. Four different models producing an
**identical** chi2 of 3.0000 is not a coincidence: it is the signature
of exactly one dataset varying while the rest tie. Confirmed directly -
of the seven regression datasets, only `autoMpg` (0.22% missing) moves
at all. The test is ranking six ties and one real observation.

This is the predicted outcome, not a surprise, and the prediction was
made and recorded **before** the arm finished.

Two honest ways forward, for Colile to choose:

1. **Report it as a descriptive result**, with colic as the worked
   example and the power limit stated. Costs nothing more.
2. **Add synthetic missingness injection** to the lab engine, matching
   B1/B2's MCAR design, so every dataset becomes informative and the
   arm reaches n = 19. More work, and it changes the engine's stated
   design, so it is a supervisor conversation rather than a code
   decision.

### The encoding arm has the same problem, and I said it would not

While the encoding arm ran I checked it the same way, and had to
correct myself. I had told Colile that "the other three arms have no
equivalent power problem". That is wrong for encoding.

**Only 3 of the 19 datasets have categorical columns at all:**

| dataset | categorical columns |
|---|---|
| credit-g | 13 |
| credit-approval | 9 |
| heart-c | 7 |
| ~~colic~~ | ~~19~~ - skips entirely, see below |

One-hot, ordinal and target encoding are all identity operations on a
purely numeric dataset, so the other 16 tie exactly, exactly as the
complete datasets tie in the imputation arm.

Effective n = **3**. The Wilcoxon floor at n = 3 is 0.25 against a Holm
bar of 0.025 for two contrasts. **Nothing in the encoding arm can be
rejected either.**

### A design consequence worth naming: the baseline removes a dataset

colic skipped **all 12** of its encoding runs, not just the ones under
a particular level. The reason is structural rather than accidental:
OFAT holds the other four components at their Chapter 1 baseline, and
the imputation baseline is `drop_rows`, which reduces colic from 368
rows to 7. That happens whatever the encoding level is.

So colic is usable in **exactly one arm** - imputation, the only arm
where `drop_rows` is varied away:

| arm | colic runs | skipped |
|---|---|---|
| imputation | 16 | 4 |
| encoding | 12 | **12** |
| scaling (earlier sweep) | 8 | **8** |

This is a real and reportable property of the OFAT design, not a bug:
**a baseline that destroys a dataset removes that dataset from every
other factor's evidence too.** The dataset with the most categorical
columns in the whole registry (19) contributes nothing to the encoding
question, because of a decision about missing values.

### Encoding arm complete: what the three informative datasets showed

Finished 21:12, **228 of 228 runs in 1,632 s (27 minutes)**: 216
succeeded, 0 failed, 12 skipped, all colic. Every testable cell came
back non-significant (Friedman p from 0.2231 to 0.7165), exactly as the
n = 3 power analysis predicted.

The descriptive content is in the three datasets that can respond:

| dataset | model | onehot | ordinal | target | best | spread |
|---|---|---|---|---|---|---|
| credit-approval (9 cat) | logreg | 0.8606 | 0.8667 | **0.8713** | target | 1.07 pts |
| credit-approval | random_forest | 0.8713 | **0.8760** | 0.8683 | ordinal | 0.77 pts |
| credit-g (13 cat) | logreg | **0.7470** | 0.7080 | 0.7350 | onehot | 3.90 pts |
| credit-g | random_forest | **0.7720** | 0.7480 | 0.7690 | onehot | 2.40 pts |
| credit-g | gradient_boosting | 0.7580 | 0.7560 | **0.7690** | target | 1.30 pts |
| heart-c (7 cat) | gradient_boosting | 0.7802 | 0.7870 | **0.8172** | target | 3.70 pts |
| heart-c | logreg | 0.8413 | 0.8443 | **0.8509** | target | 0.97 pts |
| heart-c | random_forest | 0.8308 | 0.8172 | **0.8341** | target | 1.69 pts |

**Target encoding won 5 of 12 cells and never lost badly.** That is
worth noting for a specific reason: target encoding is the one level
that leaks if it is not cross-fitted, and a leaking implementation
would show up as suspiciously *large* wins. It does not. The engine
uses sklearn's internal cross-fitting (`TargetEncoder(cv=...)`), the
leakage tests cover it, and these modest, mixed results are what a
correctly fitted target encoder looks like.

Ordinal encoding is the one that can misfire: it lost 3.90 points to
one-hot on credit-g with logistic regression, which is the expected
failure mode (imposing a false order on unordered categories hurts a
linear model most).

### A second baseline interaction: the SVM was disabled before encoding could matter

SVM showed **exactly 0.00 spread** across all three encodings on
credit-g and credit-approval. Investigated rather than assumed: on
credit-g the SVM scores 0.71000000 under every encoding, with a
macro-F1 of 0.474 against a class balance of 0.43. It is predicting the
majority class for every row.

The cause is the **scaling baseline**, not the encoding. This arm holds
scaling at `none`, and an unscaled RBF SVM on this data collapses to
the majority class. Encoding cannot move a model that is not
discriminating at all.

So the encoding arm loses the SVM entirely on its two largest
categorical datasets, for the same structural reason colic is lost:
**a fixed baseline in one component can silently remove a model or a
dataset from another component's evidence.** That is the sharpest
general lesson from this programme, and it applies to any OFAT design,
not just this one.

### Reproducibility confirmed bit for bit

The `scaling` arm of this programme deliberately repeats a factor
already swept earlier (`ofat_scaling_full`, two models), which makes an
unplanned but valuable check possible: the overlapping cells should be
*identical*, because both runs used seed 671 and the fold assignment is
hashed into the record.

Comparing every cell present in both sweeps:

```
12 overlapping cells, max absolute difference 0.00e+00
```

Not "close", not "within tolerance" - **exactly equal to every recorded
digit**, across two sweeps launched hours apart from different config
files. Seed control, fold assignment and the whole pipeline are
deterministic, which is what makes the results checkable by a third
party and the thesis defensible on reproducibility grounds.

### Scaling arm with four models: the clearest result of the programme

Finished 21:29, **304 of 304 runs in 1,035 s (17 minutes)**: 288
succeeded, 0 failed, 16 skipped (colic, all four scalers x four
models). This arm repeats the scaling factor with **all four models**
rather than the two the earlier sweep used.

The logistic regression result reproduced to every digit: Friedman
chi2 = 9.1415, p = 0.02747, standard vs none rejected at Holm 0.04102,
better on 10 of 11. The new information is the two models never tested
before, and together the four split exactly along the theoretical line:

| model | median change, standard vs none | wins | largest gain |
|---|---|---|---|
| **svm** | **+0.0510** | 9/11 | **+0.3033** |
| **logreg** | **+0.0061** | 10/11 | +0.0340 |
| random_forest | 0.0000 | 2/11 | +0.0067 |
| gradient_boosting | **0.0000** | **0/11** | **+0.0000** |

Checked further: gradient boosting produces **byte-identical accuracy
across all four scalers on 8 of 11 datasets**, random forest on 5 of
11. Where they differ at all the spread is 0.10 to 0.67 points, which
is tie-breaking noise in split selection rather than a scaling effect.

**This is textbook mechanism, measured.** A tree asks "is feature x
above threshold t?", and any monotonic rescaling moves x and t
together, so the split is unchanged. A support vector machine with an
RBF kernel measures distance between points, so a feature with a large
range dominates every distance until it is rescaled. Logistic
regression sits between: scaling does not change what it can represent,
but it changes how fast and how well the optimiser converges.

The practical statement this supports is sharper than "scaling helps":

> Scaling is essential for distance-based models, useful for
> gradient-based ones, and **provably irrelevant for tree ensembles**.
> Spending effort on it before a random forest is spending effort on
> nothing.

Note also the honest asymmetry in significance. The SVM has by far the
largest effect (+5.1 median, +30.3 maximum) yet sits at p = 0.0530 and
is not licensed, while logistic regression's far smaller +0.6 median
*is*. A rank test counts how often a thing wins, not by how much:
logistic regression won 10 of 11 narrowly, the SVM won 9 of 11 hugely,
and only the first clears the bar. This is precisely why methodology
section 7.2 makes effect sizes mandatory, and it is the clearest
example of it in the whole record.

### Selection arm: every effect points the same way, and it is downward

Finished 21:50, **380 runs in 1,251 s (21 minutes)**, then 16 repair
runs. Final: 360 succeeded, 20 skipped (colic), 16 failed rows retained
as history.

Median accuracy change against no selection, classification:

| model | chi2 | mutual_info | rfe | lasso |
|---|---|---|---|---|
| logreg | -0.0035 | **-0.0124** | -0.0052 | +0.0000 |
| svm | 0.0000 | 0.0000 | 0.0000 | 0.0000 |
| random_forest | -0.0088 | -0.0095 | **-0.0105** | -0.0031 |
| gradient_boosting | +0.0035 | -0.0002 | -0.0028 | +0.0000 |

**Almost every cell is negative.** RFE was worse on 9 of 11 datasets
for random forest, chi2 worse on 10 of 11. Two Friedman tests reached
significance (random_forest accuracy p = 0.0386, logreg F1 p = 0.0316)
but nothing survived Holm, so no single technique is singled out. The
direction, however, is consistent across 4 models and 4 techniques.

The mechanism is visible in the recorded feature counts:

| dataset | features in | chi2 / mutual_info / rfe keep | lasso keeps |
|---|---|---|---|
| digits | 64 | 32 | **47** |
| sonar | 60 | 30 | **12** |
| ionosphere | 34 | 17 | **27** |

The three filter methods keep exactly **half** the features, because
`resolve_k` uses a fixed k = n/2 rule. Discarding half the information
on datasets that were already curated for benchmarking costs accuracy
nearly everywhere. `lasso` is the exception and sits at or near zero
for three of four models, because it is **data-driven**: it keeps 47
of 64 on digits where the signal is spread, and only 12 of 60 on sonar
where it is concentrated.

**The finding:** on curated benchmark data, blind feature selection at
a fixed fraction is a net cost, while an embedded method that chooses
its own number is roughly free. That is a statement about the *k rule*
as much as about selection, and it is a design limitation of this
sweep worth stating: a sweep over k would separate "selection hurts"
from "keeping half hurts". The current evidence cannot distinguish them.

SVM shows exactly 0.0000 for every technique, which is the same
artefact seen in the encoding arm: under the `none` scaling baseline
the SVM collapses to majority-class prediction on these datasets, so
no selection choice can move it.

---

## 4d. The four-factor programme: final tally

All four arms complete, 2026-10-12, roughly 2 hours of wall-clock.

| arm | runs | time | succeeded | skipped | failed |
|---|---|---|---|---|---|
| imputation | 304 | 47 min | 300 | 4 | 0 |
| encoding | 228 | 27 min | 216 | 12 | 0 |
| scaling | 304 | 17 min | 288 | 16 | 0 |
| selection | 396 | 21 min | 360 | 20 | 16 |
| **total** | **1,232** | **~2 h** | **1,164** | **52** | **16** |

The record grew from 201 rows to **1,433**. Duplicate check after the
repair: **0 duplicated cells**.

### What is significant, after everything

| arm | result |
|---|---|
| **scaling** | **logreg: standard beats none, Holm p = 0.0410, better on 10/11.** The only rejected contrast in the programme |
| selection | two Friedman tests significant, nothing survives Holm; every effect negative |
| imputation | all null - effective n = 4 |
| encoding | all null - effective n = 3 |

One rejected contrast out of roughly forty tested cells. That is not a
disappointing yield: it is what honest multiple-comparison control
produces on 11 to 19 datasets, and the descriptive findings - trees are
provably scale-invariant, selection at a fixed k is a net cost, kNN
imputation is not expensive, a destructive baseline removes a dataset
from every other arm - are the substance.

---

## 4e. Committed to git, 2026-10-13

Two repositories initialised and committed, author Colile Sibanda
<colilesibanda@gmail.com> on both, short subject lines, no body.

| repo | commit | files | size |
|---|---|---|---|
| `pipeline-lab-engine` | `0d772f7` Pipeline Lab engine: five-component OFAT framework with run record | 59 | 6.0 MB |
| `pipeline-lab` | `eb8d97c` Pipeline Lab dashboard: compose, run and analyse experiments in the browser | 90 | 0.5 MB |

**`lab.db` is committed deliberately.** The engine's `.gitignore`
excluded `outputs/` and `*.db`, which would have left the research
record out of version control entirely. It is 5.8 MB, it holds all
1,433 runs and 151 minutes of compute, and it **cannot be regenerated
identically on other hardware** because the timings, peak memory and
machine fingerprint are part of the data. The ignore file now carries
an explicit exception with that reasoning written beside it.

Excluded per git-hygiene: both `.venv` directories (398 MB and 334 MB),
`data/cache/` (re-downloadable from OpenML), and the scaffolding files
`PROGRESS.md`, `TODO.md`, `plans.md` and `HANDOFF.md`. The
research narrative those carried lives in this document, which is
committed.

## 4f. The k-sweep decision, and why it was not executed today

Colile delegated the choice between the two open design questions.
**Option B, the k-sweep for feature selection, is the right one**, for
three reasons:

1. It rescues a result that **already exists**. The selection arm found
   that every technique costs accuracy, but cannot distinguish
   "selection hurts" from "keeping half the features hurts", because
   `DEFAULT_K_FRACTION` is fixed at 0.5. The finding is currently
   uninterpretable without it.
2. Option A, MCAR injection, would make the imputation arm testable,
   but B1 and B2 **already inject MCAR**. Doing it here arguably
   duplicates the existing studies rather than extending them, which is
   the weaker contribution.
3. The k-sweep uses the existing, tested component at different
   settings, so it cannot invalidate anything already recorded.

**It was not run today, and the reason is worth recording.** The
initial assessment was that it needed "config only, no code". That was
checked and found wrong: `resolve_k` accepts a `fraction` argument, but
all three call sites invoke it without one, so k is not reachable from
a config file. Two routes exist:

- thread `k_fraction` from the config through `evaluate` ->
  `build_pipeline` -> `LateResolvedSelector` -> `make_selector`, or
- encode it in the level name (`chi2@0.25`), which also needs changes
  to config validation and would pollute the recorded `selection`
  column that the analysis groups by.

Either is a real design change to an engine that was committed green
minutes earlier, with 258 passing tests. Making it at speed, without
the time to think through how the recorded column should represent k,
risks the integrity of 1,433 rows for a question that is not urgent.

**The honest position: the decision is made, the implementation is
deferred.** The caveat is already written into section 4c so the
selection result is not overstated in the meantime. When there is time,
the first route is preferable, with `k_fraction` recorded as its own
column rather than folded into the level name.

---

## 4g. k made configurable, and the queue after it

The k-sweep decision from 4f was implemented on 2026-10-13 rather than
left deferred. `k_fraction` now threads from the config through
`evaluate` -> `build_pipeline` -> `LateResolvedSelector` ->
`make_selector`, and is stored as **its own column** rather than folded
into the level name, so analysis can group by technique and by k
independently. Verified end to end: on sonar, 0.25 keeps 15 of 60
features, 0.5 keeps 30, 0.75 keeps 45.

**A migration trap caught before it bit.** Adding a schema column left
the live database at 86 columns while the schema declared 87, and
`CREATE TABLE IF NOT EXISTS` does nothing to a table that already
exists. Every write in the next sweep would have failed. `open_db` now
adds any missing column on open, ADD only, never dropping or retyping.
Tested on a **copy** of the real record first: 1,433 rows preserved,
`k_fraction` NULL on all of them, which is the honest value for runs
that predate the field.

Six new tests cover the behaviour, including that the k = 0.5 default
has one source of truth (`piplab.config`, which imports no sklearn) and
that lasso correctly ignores k because it is embedded and picks its own
count.

### Known inconsistency, recorded rather than patched mid-run

A **skipped** run records `k_fraction` as NULL. So does `cv_k`, and has
since the first sweep: `_record_failure` builds its row separately from
the success path and carries none of the protocol settings, even though
they are known regardless of outcome.

This was noticed while a sweep was actively writing to the same file,
so it was left alone rather than edited underneath a running process.
It affects only the skipped rows, which carry no score and are excluded
from every analysis, so nothing reported depends on it. Worth tidying
when the queue is idle.

### The queue, launched 2026-10-13

| order | sweep | runs | purpose |
|---|---|---|---|
| 1 | selection, k = 0.25 | 228 | with k = 0.5 already recorded... |
| 2 | selection, k = 0.75 | 228 | ...these separate "selection hurts" from "keeping half hurts" |
| 3 | scaling, large datasets | 36 | SQ3: adult, bank-marketing, house_16H |
| 4 | tuning | 256 | the fifth factor, never run |

Two scoping choices worth stating:

- The k-sweeps exclude `none` and `lasso`. k does not apply to the
  baseline or to embedded selection, so including them would only
  duplicate rows already recorded.
- The large-dataset sweep **excludes SVM**. One adult SVM fit exceeded
  600 CPU-seconds and was abandoned; at roughly O(n^2) on 45,000 rows
  the sweep would take days. This leaves the model with the largest
  scaling effect without large-dataset evidence. That is a stated gap,
  not an oversight: closing it needs hardware this project lacks.

---

## 4h. The k-sweep answered: it was never "selection hurts"

Both k sweeps finished (k = 0.25 in 1,633 s, k = 0.75 in 2,574 s;
228 runs each, zero failures, 12 colic skips each). With k = 0.50
already recorded, the three together settle the question section 4c
could not.

Median accuracy change against **no selection**, over the 11 datasets
complete at every k:

| model | technique | k=0.25 | k=0.50 | k=0.75 |
|---|---|---|---|---|
| gradient_boosting | chi2 | -0.0188 | +0.0035 | +0.0035 |
| gradient_boosting | mutual_info | -0.0194 | -0.0002 | +0.0011 |
| gradient_boosting | rfe | -0.0208 | -0.0028 | +0.0017 |
| logreg | chi2 | -0.0133 | -0.0035 | +0.0000 |
| logreg | mutual_info | -0.0163 | -0.0124 | +0.0013 |
| logreg | rfe | -0.0280 | -0.0052 | -0.0000 |
| random_forest | chi2 | -0.0312 | -0.0088 | +0.0000 |
| random_forest | mutual_info | -0.0295 | -0.0095 | -0.0037 |
| random_forest | rfe | -0.0240 | -0.0105 | -0.0031 |
| svm | chi2 | +0.0000 | +0.0000 | +0.0000 |
| svm | mutual_info | -0.0035 | +0.0000 | +0.0013 |
| svm | rfe | -0.0018 | +0.0000 | +0.0000 |

**Nine of twelve model-technique pairs recover monotonically as k
grows.** Not one gets worse. The verdict:

> The v2 selection result was **"keeping half the features hurts"**,
> not **"selection hurts"**. Accuracy tracks how much information is
> discarded, not whether a selection step is present. At k = 0.75 the
> penalty is essentially gone, and three cells are mildly positive.

This is the caveat from section 4c discharged. The earlier statement -
that the result could not distinguish the two explanations - was
correct at the time and is now resolved by evidence rather than
argument.

### The SVM exception is real, not an artefact

Two SVM cells read "flat across k", which would be the opposite
conclusion. The obvious suspicion was the degeneracy seen in the
encoding arm, where the unscaled SVM collapses to majority-class
prediction and therefore cannot respond to anything.

Checked rather than assumed: comparing SVM accuracy against each
dataset's majority-class rate, **only 1 of 11 cells is degenerate**
(wine, 0.6797 against a 0.6761 majority). The other ten are genuinely
discriminating, with macro-F1 from 0.70 to 0.99.

So the SVM's insensitivity to feature selection is a real property of
the model on this data, not a measurement failure. It is also
consistent: an RBF kernel aggregates over all features, so dropping the
weakest ones changes the distance geometry less than it changes a
tree's split choices.

### What this changes for the write-up

The selection arm now supports a sharper and more useful claim than it
did:

- Blind filtering at a fixed fraction is a **net cost, and the cost is
  proportional to how much is thrown away**, not a penalty for
  selecting as such.
- `lasso`, which chooses its own count from the data, sat at or near
  zero throughout the v2 arm. Together with the k gradient, that points
  to the same conclusion from two directions: the number of features
  kept is what matters, and a method that picks it adaptively avoids
  the cost that a fixed fraction imposes.
- The practical advice is therefore not "do not select" but "do not
  select blindly at an arbitrary k".

### A cost estimate that was wrong, corrected by measurement

The large-dataset sweep excluded SVM on the grounds that it is roughly
O(n^2) while "the other three models are linear or near-linear in rows,
so this sweep is hours rather than days". The first measurements say
the second half of that was optimistic:

| model | mean wall time per run, house_16H (22,784 rows) |
|---|---|
| logreg | 0.4 s |
| gradient_boosting | 178.1 s |
| **random_forest** | **509.8 s** |

Random forest is **1,275 times** slower than logistic regression here,
not "near-linear". Projected over the three datasets, with adult and
bank-marketing roughly double house_16H's rows, the 36-run sweep is
about **3.8 hours** rather than the hour implied earlier.

The sweep is still worth running: it is the only evidence that can
address SQ3, and 3.8 hours unattended is acceptable where days would
not have been. But the estimate was wrong, and the reason is worth
keeping: tree ensembles build many deep trees on large data, so their
cost grows faster than the row count suggests. Future cost estimates
should measure a tree model directly rather than reason from the
linear one.

---

## 4i. Scaling on the three large datasets (SQ3)

`ofat_scaling_large` finished on 2026-10-13: **36 of 36 runs, 0 failed,
0 skipped, 4,093 s (68 minutes)**. The 3.8-hour projection in 4h was
too high; adult and bank-marketing did not cost double house_16H.
SVM was excluded, as stated in 4g.

| dataset | rows used | model | none | standard | minmax | robust |
|---|---|---|---|---|---|---|
| adult | 45,222 | logreg | 0.8386 | **0.8487** | 0.8475 | 0.8480 |
| adult | 45,222 | random_forest | 0.8496 | 0.8499 | 0.8496 | 0.8494 |
| adult | 45,222 | gradient_boosting | 0.8633 | 0.8633 | 0.8633 | 0.8633 |
| bank-marketing | 45,211 | logreg | 0.9004 | 0.9015 | 0.9014 | 0.9016 |
| bank-marketing | 45,211 | random_forest | 0.9047 | 0.9047 | 0.9049 | 0.9047 |
| bank-marketing | 45,211 | gradient_boosting | 0.9071 | 0.9071 | 0.9071 | 0.9071 |
| house_16H (RMSE) | 22,784 | logreg | 49,283.9 | **45,502.3** | 45,502.3 | 45,502.3 |
| house_16H (RMSE) | 22,784 | random_forest | 31,513.2 | 31,515.0 | 31,512.5 | 31,516.1 |
| house_16H (RMSE) | 22,784 | gradient_boosting | 34,144.7 | 34,159.7 | 34,159.8 | 34,159.6 |

What this says about SQ3, stated at the strength the evidence allows:

- **The model split holds at 45,000 rows.** Gradient boosting is
  identical to four decimals under every scaler on both classification
  datasets; random forest moves by at most 0.0003. Tree ensembles stay
  scale-invariant at this size.
- **The logistic regression effect does not vanish with sample size.**
  Standardisation is worth +0.0101 accuracy on adult and +0.0011 on
  bank-marketing, against a median of +0.0061 on the 11 small
  datasets. The fold standard deviations are 0.0074 and 0.0023, so the
  adult gain is larger than one fold sd and the bank-marketing gain is
  not.
- **This is descriptive only.** Two large classification datasets and
  one large regression dataset cannot support a significance test, and
  the SVM, the model with the largest scaling effect, has no
  large-dataset evidence at all. SQ3 is addressed for three models on
  three datasets, not answered.

### Correction: linear regression is not always scale-invariant in practice

Sections 3 and 4 say the `logreg` key on a regression target resolves
to LinearRegression, "which is invariant to affine rescaling, so its
scaling contrast cannot be anything but null". The recorded data
contradicts the second half of that sentence.

LinearRegression RMSE across the four scalers, all eight regression
datasets:

| dataset | none | standard | spread |
|---|---|---|---|
| abalone, concrete, cpu_small, diabetes, energy-efficiency, kin8nm | identical | identical | 0.000000 |
| autoMpg | 2.9690 | 2.9656 | 0.0034 |
| **house_16H** | **49,283.9** | **45,502.3** | **3,781.6** |

Six datasets are exactly invariant, as the mathematics says. house_16H
is not: scaling lowers RMSE by 7.7%, and the same numbers appear in
two independently launched sweeps (`ofat_scaling_regression` and
`ofat_scaling_large`), so it is reproducible rather than noise.

The probable cause is numerical conditioning. house_16H has the widest
feature spread in the registry (largest feature standard deviation
12.9 million times the smallest), and an unscaled least-squares solve
on such a matrix loses precision. That explanation has **not been
verified directly**; it is the obvious candidate and nothing more.

What changes: the invariance claim is true of the estimator in exact
arithmetic and false of it in floating point on badly conditioned
data. The substitution note stored on those rows ("invariant to affine
feature scaling") overstates the case for house_16H. The note text in
`models.py` should be softened when the queue is idle; the rows
already recorded keep the old wording.

---

## 4j. Tuning, the fifth factor

`ofat_tuning_v2` finished on 2026-10-13: **256 runs in 20,975 s
(5.8 hours)**. 228 succeeded, 16 skipped (colic), 12 failed. 16
datasets under 2,000 rows, four models, nested CV with inner k = 3.
All four levels ran, including Bayesian, so the optuna-integration fix
from 4b held across a real sweep.

### Results, classification (11 complete datasets)

| model | metric | Friedman p | outcome |
|---|---|---|---|
| **svm** | **macro-F1** | **0.0145** | **bayesian vs none: p = 0.0127, Holm 0.0381, rejected.** Median +0.0068, 95% CI [+0.0017, +0.0539], better on 10 of 11 |
| svm | accuracy | 0.0262 | all three contrasts p = 0.0254, Holm 0.0762, not rejected; better on 8 of 11 |
| random_forest | accuracy | 0.0293 | nothing survives Holm; median **-0.0029**, worse on 7 of 11 |
| random_forest | macro-F1 | 0.0293 | same pattern |
| logreg | accuracy, macro-F1 | 0.7793 | no difference |
| gradient_boosting | accuracy, macro-F1 | 0.7679 | no difference |

This is the **second rejected contrast in the whole programme**, after
logistic regression scaling. Two cautions on reading it:

- It holds for macro-F1 and not for accuracy, where the same model
  reaches Holm 0.0762. One metric of two is a narrow result.
- The scaling baseline in this arm is `none`, and section 4c showed the
  unscaled SVM is the weakest configuration in the study. Tuning C and
  gamma may partly be compensating for the missing scaling, which OFAT
  cannot separate. This is the interaction limit of the design, stated
  in section 2, showing up in a result.

Random forest is the opposite case: tuning made it slightly **worse**
on 7 of 11 datasets. The defaults were already at least as good as
anything in a six-candidate grid.

Regression has only four datasets in this sweep, so the power warning
fires (floor 0.125 against a bar of 0.0167). Gradient boosting improved
RMSE on 4 of 4; that is a description, not a test.

### A design flaw this exposed: "random" and "grid" are the same search

Every random-search score equals the corresponding grid-search score,
on all 56 model-dataset pairs:

| model | grid candidates | random n_iter | identical scores |
|---|---|---|---|
| logreg | 4 | 10 | 11 of 11 |
| svm | 6 | 10 | 15 of 15 |
| random_forest | 6 | 10 | 15 of 15 |
| gradient_boosting | 6 | 10 | 15 of 15 |

Every grid has fewer candidates than `DEFAULT_N_ITER = 10`, so
RandomizedSearchCV exhausts the grid and becomes grid search. sklearn
said so in a warning that had been scrolling past since the first unit
test. The tuning factor therefore has **three distinct levels, not
four**: none, exhaustive search, Bayesian. The `random` rows are valid
measurements but carry no independent information, and the Holm
correction is charging for three contrasts where only two differ.

Fixing it means either larger grids or continuous distributions for
the random level. That changes what the level means, so it is recorded
here as a limitation rather than patched after the results were in.

### What tuning cost

| model | untuned, s per run | tuned, s per run | multiple |
|---|---|---|---|
| gradient_boosting | 6.1 | 262 to 339 | 43x to 56x |
| random_forest | 3.0 | 92 to 138 | 31x to 46x |
| svm | 0.3 | 6.7 to 17.5 | 22x to 58x |
| logreg | 1.2 | 17 to 58 | 14x to 48x |

Set against the effects: gradient boosting paid about 50 times the
compute for no measurable gain, random forest paid about 40 times for
a slight loss, and the SVM paid the least in absolute terms for the
only real improvement. That is proposition P2 from the poster (the
component with the largest cost is not the one with the largest
effect) with numbers behind it.

### The 12 failures, and the fix

All 12 are one bug: on a regression dataset the `logreg` key is
LinearRegression, and the `logreg` grid searches over `C`, which
LinearRegression does not have. Three tuned levels on each of four
regression datasets failed with "Invalid parameter 'C'".

Fixed after the sweep (engine commit `64351ad`): `evaluate` now checks
the grid against the estimator's real parameters and raises a
ProtocolError, so the run is recorded as **skipped with the reason**.
Ridge was not substituted, because that would compare a tuned model
against a different untuned one. Three tests cover it, including that
the untuned baseline still runs and that SVR, which does have a valid
grid, is still tuned. The 12 failed rows stay in the record as history.

The substitution note for LinearRegression was softened in the same
commit, as promised in 4i.

---

## 4k. Imputation with injected missingness

Six sweeps were queued on 2026-10-13 after the tuning arm: MCAR then MAR
at 5%, 15% and 30%, 240 runs each (4 imputation levels x 15 complete
datasets x 4 models, k = 10). The injector is the bit-identical port of
B2's described in section 4g's follow-up commits. This section is
extended as each sweep lands.

### 5% MCAR: complete

240 runs in 1,752 s (29 minutes): 236 succeeded, 4 failed, 0 skipped.

With every dataset now carrying gaps, the arm is testable for the first
time. Classification has 8 complete datasets (sonar dropped, see
below), regression has 6.

| model | metric | Friedman p | outcome |
|---|---|---|---|
| **gradient_boosting** | accuracy | **0.0048** | **all three imputers beat drop_rows**: knn Holm 0.0234 (8 of 8), mean 0.0313 (7 of 8), median 0.0313 (7 of 8); medians +0.042 to +0.051 |
| **gradient_boosting** | macro-F1 | **0.0026** | all three rejected at Holm 0.0234; medians +0.053 to +0.061 |
| random_forest | accuracy | 0.0630 | not licensed |
| svm | accuracy | 0.0789 | not licensed |
| logreg | accuracy | 0.2547 | not licensed |
| all four models | RMSE (6 datasets) | 0.10 to 0.13 | not licensed |

Six contrasts rejected in one sweep, against two in the whole programme
before it. Two things limit what they mean:

- **They say "imputing beats deleting", not "which imputer is best".**
  Every test is against the Chapter 1 baseline, `drop_rows`. The
  question B2 answered (kNN against mean and median) needs a comparison
  among the imputers themselves, which the baseline-referenced design
  does not make. That secondary analysis is worth running once all six
  sweeps are in.
- **`drop_rows` is scored on different rows.** At 5% missing it keeps
  76 of 1,797 rows on digits and 118 of 569 on breast_cancer, because a
  wide dataset almost never has a complete row. Its score is a
  cross-validation over that remnant, while the imputers are scored on
  the full data. The contrast is real as a comparison of two workflows
  and is not a like-for-like comparison of test sets.

### The 4 failures, and the fix

All four are sonar under `drop_rows`: 60 columns at 5% missing leaves
so few complete rows that one class has fewer than 10 members.
The existing check only compared the total row count with k, so
sklearn raised a bare ValueError inside the stratified splitter and the
run was recorded as failed rather than skipped.

Fixed in engine commit `7a3b73a`: `evaluate` now also checks the
smallest class against k for classification and raises a ProtocolError,
so the run is skipped with the reason. Two tests cover it. The fix was
committed while the 15% MCAR sweep was running; that sweep had already
loaded the old code, so any such case in it is still recorded as
failed, and the four sweeps after it use the fix. Failed and skipped
rows are both excluded from analysis, so no reported number depends on
which label a row carries.

### 15% MCAR: complete, and the baseline stops working

240 runs in 1,739 s (29 minutes): 216 succeeded, 20 skipped, 4 failed.

At 15% missing, `drop_rows` leaves too little data on **6 of the 9
classification datasets** (breast_cancer, digits, ionosphere, sonar,
wdbc skipped; wine failed on the small-class case under the old code).
The baseline-referenced analysis therefore collapses to 3
classification datasets and can test nothing.

On regression, where `drop_rows` does run, every imputer scored
**worse** than it on 6 of 6 datasets for three of the four models.
That is not evidence that imputing harms prediction. `drop_rows` trains
and tests on complete rows only, so its test folds contain no gaps at
all, while the imputers are tested on rows whose gaps were filled.
The two scores measure different tasks. This is the like-for-like
problem flagged at 5%, now large enough to reverse the sign.

**Conclusion: under injected missingness `drop_rows` cannot serve as the
reference level.** It is skipped where missingness is high and scored
on different rows where it is not.

### The comparison that is like for like: imputers against each other

`analyse.py` gained `--baseline` and `--exclude`, and the injected
sweeps are now read with `--baseline mean --exclude drop_rows`: kNN and
median against mean, all scored on the same full rows, over all 9
classification datasets and all 6 regression datasets. This is also the
contrast B2 reports, so it is the one that lines up with that study.

This choice of reference was made after the baseline-referenced
analysis of the 5% sweep, and was stated in this log then, before any
imputer-against-imputer number had been computed. It is still a
departure from the Chapter 1 baseline and should be reported as one.

| sweep | model | metric | Friedman p | outcome |
|---|---|---|---|---|
| 5% MCAR | **svm** | accuracy | 0.0297 | **knn beats mean**: Holm 0.0469, better on 7 of 9, median +0.0106 |
| 5% MCAR | **svm** | macro-F1 | 0.0302 | **knn beats mean**: Holm 0.0469, better on 7 of 9, median +0.0119 |
| 15% MCAR | **logreg** | accuracy | 0.0319 | **knn beats mean**: Holm 0.0391, 8 of 9, median +0.0131. **median beats mean**: Holm 0.0391, 7 of 9, median +0.0084, CI [-0.0001, +0.0114] |
| 15% MCAR | logreg | macro-F1 | 0.0319 | not rejected (Holm 0.0547 for both) |
| both | random_forest, gradient_boosting | both | 0.24 to 0.64 | no difference |
| both | all four models | RMSE, 6 datasets | mostly > 0.1 | underpowered: 6 datasets cannot clear the Holm bar for two contrasts (floor 0.03125, bar 0.025) |

Read at the strength the numbers allow:

- kNN imputation beats mean imputation for the two scale-sensitive
  models, SVM at 5% and logistic regression at 15%, by about one
  accuracy point. The tree ensembles do not care which imputer is used.
- The effects are small and each appears at one rate for one model, so
  this is a pattern across two sweeps, not yet a stable result. The
  30% MCAR and three MAR sweeps will show whether it holds.
- The median-beats-mean contrast at 15% has a confidence interval that
  touches zero and should be treated as marginal.
- Regression cannot be tested at n = 6. For LinearRegression at 15%,
  kNN lowered RMSE on 5 of 6 datasets; that is a description.

### 30% MCAR: complete

240 runs in 1,620 s (27 minutes): 216 succeeded, 24 skipped, 0 failed.
All 24 skips are `drop_rows` on the six wide classification datasets
(wine, breast_cancer, digits, wdbc, ionosphere, sonar), now recorded as
skipped with the reason because this sweep ran on the fixed code.

Imputers against mean, 9 classification and 6 regression datasets:

| model | metric | Friedman p | outcome |
|---|---|---|---|
| **svm** | accuracy | 0.0200 | **knn beats mean**: Holm 0.0313, better on 7 of 9, median +0.0295 |
| **svm** | macro-F1 | 0.0017 | **knn beats mean**: Holm 0.0156, better on 8 of 9, worse on 0, median +0.0295 |
| logreg | accuracy | 0.0970 | not licensed |
| random_forest, gradient_boosting | both | 0.46 to 1.00 | no difference |
| all four models | RMSE | 0.11 to 0.51 | no difference, and underpowered at n = 6 |

### MCAR across the three rates

| rate | svm: knn vs mean | logreg: knn vs mean | tree ensembles |
|---|---|---|---|
| 5% | rejected, +0.0106 accuracy | not licensed (p = 0.2466) | no difference |
| 15% | not licensed (p = 0.1070) | rejected, +0.0131 accuracy | no difference |
| 30% | rejected, +0.0295 accuracy | not licensed (p = 0.0970) | no difference |

- The SVM result now appears at two of three rates and is largest at
  30%, where it also holds on both metrics. That is firmer than it was
  after two sweeps, though the 15% gap shows it is not uniform.
- The tree ensembles are indifferent to the imputer at every rate, on
  both metrics. That is three sweeps agreeing.
- Median against mean is not rejected at 5% or 30%; the marginal 15%
  result for logistic regression stands alone.
- **This neither confirms nor contradicts B2 on regression.** B2 found
  kNN best for regression at 5% and 15% and the advantage gone by 30%.
  The lab regression arm has 6 datasets and cannot reject anything with
  two contrasts, so it has nothing to say on that claim. The lab
  classification result (kNN advantage largest at 30% for the SVM) is a
  different task type and should not be read against B2's regression
  finding.

### 5% MAR: complete, and a clean null

240 runs in 2,489 s (41 minutes): 236 succeeded, 4 skipped (digits
under `drop_rows`), 0 failed.

Imputers against mean, 9 classification and 6 regression datasets:
**no Friedman test is significant for any model on any metric**
(classification p from 0.1220 to 0.7165, regression p from 0.1146 to
1.0000). The SVM, which separated kNN from mean at 5% MCAR, sits at
p = 0.1220 here.

At the same 5% rate, then, the kNN advantage for the SVM is present
under MCAR and absent under MAR. One pair of sweeps is too little to
call that a mechanism effect: the two differ by which cells were
blanked, and a 1-point effect on 9 datasets can come and go with that
alone. The 15% and 30% MAR sweeps will show whether MAR is
systematically flatter.

### 15% MAR: complete

240 runs in 1,604 s (27 minutes): 224 succeeded, 16 skipped (`drop_rows`
on digits, ionosphere, sonar and wine), 0 failed.

Imputers against mean, 9 classification and 6 regression datasets:

| model | metric | Friedman p | outcome |
|---|---|---|---|
| **logreg** | accuracy | 0.0353 | **knn beats mean**: Holm 0.0156, better on 8 of 9, median +0.0059, CI [+0.0040, +0.0288] |
| **logreg** | macro-F1 | 0.0095 | **knn beats mean**: Holm 0.0156, better on 8 of 9, median +0.0061 |
| **svm** | macro-F1 | 0.0302 | **knn beats mean**: Holm 0.0313, better on 7 of 9, median +0.0121 |
| svm | accuracy | 0.0275 | not rejected: knn Holm 0.0625, better on 6 of 9, worse on 0, tied 3 |
| random_forest, gradient_boosting | both | 0.64 to 0.89 | no difference |
| all four models | RMSE | 0.07 to 1.00 | no difference; underpowered at n = 6 |

Median against mean is nowhere near rejection (Holm 0.46 to 0.64) and
is worse than mean on most datasets, so the marginal median result at
15% MCAR does not repeat under MAR.

The 5% MAR sweep was a clean null, and the tentative reading then was
that MAR might be flatter than MCAR. This sweep does not support that:
at 15% MAR the kNN advantage is present for both scale-sensitive
models, and for logistic regression it holds on both metrics with a
confidence interval clear of zero. The caution written at 5% MAR, that
one pair of sweeps could not establish a mechanism effect, was the
right call.

### 30% MAR: complete, and the first tree-model response

240 runs in 2,270 s (38 minutes): 212 succeeded, 28 skipped
(`drop_rows` on seven datasets, now including iris), 0 failed.

| model | metric | Friedman p | outcome |
|---|---|---|---|
| **random_forest** | accuracy | 0.0063 | **knn beats mean**: Holm 0.0156, better on 8 of 9, worse on 0, median +0.0085. **median beats mean**: Holm 0.0391, 6 of 9, median +0.0029, CI [-0.0001, +0.0040] |
| **random_forest** | macro-F1 | 0.0419 | **knn beats mean**: Holm 0.0156, 8 of 9. median not rejected (0.0781) |
| **svm** | accuracy | 0.0302 | **knn beats mean**: Holm 0.0469, better on 7 of 9, median +0.0200 |
| svm | macro-F1 | 0.0930 | not licensed |
| logreg | both | 0.0743 | not licensed |
| gradient_boosting | both | 0.82 to 0.89 | no difference |
| all four models | RMSE | 0.04 to 0.61 | underpowered at n = 6 |

Earlier entries in this section say the tree ensembles are indifferent
to the imputer, "now across five sweeps". The sixth sweep breaks that
for random forest: at 30% MAR, kNN beats mean on 8 of 9 datasets. The
statement stands for gradient boosting, which shows no difference in
any of the six sweeps, and has to be narrowed for random forest to
"indifferent in five sweeps of six".

### All six injected sweeps together

1,440 runs in 11,474 s (3.2 hours): **1,340 succeeded, 92 skipped,
8 failed**. Every skip and failure is `drop_rows` leaving too little
data, which does not affect the imputer-against-imputer comparison.

kNN against mean, accuracy, 9 classification datasets per sweep:

| sweep | logreg | svm | random_forest | gradient_boosting |
|---|---|---|---|---|
| MCAR 5% | - | **+0.0106** | - | - |
| MCAR 15% | **+0.0131** | - | - | - |
| MCAR 30% | - | **+0.0295** | - | - |
| MAR 5% | - | - | - | - |
| MAR 15% | **+0.0059** | - (Holm 0.0625) | - | - |
| MAR 30% | - | **+0.0200** | **+0.0085** | - |

A bold figure is the median accuracy gain where the contrast was
rejected after Holm; a dash means not rejected or not licensed.

What the six sweeps support:

- **kNN imputation beats mean imputation in 6 of 24 model-sweep cells
  on accuracy, and is never significantly worse.** Every rejected
  contrast points the same way.
- **The benefit sits with the scale-sensitive models.** The SVM
  responds in 3 sweeps and logistic regression in 2; gradient boosting
  never does; random forest does once, at the highest rate.
- **The gains are about half a point to three points of accuracy**, and
  the largest are at 30% missing.
- **No dependence on mechanism is established.** MCAR gives 3 rejected
  cells and MAR gives 3. The MAR 5% null is the one sweep with nothing.
- **Median against mean is not established.** It is rejected twice in
  24 cells, both times with a confidence interval that touches zero.
- **Regression was never testable.** Six regression datasets cannot
  clear the Holm bar for two contrasts (floor 0.03125, bar 0.025). A
  seventh complete regression dataset would fix that. Descriptively,
  for LinearRegression kNN lowered RMSE on 5 of 6 datasets at 15% MCAR
  and 4 of 6 at 30% MAR, while median was worse than mean on 6 of 6 in
  both.

Two cautions on the whole set:

- **No correction is applied across sweeps.** Each sweep is its own
  family for Holm. Across the six there are 48 classification Friedman
  tests at alpha 0.05, so two or three significant results would be
  expected by chance alone; 13 were observed. The pattern is well
  beyond chance, but any single cell should not be leaned on.
- **The reference level is mean, not the Chapter 1 baseline.** The
  reason is in the 15% MCAR entry above; it is a reported departure.

Against B1 and B2: B1 found a stable null for imputation at 15% MCAR;
B2 found kNN best for regression at low missingness under both
mechanisms. The lab finds a small kNN advantage for classification
with scale-sensitive models and cannot test regression. These are
compatible rather than confirming: the lab result is on a different
task type from B2's and uses a different set of models and datasets
from B1's. Reconciling the three is a job for the comparison chapter,
not for this log.

---

## 4l. Where the programme stands, 2026-10-13

Sections 1 and 8 were written on 2026-10-12 and are kept as they were.
This is the current state.

**The record: 3,621 runs** in `pipeline-lab-engine/outputs/lab.db`, 89
columns (the original 86 plus `k_fraction`, `injected_rate` and
`injected_mechanism`). Engine tests: 314 passing with the
timing-sensitive provenance file excluded.

All five factors now have recorded sweeps:

| factor | what ran | headline |
|---|---|---|
| scaling | 19 datasets x 4 models; 3 large datasets x 3 models | logreg: standard beats none (Holm 0.0410, 10 of 11). Trees invariant, including at 45,000 rows |
| selection | k = 0.25, 0.50, 0.75 | the cost is discarding features, not selecting; penalty gone by k = 0.75 |
| encoding | 19 datasets x 4 models | untestable: 3 informative datasets. Target encoding won 5 of 12 cells |
| tuning | 16 datasets x 4 models | SVM macro-F1: Bayesian beats none (Holm 0.0381, 10 of 11). 30x to 50x the compute elsewhere for nothing |
| imputation | natural, then MCAR and MAR at 5/15/30% | kNN beats mean for scale-sensitive models in 6 of 24 cells; never worse |

**Open, in rough order of value:**

| item | why | cost |
|---|---|---|
| A seventh complete regression dataset | every regression comparison in the imputation arm, and the tuning arm, is stuck one dataset short of testable | one registry entry plus re-running the regression rows |
| The `random` tuning level | identical to `grid` on all 56 pairs because every grid is smaller than n_iter. Needs larger grids or continuous distributions | a design change, then a tuning re-run (hours) |
| SVM on the large datasets | the model with the largest scaling effect has no evidence at 45,000 rows | days on this machine; needs other hardware |
| Skipped rows carry no protocol settings | `cv_k` and `k_fraction` are NULL on skipped rows; cosmetic, no analysis depends on it | small |
| Verify the house_16H conditioning explanation | the 7.7% LinearRegression shift is attributed to conditioning without a direct check | small |
| Dashboard Findings page | still compares against the Chapter 1 baseline only; it does not know about `--baseline mean`, so it will show the injected imputation sweeps against `drop_rows` | moderate |
| Thesis positioning | how these results sit beside the frozen B1 and B2 record | a supervisor conversation |

---

## 4m. Next three steps, planned 2026-10-13

Colile asked for all three of the leading open items from 4l. This is
the plan as written **before** any of it was run, so the reasoning is
on record ahead of the results.

**1. More complete regression datasets.** Every regression comparison
in the injected imputation arm has 6 datasets, one short of the 7 that
two Holm-corrected contrasts need. Eight OpenML candidates were probed
and all are complete, numeric and continuous-target:

| candidate | OpenML id | rows | features |
|---|---|---|---|
| bodyfat | 560 | 252 | 14 |
| yacht_hydrodynamics | 42370 | 308 | 6 |
| QSAR_fish_toxicity | 44970 | 908 | 6 |
| stock | 223 | 950 | 9 |
| airfoil_self_noise | 44957 | 1,503 | 5 |
| wind | 503 | 6,574 | 14 |
| puma8NH | 225 | 8,192 | 8 |
| bank8FM | 572 | 8,192 | 8 |

Three small ones will be added (bodyfat, stock, airfoil_self_noise),
taking the injected imputation arm to 9 regression datasets, clear of
the bar with margin as was done for scaling in 4c, and the tuning arm's
regression side from 4 to 7. They are chosen for being small, so the
tuning re-run stays affordable, and for differing in width (5, 9 and
14 features). The choice is made on size and shape before any of them
has been scored. The six injected sweeps are then run on the three new
datasets only and appended under the existing config names.

**2. Fix the random and Bayesian tuning levels.** Random search is
identical to grid search on all 56 pairs because every grid has fewer
candidates than n_iter. Bayesian search draws 10 trials from the same
4 to 6 candidates, so it is nearly exhaustive as well. The fix gives
random and Bayesian a shared **continuous search space** per model at
the same budget of 10 candidates, and leaves grid as the small discrete
grid. That makes the three tuned levels genuinely different, and makes
random against Bayesian a fair comparison at equal budget. Because this
changes what the levels mean, it runs as a new sweep, `ofat_tuning_v3`,
on the 16 small datasets plus the 3 new ones; `ofat_tuning_v2` stays in
the record as it is. Expected cost: about 7 hours.

**3. Teach the dashboard's Findings page the reference level.** The
page compares every sweep against the Chapter 1 baseline, so it shows
the injected imputation sweeps against `drop_rows`, which section 4k
established is not a like-for-like comparison. It will use mean as the
reference for injected sweeps, say so on the page, and be tested
against the numbers `analyse.py` reports.

Order of work: datasets first, then launch the tuning sweep, then do
the dashboard work while the sweep runs.

---

## 4n. The three steps, carried out 2026-10-13

### Step 1: three regression datasets, and regression becomes testable

bodyfat, stock and airfoil_self_noise were registered (engine commit
`3c20256`) and the six injected sweeps were run on those three only and
appended under the existing config names: 288 runs in about 16 minutes,
284 succeeded, 4 skipped, 0 failed. No succeeded cell is duplicated.
The injected arm now has **9 regression datasets**.

Imputers against mean, RMSE, 9 regression datasets. A positive figure
means a lower error than mean imputation.

| sweep | model | Friedman p | knn vs mean | median vs mean |
|---|---|---|---|---|
| MCAR 5% | logreg (LinearRegression) | 0.0131 | not rejected (7 of 9 better) | **worse**: Holm 0.0078, worse on 9 of 9 |
| MCAR 15% | logreg | 0.0018 | **better**: Holm 0.0078, 8 of 9 | **worse**: Holm 0.0078, 9 of 9 |
| MCAR 15% | random_forest | 0.0498 | not rejected | **worse**: Holm 0.0078, 9 of 9 |
| MCAR 30% | all four models | 0.10 to 0.64 | not licensed | not licensed |
| MAR 5% | logreg | 0.0183 | not rejected (Holm 0.0547) | **worse**: Holm 0.0391, 7 of 9 |
| MAR 5% | svm (SVR) | 0.0319 | **better**: Holm 0.0391, 7 of 9, CI touches zero | not rejected |
| MAR 15% | logreg | 0.0084 | **better**: Holm 0.0156, 8 of 9 | **worse**: Holm 0.0195, 7 of 9 |
| MAR 30% | logreg | 0.0031 | **better**: Holm 0.0273, 7 of 9, CI touches zero | **worse**: Holm 0.0078, 9 of 9 |
| every sweep | gradient_boosting | 0.37 to 0.89 | no difference | no difference |

What the regression side now supports:

- **Median imputation is worse than mean imputation for linear
  regression.** Rejected in 5 of 6 sweeps, and worse on all 9 datasets
  in three of them. This is the most consistent single result in the
  imputation arm. The differences are small in size (median RMSE
  change around 0.03 to 0.06) but almost never in the other direction.
- **kNN beats mean for linear regression at 15% under both mechanisms**
  (8 of 9 datasets each), and marginally at 30% MAR.
- **Gradient boosting is indifferent to the imputer** in all six
  sweeps, on regression as it was on classification.
- These are median differences in raw RMSE across datasets whose
  targets are on very different scales, so the size of the "typical
  change" is not comparable between datasets. The sign and the win
  count are the reliable parts.

Against B2 (kNN best for regression at 5% and 15% under MCAR and MAR,
gone by 30%): the lab agrees at 15% under both mechanisms and at 30%
MCAR, where nothing is rejected. It does not reproduce the 5% result
(kNN is ahead on 7 of 9 datasets at both 5% sweeps but is not
rejected), and it finds a marginal kNN advantage at 30% MAR that B2
did not. That is partial agreement from a different set of datasets
and models, and should be described that way.

The classification tables in 4k are unchanged: the three new datasets
are regression only.

### Step 2: random and Bayesian tuning given a real search space

Engine commit `3c20256`. Random and Bayesian search now share one
continuous space per model (`SPACES` in `components/budgets.py`) at
the same budget of 10 candidates; grid keeps the small discrete grid.

| model | space searched by random and Bayesian |
|---|---|
| logreg | C log-uniform 0.001 to 100 |
| svm | C log-uniform 0.01 to 100; gamma log-uniform 0.0001 to 1 |
| random_forest | n_estimators 100 to 300; max_depth one of none, 5, 10, 20, 30; min_samples_leaf 1 to 5 |
| gradient_boosting | learning_rate log-uniform 0.01 to 0.3; n_estimators 100 to 300; max_depth 2 to 5 |

Tests assert that every space is larger than the random budget, so
random search cannot collapse into grid search again, and that a
random search actually draws ten distinct values that are not the grid.
The applicability check from 4j now uses the parameters the requested
level really searches. 321 engine tests pass.

A smoke test of all four levels on wine and bodyfat gave four
different scores per model, where before random and grid were
identical.

`ofat_tuning_v3` (304 runs: 4 levels x 19 datasets x 4 models) was
launched at 17:01 on 2026-10-13 under a new config name, because the
levels mean something different from v2's and the two must not be
pooled. Its results are recorded in a later section.

### Step 3: the Findings page reads injected sweeps against mean

Dashboard commit `4f4a2ec`. `core/findings.py` decides the reference
level per sweep: an imputation sweep with injected missingness is
compared against mean with `drop_rows` excluded, and every other sweep
keeps its Chapter 1 baseline. Each finding carries a note explaining
the departure, shown on the page above the numbers.

A test pins the page to `analyse.py --baseline mean --exclude
drop_rows` on the 30% MCAR sweep (SVM accuracy: Friedman 7.8235,
p = 0.0200; kNN Holm 0.03125, better on 7 of 9), and the page was
checked in a browser: 12 findings, each with the note, no console
errors. 110 dashboard tests pass.

---

## 4o. Two smaller open items closed, 2026-10-13

Done while `ofat_tuning_v3` was running. Neither touches a recorded
result.

### The house_16H result is explained, and the earlier guess was wrong

Section 4i attributed the 7.7% LinearRegression shift on house_16H to
"numerical conditioning", meaning lost precision, and said plainly that
it had not been verified. It has now been checked directly, and the
cause is more specific than that.

| check on house_16H (22,784 rows, 16 features) | result |
|---|---|
| feature standard deviations | one near 66,000; the other fifteen below 0.34 |
| condition number of the centred raw matrix | 1.4e7 |
| condition number after standardising | 23 |
| rank sklearn reports on the raw data | **9 of 16** |
| rank sklearn reports on the scaled data | 16 of 16 |
| raw data, default `tol = 1e-6` | RMSE 49,412.8 |
| raw data, `tol = 1e-9` | rank 16, RMSE **45,539.1** |
| scaled data | RMSE **45,539.1** |

sklearn's least-squares solver discards any singular value below `tol`
times the largest. With one feature on a scale 200,000 times the
others, 7 of the 16 directions fall under that cutoff and are dropped,
so the unscaled model is fitted on 9 directions instead of 16. Tighten
the tolerance and the raw data gives exactly the scaled score.

So the estimator **is** scale-invariant, and nothing was lost to
rounding. The unscaled model was simply not the full model, because the
solver's default rank cutoff is relative to the largest feature scale.
This is a sharper statement of the practical point: on data with one
dominant-scale feature, not scaling can silently remove features from a
linear model. (These figures use their own fold split, so they differ
slightly from the recorded 49,283.9 and 45,502.3; the gap between raw
and scaled is the same.)

The same mechanism probably explains the much smaller shift on autoMpg
(0.0034 RMSE). That has not been checked.

The comment in `components/models.py` now carries the verified
explanation.

### Skipped and failed rows now carry their settings

`cv_k`, `inner_k`, `holdout_repeats`, `k_fraction`, `injected_rate` and
`injected_mechanism` are known before a run starts, but were written on
the success path only. A skipped row could not say at what missing rate
it had been skipped. They are now set in `_base_row`, which every
outcome shares. A test runs a real sweep that skips and checks the
skipped row carries the settings. 322 engine tests pass.

Rows already recorded keep their NULLs; the record is append-only and
no analysis reads those fields on a skipped row. `ofat_tuning_v3` had
already loaded the old code when this was committed, so its skipped
rows will also be NULL in those columns.

---

## 4p. The corrected tuning sweep: the rejected SVM result does not survive

`ofat_tuning_v3` finished 2026-10-14: **304 runs in 15.2 hours**
(17:01 on the 13th to 08:13 on the 14th). 267 succeeded, 37 skipped, 0
failed. All skips are expected: 16 are colic (row deletion, as in every
other arm), 21 are `logreg` tuning on a regression target, correctly
refused by the fix in 4j since LinearRegression has nothing to search.
No row is duplicated; the database passes integrity_check.

### Classification: the rejected result from v2 is gone

| model | metric | v2 Friedman p | v3 Friedman p |
|---|---|---|---|
| svm | accuracy | 0.0262 | 0.1788 |
| **svm** | **macro-F1** | **0.0145 (rejected)** | **0.2330** |
| random_forest | accuracy | 0.0293 | 0.0931 |
| random_forest | macro-F1 | 0.0293 | 0.0753 |
| logreg, gradient_boosting | both | > 0.25 | > 0.25 |

Nothing is significant in v3 on any model or metric for classification.
The one rejected contrast the programme had from tuning - Bayesian
beating no tuning for the SVM on macro-F1 - **does not survive when
Bayesian is given a real space to search instead of the five or six
points a tiny grid offered**.

Checked directly, dataset by dataset, SVM macro-F1:

| dataset | none (same both sweeps) | v2 bayesian | v3 bayesian |
|---|---|---|---|
| iris | 0.9666 | 0.9593 | 0.9732 |
| wine | 0.6453 | 0.7097 | 0.6877 |
| sonar | 0.8142 | 0.8911 | 0.8668 |
| heart-c | 0.6264 | 0.6804 | 0.6573 |
| credit-approval | 0.5980 | 0.6286 | **0.6676** |
| pima | 0.7044 | 0.7112 | **0.6782** |
| credit-g | 0.4743 | 0.4748 | **0.4118** |
| digits | 0.9889 | 0.9906 | 0.9883 |

The untuned baseline is identical between sweeps, as it must be (same
seed). Bayesian's gain shrinks on most datasets and reverses outright
on two (pima, credit-g): with only 10 trials to cover a continuous
range instead of a handful of grid points, the search sometimes lands
worse than it would have by accident on the old, effectively
exhaustive "search". **The v2 result was real in the narrow sense that
the numbers were not fabricated, but it was measuring how well Bayesian
search happens to rediscover a small fixed grid, not how well it tunes
a model.** That is not a finding about tuning; it is restated from 4j
to make the correction explicit.

### Regression: a new result, on the arm that could not be tested before

4c and 4j could not test regression tuning at n = 4. At n = 7 (3 new
datasets from 4n):

| model | Friedman p | outcome |
|---|---|---|
| **svm (SVR)** | **0.0342** | **grid beats none**: Holm 0.0469, better on 7 of 7, median RMSE improvement +1.18, CI [+0.19, +3.82] |
| random_forest | 0.1344 | not significant |
| gradient_boosting | 0.0503 | not significant, just over the line |
| logreg | - | fewer than two complete datasets (LinearRegression has no grid) |

SVR is the one model where a small, specific grid (C and gamma from
`GRIDS`) reliably beats the default, won on every one of the seven
regression datasets, and random and Bayesian search over the wider
continuous space do not reach significance despite also improving on
most datasets (6 of 7 and 5 of 7 respectively). The grid here is small
enough to be close to exhaustive for a 2-parameter model, which may be
why it outperforms a 10-draw sample from a wider space.

### What this changes

- **Tuning's one surviving positive result in the whole programme is
  now: grid search tunes the SVM regressor.** Classification tuning has
  no rejected result at all, replacing what was previously the
  programme's second-strongest finding.
- **The cost argument from 4j stands and sharpens.** Gradient boosting
  and random forest paid 30 to 50 times the compute in v2 for no
  measurable gain; v3 adds that random and Bayesian search did not
  rescue classification tuning either, at a similar or higher cost than
  grid.
- **This is why the re-run mattered.** Had v2 been reported as final,
  the thesis would have stated that Bayesian tuning helps the SVM. That
  claim does not survive giving Bayesian a real search space. The
  correction in 4j was necessary, not cosmetic.

---

## 4q. SVM on the three large datasets, and what is still missing, 2026-10-14

`ofat_scaling_large_svm` finished overnight: **12 runs in a few hours,
12 succeeded, 0 failed**. Database passes integrity_check, no succeeded
cell duplicated. Committed `ab4faf1`.

Only 2 classification datasets (adult, bank-marketing) and 1 regression
dataset (house_16H) are in this arm, so Friedman has too few datasets to
run (n=2 and n=1): nothing here is a tested finding, only a direct
reading of the numbers.

| dataset | metric | none | standard | minmax | robust |
|---|---|---|---|---|---|
| adult | accuracy | 0.7913 | **0.8535** | 0.8370 | 0.7963 |
| adult | macro-F1 | 0.5793 | **0.7873** | 0.7627 | 0.6380 |
| bank-marketing | accuracy | 0.8831 | **0.9052** | 0.8947 | 0.8828 |
| bank-marketing | macro-F1 | 0.4773 | **0.7085** | 0.6262 | 0.4731 |
| house_16H | RMSE | 55347.9 | **55109.0** | 55301.3 | 55337.0 |

Standard scaling wins on every metric on every dataset here, by a wide
margin on macro-F1 for both classification sets (adult +20.8 points,
bank-marketing +23.1 points) and a small margin on house_16H RMSE. This
is the same direction and a larger size than the smaller-dataset SVM
scaling result in 4c/4i (CD 0.957, +7.3 accuracy points), read without
a significance test because there are not enough datasets at this size
to run one. It is evidence, not a finding, and is reported as such.

### What is still a genuine gap

Checking every config against the record directly (not the stale table
in 4l) found that encoding, selection and tuning have **zero coverage**
on adult, bank-marketing or house_16H. Every v2 config
(`ofat_encoding_v2`, `ofat_selection_v2`) and `ofat_tuning_v3`
deliberately excludes these three datasets for the same cost reason the
scaling arm originally did, before 4i and this section measured the
real cost and ran it anyway.

Two new configs close part of this, written and committed `d1c2b83`:

| config | arm | datasets | models | runs |
|---|---|---|---|---|
| `ofat_encoding_large` | encoding | adult, bank-marketing | all 4 | 24 |
| `ofat_selection_large` | selection | adult, bank-marketing, house_16H | all 4 | 60 |

house_16H is excluded from the encoding config only: it has zero
categorical columns (checked directly), so onehot/ordinal/target have
nothing to encode there. It is included in selection, which has no such
requirement.

Tuning on the three large datasets is not attempted here: tuning's cost
is per-candidate-fit, and on SVM specifically (gamma included in the
search space) this would multiply the already-measured ~280 CPU-second
adult fit by up to 10 candidates per fold. That is left as an open item
rather than run blind.

`ofat_encoding_large` is launched now; `ofat_selection_large` follows
once it completes, without pausing in between, per standing instruction
to keep working unattended.

---

## 4r. Encoding on the two large categorical datasets, 2026-10-14

`ofat_encoding_large` finished: **24 runs, 24 succeeded, 0 failed, 0
skipped**. Integrity_check ok, no succeeded cell duplicated. Committed
`49b1886`; config committed `d1c2b83`.

Only adult and bank-marketing qualify (house_16H has no categorical
columns), so n=2 for every model, below the 6-dataset floor needed for
Friedman to reach p<0.05 at all. As in 4q, this is a direct reading of
the numbers, not a tested finding.

| dataset | model | onehot acc / F1 | ordinal acc / F1 | target acc / F1 |
|---|---|---|---|---|
| adult | logreg | 0.8386 / 0.7656 | **0.8024 / 0.6840** | 0.8428 / 0.7703 |
| adult | random_forest | 0.8496 / 0.7879 | 0.8543 / 0.7933 | 0.8608 / 0.8005 |
| adult | gradient_boosting | 0.8633 / 0.8006 | 0.8625 / 0.7988 | 0.8648 / 0.8048 |
| adult | svm | 0.7913 / 0.5793 | 0.7914 / 0.5797 | 0.7914 / 0.5797 |
| bank-marketing | logreg | 0.9004 / 0.6913 | **0.8893 / 0.6201** | 0.9004 / 0.6881 |
| bank-marketing | random_forest | 0.9047 / 0.7205 | 0.9057 / 0.7312 | 0.9060 / 0.7332 |
| bank-marketing | gradient_boosting | 0.9071 / 0.7302 | 0.9044 / 0.7193 | 0.9060 / 0.7327 |
| bank-marketing | svm | 0.8831 / 0.4773 | 0.8831 / 0.4775 | 0.8832 / 0.4775 |

Two readings, consistent with the smaller-dataset encoding work already
in the record:

- **logreg is the one model ordinal encoding visibly hurts**, on both
  datasets (adult F1 -8.2 points, bank-marketing F1 -7.1 points): a
  linear model is sensitive to the false numeric order ordinal imposes
  on unordered categories, exactly the mechanism the thesis already
  argues for logreg elsewhere.
- **SVM is encoding-invariant at four decimal places on both datasets.**
  This is not new: 4q already showed the unscaled SVM here is dominated
  by the lack of scaling (one feature's variance swamps the rest), so a
  categorical-encoding choice changes almost nothing relative to that.
  Tree models (random_forest, gradient_boosting) show small, inconsistent
  shifts in both directions, as they do in the smaller-dataset arm.

### Selection launched next

`ofat_selection_large` (60 runs: 5 levels x 3 datasets x 4 models)
launched immediately after this commit, per standing instruction not to
pause between sweeps. house_16H is included here, since selection has
no categorical-column requirement.

---

## 4s. chi2 selection crashed on adult; fixed, record restarted clean, 2026-10-14

`ofat_selection_large` was launched after 4r and reached adult within a
minute. All four models failed identically on `selection=chi2`:
`ValueError: setting an array element with a sequence.`

### Cause

`_chi2_or_f_classif` (the wrapper that falls back to f_classif when chi2's
non-negativity requirement is not met, added 2026-10-12 for ionosphere)
casts its input with `np.asarray(X, dtype=float)` to check for negative
values. adult and bank-marketing are the first datasets in the programme
with enough categorical cardinality that sklearn's `ColumnTransformer`
keeps the onehot-encoded block **sparse** (a `csr_matrix`) rather than
densifying it. `np.asarray` cannot cast a sparse matrix that way, so the
check itself crashed before chi2 or f_classif ever ran. The same cast,
guarded by a bare except, sits in `substitution_note` too: it did not
crash, but it silently returned no substitution note on sparse input,
which would have been a true but unrecorded substitution. The 19 smaller
datasets in `ofat_selection_v2` never exercise this: none of them have
enough categorical levels to push the ColumnTransformer into sparse
output, so the bug was latent until a dataset this wide was run, the
same pattern as every other large-dataset bug in this programme so far.

### Fix

Both call sites now densify explicitly with `X.toarray()` when
`scipy.sparse.issparse(X)`, before the existing dense cast. chi2 and
f_classif both accept sparse input natively; only the negativity CHECK
needed a dense view. A regression test reproduces the exact csr_matrix
failure directly (`test_chi2_accepts_sparse_input`) and checks the
substitution-note path too. 342 engine tests pass. Committed `4201de3`.

### The record was restarted, not resumed

The sweep had written 9 rows (5 succeeded, 4 failed from this bug)
before being stopped. Since `lab.db` had not been committed since 4r,
`git checkout -- outputs/lab.db` discarded those 9 rows entirely rather
than leaving 4 permanently-failed rows under the sweep's config name for
a bug that no longer exists. Confirmed zero `ofat_selection_large` rows
and `pragma integrity_check` ok before relaunching under the same config
name with a fresh batch id. This is the correct use of "append-only":
once committed, a row stays; nothing here was committed.

`ofat_selection_large` is running again from scratch.

---

## 4t. A false stall report: rfe+svm on adult was slow, not hung, 2026-10-14

The relaunched `ofat_selection_large` reached `rfe` + `svm` on adult and
showed zero CPU movement over a sampled 15-second window, a single
thread parked in `Wait`/`UserRequest`, and no log growth for over 20
minutes. That was read as a genuine stall and the process was killed,
losing 13 already-valid rows (`none`, `chi2`, `mutual_info` complete on
adult across all four models, plus `rfe`/logreg) that had to be
rewritten.

### This was the wrong read, caught before acting on it twice

Before relaunching, the specific combination was isolated and measured
directly rather than assumed:

| fit | time |
|---|---|
| SVM alone on adult (no selection) | 210.2 s |
| RFE (decision-tree estimator) + SVM on adult | **532.9 s** |

rfe+svm takes about 2.5x plain SVM, consistent with RFE doing its own
repeated tree fits before the final SVM fit runs. It was never hung; it
was a single very slow fit, and the CPU reading that looked like zero
was a sampling artefact rather than evidence of a deadlock. This project
has already logged one CPU-measurement bug this session (the
`.CPU` TimeSpan-vs-double confusion in 4-something); this is a second,
different mistake in the same area, worth naming so it is not repeated a
third time: **a short CPU sample during a native BLAS/liblinear call is
not reliable evidence of a stall, and killing a process on that basis
alone is premature.** The correct check is a longer sampled window, or
better, comparing against a directly measured isolated timing for the
same combination before concluding anything is wrong.

### What this costs

The sweep was relaunched a second time from scratch (fresh batch id,
`7d79015d749d4d7b91b00445ba536bec`), re-doing the 13 rows that were
already correct. `lab.db` was not committed between attempts, so nothing
false entered the permanent record; the cost was time, not correctness.
Given the measured combination costs above, and that four of the five
selection levels have at least one SVM run on each of the two
classification datasets, this sweep likely needs a few hours to finish,
not the roughly one hour each of the SVM large-dataset sweeps took. That
is a revised estimate, not the original "60 runs" sizing, which did not
account for selection methods compounding with SVM's own cost.

---

## 4u. Selection on the three large datasets, 2026-10-14

`ofat_selection_large` finished (after the restart in 4s and the slow,
not hung, runs described in 4t): **60 runs, 60 succeeded, 0 failed**.
Integrity_check ok, no succeeded cell duplicated. Committed `02148e3`;
config committed `d1c2b83`.

n is 2 for classification (adult, bank-marketing) and 1 for regression
(house_16H), both below Friedman's floor, so as in 4q and 4r this is a
direct reading, not a tested finding.

### lasso behaves completely differently on the two classification datasets

| dataset | columns after onehot | lasso keeps | chi2/mutual_info/rfe keep |
|---|---|---|---|
| adult | 104 | **5** | 52 (half, by `k_fraction`) |
| bank-marketing | 51 | 49 (almost all) | 26 (half) |

On adult, L1 logistic regression zeroes all but 5 of 104 one-hot
columns, and every model pays for it: logreg F1 0.7656 to 0.6923 (-7.3
points), random_forest 0.7879 to 0.7319, gradient_boosting 0.8006 to
0.7412, even SVM moves (0.5793 to 0.6380, the only model lasso helps
here, perhaps because dropping correlated one-hot columns reduces
SVM's sensitivity to feature scale imbalance). On bank-marketing, where
lasso keeps 49 of 51 columns, every model is within 0.01 F1 of the
`none` baseline: lasso is close to a no-op there. The other three
selectors (chi2, mutual_info, rfe) all use the same fixed `k_fraction`
and keep roughly half the columns on both datasets, with small,
model-dependent costs (gradient_boosting and random_forest barely move;
logreg loses 1-3 F1 points; SVM is unaffected, same invariance as 4q
and 4r).

The mechanism is adult's categorical cardinality: 8 categorical columns
expand to 104 one-hot columns, several representing rare levels of
`native-country` and `occupation` with few training examples per level.
L1 regularisation has far more near-zero coefficients to prune there
than on bank-marketing's 51 columns, so the SAME technique at the SAME
default strength produces a near-total prune on one dataset and almost
no prune on the other. This is a data-dependent interaction the
smaller-dataset selection arm (4-something, `ofat_selection_v2`) could
not show: none of its 19 datasets has cardinality anywhere near adult's.

### house_16H: lasso and the baseline are identical

On house_16H, `lasso` and `none` give byte-identical RMSE on every
model (e.g. gradient_boosting 34144.73 both). `n_features_selected` is
16 of 16 for both: the L1 penalty does not zero any coefficient on this
dataset's 16 numeric features, so `_MinFeatures`'s fallback never
triggers and the selector is a true no-op here, not a near-no-op as on
bank-marketing. chi2/mutual_info/rfe all cut to 8 of 16 features (the
`k_fraction` default) and cost gradient_boosting and random_forest
2,000-9,000 RMSE (worse), while logreg (LinearRegression) and svm (SVR)
move by comparable or smaller amounts in mixed directions. This matches
the already-recorded selection pattern (4h): the cost here is
discarding features outright, not the selection mechanism itself.

### What this adds to the programme

Selection's cost on large datasets is **not uniform across data at all
sizes**: lasso's behaviour on adult (prune almost everything) versus
bank-marketing (prune almost nothing) is the sharpest data-dependence
any single technique has shown in either selection sweep. The 19
smaller datasets could not expose this because none has adult's
categorical width.

---

## 4v. The repeated-holdout secondary protocol, launched 2026-10-14

With encoding and selection now covered on the three large datasets
(4r, 4u), the scaling arm (4q) already done, and tuning deliberately
left open (4q), the remaining config-based gap was identified by
checking every config file against `lab.db` directly: `holdout_large`
is the only config that has never been run at all. `ofat_encoding`,
`ofat_selection` and `ofat_tuning` (the original, un-versioned configs)
also show zero rows, but each is superseded by a v2/v3/k25/k75 variant
that already has a full record, so running the originals would only
duplicate inferior versions of work already done.

`holdout_large` is methodology section 6.1's answer to a single
train/test split: 30 repeats of a 70/15/15 split, on the four datasets
with at least 4,000 rows (adult, bank-marketing, house_16H, abalone),
varying scaling, on logreg and random_forest only (no SVM, so none of
the large-dataset cost concerns from 4q-4u apply here). 32 top-level
runs, each internally averaging 30 holdout repeats. Config re-validated
(`load_config` parses, 32 runs) and launched under batch
`27e9d912882a4844a44b1020635e9ab2`.

This is the first time this protocol has been exercised on any dataset
in the engine's history; its own test suite covers it with small
synthetic data only. Progress and the first failure or completion will
be checked directly against the log and database, not assumed.

---

## 4w. Repeated holdout agrees with k-fold: the secondary protocol closed, 2026-10-14

`holdout_large` finished: **32 runs, 32 succeeded, 0 failed**, each
averaging 30 repeats of a 70/15/15 split. Integrity_check ok, no
succeeded cell duplicated. Committed `f9fb599`; config committed
`4a86...` (pre-existing, never run before this sweep).

This is the first time `repeated_holdout` has run on real data anywhere
in this engine's history. It did not need a single workaround: no
failures, no skips, across four datasets and two models.

### Agreement with the k-fold record, read directly (n too small to test)

| dataset | model | k-fold result (earlier sections) | holdout result here |
|---|---|---|---|
| house_16H | logreg | raw 49,283.9 vs scaled 45,502.3 (4i, 4o: solver rank cutoff, verified mechanism) | raw 49,445.8 vs scaled (minmax/standard/robust, all identical) 45,829.3 -- **same ~7.3% gap, same direction, same identical-across-non-none-levels signature** |
| house_16H | random_forest | near scale-invariant in every scaling sweep | 32,295.7 to 32,298.4 across all four levels -- **near-invariant here too** |
| adult | logreg | standard beats none in `ofat_scaling_large_svm`-era readings (4q, SVM only, no logreg comparison there) | F1 0.7683 (none) to 0.7836 (standard), **standard and robust both ahead of none and minmax, same direction as every other classification dataset in the programme** |
| adult | random_forest | near scale-invariant throughout | 0.7884 to 0.7889 across all four levels, **effectively flat** |
| bank-marketing | logreg | standard/robust ahead of none in every classification sweep so far | F1 0.6931 (none) to 0.6997 (robust/standard), **same small, consistent direction** |
| bank-marketing | random_forest | near scale-invariant | 0.7291 to 0.7297, **flat** |

Every one of these agrees in direction and rough size with the k-fold
record collected under a completely different evaluation protocol. The
house_16H logreg result is the sharpest: minmax, standard and robust
give byte-identical RMSE here, exactly the signature that 4o traced to
sklearn's solver dropping the same singular values regardless of which
non-"none" scaler is used, as long as it brings the dominant feature's
scale down far enough. Seeing that exact signature reappear under 30
independent 70/15/15 splits, rather than 10-fold CV, is strong evidence
the mechanism is a property of the data and the solver, not an artefact
of any one evaluation protocol.

### What this closes

Methodology section 6.1's objection to a single train/test split is
answered for the four largest datasets in the registry: the scaling
effect that matters most in this programme (house_16H's rank-deficiency
gap, and the smaller but consistent logreg-scaling gain on adult and
bank-marketing) is not an artefact of the k-fold split; it reproduces
under repeated holdout with a completely different split structure. No
formal test licenses this as a significant result (n is 2 or 1 per
model here, same limit as 4q, 4r, 4u), but it is independent corroborating
evidence for findings the programme already carries, collected under
the protocol the methodology names as the alternative check.

With this sweep done, every config file in `configs/` has either a
complete run record or is a superseded original with a v2/v3/k25/k75
replacement already recorded. No further config-based gap remains
open.

---

## 4x. The imputer-vs-imputer secondary analysis, closed: a clean null

Section 4k (natural, Chapter-1-baseline missingness) flagged that its
six rejected contrasts said only "imputing beats deleting", not "which
imputer is best", and that the imputer-vs-imputer comparison was
"worth running once all six sweeps are in". `analyse.py --config
ofat_imputation_v2 --baseline mean --exclude drop_rows --complete-only`
answers it directly: this compares knn and median against mean,
excluding drop_rows so the comparison is like-for-like on the same
rows, which the original Chapter-1-baseline reading (against drop_rows)
could not offer.

All 19 datasets qualify (unlike the drop_rows-referenced reading, which
drops whichever datasets make `drop_rows` fail or score on too few
rows): 12 classification, 7 regression, nothing excluded.

| task | model | Friedman p |
|---|---|---|
| classification | gradient_boosting | 0.0970 |
| classification | logreg | 0.1482 |
| classification | random_forest | 0.6703 |
| classification | svm | 0.6065 to 0.8669 (accuracy/F1) |
| regression | all four models | 0.3679 |

**Nothing is significant.** Not one model, not one metric, not one
task type shows a global difference among mean, median and kNN
imputation under natural (Chapter-1-baseline) missingness. This is a
clean null, not a near-miss: every p-value is comfortably above 0.05,
several above 0.6.

Checked directly why: natural missingness in this registry is
overwhelmingly ABSENT, not merely light. 15 of the 19 datasets in this
sweep have **0.00%** missing values -- mean, median and kNN imputation
have nothing to act on and are necessarily identical there. Only colic
(20.1%) has a rate comparable to what the injected sweeps control for;
credit-approval, heart-c and autoMpg have small genuine rates (0.2-0.7%).
With at most one or two datasets per sweep actually exercising the
imputer, a global test across all 19 has no power to detect an
imputer-choice effect even if one exists on colic alone.

This sharpens what the programme can claim about imputation:

- **Whether to impute at all (versus dropping rows) is the real
  finding** (4k: six rejected contrasts, drop_rows loses almost every
  time, because dropping ANY row with a gap is costly even at a true
  rate near zero if the registry has many columns). **Which imputer to
  use, among mean/median/kNN, could not be tested here** -- not because
  the effect is absent, but because this registry's natural missingness
  gives the comparison almost no datasets to work with.
- Under INJECTED missingness (4k, 4n), which controls the rate
  directly, kNN beats mean significantly at several rates and
  mechanisms, and median is significantly worse than mean for
  regression at several rates. That is where imputer choice has been
  shown to matter in this programme.
- **The honest statement is: this sweep cannot tell "imputer choice does
  not matter" from "imputer choice was never really tested", and
  reports the second, not the first.** The null above is a null about
  the registry's missingness, not a settled null about mean vs median vs
  kNN.

This closes the item flagged in 4k as "worth running once all six
sweeps are in", with the honest limitation stated rather than reported
as a stronger result than the data supports.

---

## 4y. Tuning on large datasets: measured, and left for a decision

With every config-based gap closed (4w) and the imputer secondary
analysis resolved (4x), the one remaining open item from 4q is tuning
on the three large datasets. Before writing a config blind, the real
cost was measured the same way 4i and 4q measured scaling and SVM
costs: one grid-search fit (one outer fold, inner_k=3) on adult, for
the three non-SVM models, encoding=onehot, scaling=none:

| model | one grid-search fit | projected for 1 outer run (x10 folds) | projected for 2 large classification datasets x 3 tuned levels (grid, random, bayesian) |
|---|---|---|---|
| logreg | 71.6 s | ~12 min | **~1.2 hours** |
| gradient_boosting | 290.9 s | ~49 min | **~4.8 hours** |
| random_forest | **1,378.8 s (23 min)** | **~3.8 hours** | **~23 hours** |

random_forest's grid search alone, on adult and bank-marketing, at grid
level only, already projects to most of a day. Random and Bayesian
search use a continuous space at a 10-candidate budget (4n), which does
not obviously cost less per candidate than grid's small discrete set,
so the true total is at least this, probably more once house_16H and
the other two levels are added.

This is not run blind. It is the same threshold 4q used to leave SVM
tuning on large datasets as an open item rather than launch it
unmeasured: a result this large changes what "launch now" means, and
the decision of whether roughly a day of compute is worth one
tuning-on-large-datasets data point belongs to Colile, not to an
unattended default.

**Left open, with the real number attached**: tuning on adult,
bank-marketing and house_16H, restricted to logreg/random_forest/
gradient_boosting (SVM excluded as in 4q), costs on the order of a day
of machine time, dominated by random_forest's grid search. A narrower
version -- logreg and gradient_boosting only, or grid only, dropping
random_forest or the random/bayesian levels -- would cost roughly 6
hours instead and is the configuration to run if the full version is
too expensive to justify.

---

## 4z. Tuning on large datasets launched in full, 2026-10-15

Colile reviewed the cost measured in 4y and asked for the full design
run regardless of the time it takes: "I want the full runs for
everything... complete que the rest now even if you think it will take
days." `ofat_tuning_large` is launched as designed there, with nothing
narrowed:

| | |
|---|---|
| vary | tuning |
| levels | none, grid, random, bayesian |
| datasets | adult, bank-marketing, house_16H |
| models | logreg, random_forest, gradient_boosting (svm excluded, per 4y) |
| protocol | kfold, cv_k=10, inner_k=3 |
| runs | 36 |

Config committed `f8cced0`, launched under batch
`f21442d97da8472b83815f52475d8003`. Expected cost, from the direct
measurement in 4y: on the order of a day, dominated by random_forest's
grid search (~23 hours for grid alone on the two large classification
datasets; random and Bayesian plus house_16H add more on top of that).
This is accepted and expected, not a surprise to react to.

---

## 4za. Tuning on large datasets finished: gradient_boosting is the one model it reliably helps

`ofat_tuning_large` finished after roughly 30 hours (launched 13:12 on
2026-10-15, completed 20:00 on 2026-10-16): **36 runs, 33 succeeded, 3
skipped, 0 failed**. All three skips are `logreg` tuning on house_16H's
regression target, correctly refused by the applicability check from
4j (LinearRegression has no `C` to search); the untuned baseline for
logreg still ran there. Integrity_check ok, no succeeded cell
duplicated. Committed `f06291e`; config committed `f8cced0`.

n is 2 for classification (adult, bank-marketing) and 1 for regression
(house_16H), the same limit as every other large-dataset arm, so this
is a direct reading, not a tested finding.

| dataset | model | none | grid | random | bayesian |
|---|---|---|---|---|---|
| adult | gradient_boosting (F1) | 0.8006 | **0.8145** | **0.8154** | **0.8143** |
| adult | random_forest (F1) | 0.7879 | 0.7955 | 0.8004 | 0.7998 |
| adult | logreg (F1) | 0.7656 | 0.7685 | 0.7660 | 0.7663 |
| bank-marketing | gradient_boosting (F1) | 0.7302 | **0.7477** | **0.7494** | **0.7446** |
| bank-marketing | random_forest (F1) | 0.7205 | 0.7226 | 0.7179 | 0.7200 |
| bank-marketing | logreg (F1) | 0.6913 | 0.6923 | 0.6946 | 0.6925 |
| house_16H | gradient_boosting (RMSE) | 34144.7 | 32598.6 | 31719.1 | **31651.4** |
| house_16H | random_forest (RMSE) | 31513.2 | 31485.3 | 31408.9 | 31428.7 |
| house_16H | logreg (RMSE) | 49283.9 | skipped | skipped | skipped |

**gradient_boosting is the one model tuning moves by a real amount on
every dataset, at every level**: F1 gains of 1.4 to 1.9 points on the
two classification datasets, and a RMSE improvement of 1,546 to 2,493
on house_16H (4.5% to 7.3%), consistent in direction and size across
all three non-baseline tuning levels. random_forest moves a little
(F1 up to +0.8 points, RMSE down by roughly 0.3%) and logreg barely
moves at all (F1 within 0.3 points either way) on both classification
datasets.

This is the same shape of result as the smaller-dataset tuning arm
(4j, 4p): gradient_boosting's default hyperparameters (particularly
`n_estimators` and `max_depth`) leave real room on the table that a
search closes, while logreg's single hyperparameter (`C`) and
random_forest's defaults are already close to a local optimum for most
data. It extends that pattern to datasets 2 to 25 times larger than any
in the smaller-dataset arm, at a real compute cost: this single sweep
took roughly as long as every other sweep in the programme combined,
dominated by random_forest's expensive candidate fits (confirmed
directly in 4y: a single random_forest tuning fit on adult measured at
1,259 to 1,379 seconds depending on search strategy) and several very
long optuna Bayesian runs that were checked directly rather than
assumed stalled, more than once, during monitoring.

Grid, random and Bayesian search are indistinguishable from each other
here: no model or dataset shows a search strategy clearly ahead of the
others by more than noise, matching 4p's classification-level finding
(no search strategy result survived the v2-to-v3 correction) and
extending it to these three large datasets.

With this, every factor in the five-component design now has coverage
on the three large datasets (scaling: 4q; encoding: 4r; selection: 4u;
tuning: this section), closing the large-dataset gap entirely.

---

## 4zb. The dataset-characteristic meta-analysis, carried out 2026-10-16

The research report named this the highest-value next step because it
needs no new compute: the engine stores dataset characteristics on every
run, so "which properties of a dataset predict that a preprocessing
choice will matter?" is answerable from the 4,377 rows already recorded.
Written up in `docs/META-ANALYSIS.md`, with figures 7-9.

281 (dataset, model, factor) cells. Response is the SPREAD across a
factor's levels as a percentage of the baseline score, which makes
datasets on different target scales comparable.

### The sensitivity map

| | scaling | encoding | selection | tuning |
|---|---|---|---|---|
| logreg | 0.66% | 0.00% | 3.69% | 0.74% |
| svm | **6.31%** | 0.00% | 1.41% | **8.22%** |
| random_forest | 0.10% | 0.00% | 3.71% | 1.02% |
| gradient_boosting | 0.01% | 0.00% | 3.78% | 2.63% |

This is probably the most directly useful table the programme has
produced for an applied reader. SVM is the sensitive model; scaling is
irrelevant to tree ensembles (0.01% median for gradient boosting);
selection is the only factor that is consistently non-trivial for every
model family.

### Two corrections made while doing it

**`missing_pct` is contaminated by the injection sweeps.** Reading it
with `max()` over all runs returns the injected rate, so iris reads 30%
when its natural rate is zero. It must be read from uninjected runs
only. Corrected figure: 20 of the 25 registry datasets have 0.00%
natural missingness. (The earlier reports' "15 of 19" is the imputation
arm's 19 datasets and is also correct; both were re-verified.)

**An apparently strong correlation was a confound and was discarded.**
Natural missingness appeared to predict encoding sensitivity
(rho = 0.667, p < 0.0001), which has no plausible mechanism. In this
registry every dataset with missing values also has categorical features
(rho = 0.748 across the 25 datasets). Partial correlations settle it:
controlling for categorical fraction, the missingness effect collapses
to rho = 0.123 (p = 0.305), while categorical fraction survives at
rho = 0.780 (p < 0.0001). Reported as a confound, not a finding.

### What it found

- **cat_fraction predicts encoding sensitivity at rho = 0.883.**
  Mechanistically obvious, and it serves as the sanity check that
  validates the sensitivity measure before anything subtler is trusted.
- **Univariate filter selection is a tail risk.** Median selection
  spread is under 4%, but chi2 and mutual_info raise gradient boosting
  RMSE on energy-efficiency from 0.467 to 3.08, a sixfold increase, by
  discarding features the model needs jointly. RFE stays within 4% of no
  selection. Checked directly against the raw per-level RMSE to confirm
  it is a real effect and not a near-zero-baseline ratio artefact.
- **A negative result on the house_16H mechanism.** The hypothesis that
  feature-scale disparity predicts scaling sensitivity shows no
  relationship for any model (all p > 0.25). The likely cause is that
  `mean_abs_correlation` is the wrong proxy: it measures inter-feature
  correlation, not scale disparity, and the record stores no
  scale-ratio statistic. **Recommended instrumentation change: record
  max(std)/median(std) per dataset**, which is a one-line addition and
  makes the hypothesis testable on the next sweep.

### Honest limits

Cells are not independent (four models share each dataset, so effective
n is nearer 18 than 72), and no multiple-comparison correction was
applied across the 24 correlations tested, so roughly one false positive
is expected. The two headline results are far beyond that threshold; the
weakest (tuning vs mean_abs_correlation, p = 0.0463) is flagged as
unconfirmed in the write-up.

---

## 5a. The power floor acted on, not just reported, 2026-10-17

Section 4.4.4 of the research report recorded that five selection cells
had a significant global test and no surviving contrast, because at
n = 7 regression datasets with k = 4 levels the smallest attainable
Holm-adjusted p is (2 / 2^7) * 4 = 0.0625, above alpha. That was true
but incomplete as a response: the shortfall was a single dataset.

forest_fires (OpenML 42363, 517 rows, 12 features, 2 categorical, no
missing values) was added to the registry and the four affected arms
were re-run on that dataset alone, appending to their existing config
names. 64 runs, 61 succeeded, 3 skipped (logreg tuning on a regression
target, as always), 0 failed, about 19 minutes of compute. Integrity
check ok, no duplicate cells.

### What became detectable at n = 8

| arm | model | contrast | Holm | datasets |
|---|---|---|---|---|
| selection | gradient_boosting | chi2 worse than none | 0.0312 | worse on 8 of 8 |
| selection | gradient_boosting | rfe worse than none | 0.0312 | worse on 8 of 8 |
| tuning | gradient_boosting | bayesian beats none | 0.0469 | better on 7 of 8 |
| tuning | gradient_boosting | grid beats none | 0.0469 | better on 7 of 8 |
| tuning | svm (SVR) | grid beats none | **0.0234** | better on 8 of 8 |

The SVR grid result was already rejected at n = 7 (Holm 0.0469); the
extra dataset strengthened it to 0.0234 on 8 of 8. The other four are
new and could not have been found before.

The selection result is worth stating plainly because it runs against
the usual framing: on regression data in this registry, chi-square
filtering and recursive elimination each made gradient boosting worse
on **every** dataset tested. The arm's Friedman p was 0.0053 all along;
the effect was present and undetectable, not absent.

Programme totals move from 4,377 runs and 25 rejected contrasts to
**4,441 runs and 29**, across 26 datasets and 81.6 hours.

### Why this matters beyond the extra findings

The limitation is now reported as identified, acted on and resolved
rather than as an unfixed weakness, which is a materially different
claim. It also demonstrates the point section 4.4.4 makes: computing
the attainable floor costs minutes, and had it been done during design
rather than after collection, these five results would have been
available from the first analysis.

### Also added to the report in this pass

Effect sizes with bootstrapped confidence intervals are now reported in
the body (Table 4.5) rather than left in the record. Doing so exposed a
qualification worth stating: of the rejected contrasts, 14 have an
interval that excludes zero and 11 have one that touches or crosses it,
almost all in the imputation arm. Those are now described as weaker
evidence than the headline findings rather than presented as equivalent.

A worked leakage example was added to 4.5.1, so the claim that the
instrumentation catches a deliberate leak is backed by what the leak
actually does rather than asserted.

---

## 5b. Seed replication: the headline scaling result does not fully survive

Every run in the record used seed 671, so the scaling result rested on
one fold assignment. The whole scaling arm was repeated under seeds
1337 and 20260702, 608 runs in 1.8 hours, 576 succeeded and 32 skipped
(colic row deletion, as in every other scaling sweep), 0 failed. The
three seeds are kept under separate config names and are never pooled.

### Logistic regression, standard scaling against none

| seed | Friedman p | Holm | datasets improved | median difference |
|---|---|---|---|---|
| 671 | 0.0275 | **0.0410 rejected** | 10 of 11 | +0.0061 |
| 1337 | 0.0742 | not licensed | 8 of 11 | +0.0080 |
| 20260702 | 0.1746 | not licensed | 8 of 11 | +0.0070 |

**The contrast reaches significance under one seed of three.** Stated
as "standard scaling significantly improves logistic regression", the
finding does not replicate.

What does replicate is the effect. Standard scaling wins on the
majority of datasets under all three seeds, and the median improvement
is almost constant at 0.61, 0.80 and 0.70 of a percentage point. The
direction and the magnitude are stable; what moves is whether the win
count clears the threshold. At n = 11 the Wilcoxon test is sensitive to
a couple of sign changes, so 10 of 11 and 8 of 11 fall on opposite
sides of the boundary while the underlying difference barely moves.

### A second observation from the same sweeps

Under seed 1337 the SVM produced three rejected contrasts on accuracy
(minmax, robust and standard, each Holm 0.0176, 8 or 9 of 11 datasets).
The same arm is not significant under the other two seeds, at Friedman
0.0530 and 0.0771, both close to the line. The SVM behaves exactly like
logreg here: consistent in direction, intermittently significant.

### Why this is reported rather than quietly dropped

The replication was run to test a limitation and it found a larger one.
Reporting only the seed that worked would be the specific failure the
rest of this programme was built to prevent. The report now states the
result in section 4.4.7 with the table above, qualifies the claim in
4.4.1 and 4.6, and replaces the old "sensitivity to the seed was not
examined" limitation in 5.3.1 with what the replication actually found:
the registry is not large enough to establish this finding reliably,
which is different from the finding being absent.

Programme totals: 5,049 runs, 83.4 hours, 25 sweeps. The seed rows are
replication of an existing arm, not new coverage, and Table 4.3 says so.

---

## 5c. Three analyses over the existing record, no new compute

The seed replication in 5b left an awkward result. Rather than only
report it, three further analyses were run against data already
collected.

### A threshold for when a single-seed result can be trusted

If seed instability were random it would fall evenly across datasets.
It does not. Across the 132 (model, scaler, dataset) cells measured
under all three seeds, agreement on direction depends on effect size:

| mean effect | cells | seeds agree | rate |
|---|---|---|---|
| below 1 pp | 51 | 15 | 29% |
| 1 pp or more | 42 | 39 | **93%** |

Fisher exact test: odds ratio 31.2, p < 0.0001. Cells where all three
seeds return exactly zero are excluded as true no-ops rather than
counted as disagreement, which is the conservative reading; including
them raises the odds ratio to 65.

This converts 5b from a caveat into a rule: at 11 datasets and 10-fold
CV, a scaling difference below about one percentage point should not be
trusted from a single seed, and one above it generally can be. The
threshold is specific to this registry, but the procedure transfers and
cost 1.8 hours.

### Cost scales very differently by component

Mean wall seconds per run, by dataset size:

| component | <1k rows | 1k-10k | >10k | ratio |
|---|---|---|---|---|
| encoding | 2.8 | 16.7 | 133.2 | 47x |
| scaling | 4.2 | 16.3 | 378.1 | 91x |
| selection | 2.8 | 16.6 | 642.7 | **228x** |
| tuning | **51.4** | **615.2** | **3404.4** | 66x |

Tuning is the most expensive at every size, an order of magnitude above
the rest even on small data. Selection is cheap on small data and
scales worst, because the wrapper methods refit once per candidate
subset. By model: gradient_boosting 108.4s, random_forest 96.8s, svm
27.8s, logreg 25.0s averaged over all runs, so the component with the
worst evidence-to-cost ratio also benefits only the most expensive
model family.

### The meta-analysis re-run at n = 8, and a result lost

Repeating the dataset-characteristic analysis on the enlarged record:
categorical fraction still predicts encoding sensitivity at rho = 0.882
(was 0.883 on 72 cells, now 76), which is how a real relationship
behaves when observations are added.

**The weakest correlation did not survive.** Tuning sensitivity against
mean absolute correlation moved from rho = 0.248 at p = 0.0463 to
0.229 at p = 0.0608. The meta-analysis had already flagged it as
unconfirmed and warned that roughly one false positive was expected
among 24 tests. It is now withdrawn rather than carried forward.

Report totals: 14,164 words, 8 tables. Baseline package v1 was saved
before this work began; v2 captures it.

---

## 5d. Widening the registry and testing the imputation arm, launched 2026-10-17

Two pieces of work were launched together, both following directly from
the seed replication in 5b. In progress at the time of writing; this
entry records what was set up and why, and the results follow in a
later section.

### Submission packages saved first

Before starting, the project was archived as
`Submission/ITRI671 Pipeline Lab Submission v1.zip` (4.4 MB, 30 items)
so there is a complete, verified fallback if the remaining work runs
out of time. v2 was written after 5c. Each carries a manifest recording
every file with its size, modification time, SHA-256 prefix and the git
commit of the engine and docs repositories at packaging time, so the
contents can be dated rather than taken on trust.

### Five classification datasets, for stability rather than the floor

The classification side held 11 datasets. The discreteness floor is not
the binding constraint there: at n = 11 with k = 3 it is 0.0029, well
under alpha. The constraint is **stability**. Section 5b showed that at
this sample size two sign changes move a contrast across the threshold
while the underlying effect barely moves, which is why the scaling
result reached significance under one seed of three.

banknote, blood_transfusion, climate_sim, phoneme and steel_plates were
registered (OpenML 1462, 1464, 1467, 1489, 1504). All five are
complete, binary and numeric, chosen before scoring for a spread of
size (540 to 5,404 rows), width (4 to 33 features) and class balance
(0.093 to 0.801). They take the classification arms to **n = 16**.

320 runs across the four arms, appended under the existing config names.

### The imputation arm faces the seed test

The imputation arm carries 21 of the programme's 29 rejected contrasts
and every one rests on seed 671. Having shown that the scaling result
is seed-sensitive, leaving the arm that carries most of the findings
untested would be indefensible.

All six injected sweeps are repeated under seed 1337: 1,728 runs,
measured at roughly 3.4 hours from the originals. The seed changes both
the fold assignment and the injected missingness pattern, which is the
stronger test, since it asks whether a finding survives a different
draw rather than a different split of the same gaps. Separate config
names keep the seeds from being pooled.

### The risk is acknowledged in advance

If the imputation contrasts behave like the scaling ones, a substantial
part of the findings section will need qualifying shortly before
submission. That is the reason v1 and v2 exist. The alternative, not
running the check, would leave the single largest untested assumption
in the study for an examiner to find.

---

## 5e. The scaling arm at 16 datasets: the result moves between models

The five classification datasets from 5d are in (320 runs, 0 failed).
The scaling arm now has 16 classification datasets rather than 11, and
the picture changes in a way worth recording carefully.

| model | n=11 (seed 671) | n=16 (seed 671) |
|---|---|---|
| logreg | Friedman 0.0275, **standard rejected** Holm 0.0410, 10/11 | Friedman 0.0298, **nothing rejected**, standard Holm 0.0557 |
| svm | Friedman 0.0530, nothing rejected | Friedman 0.0154, **three rejected**: standard Holm 0.0071 (12/16), minmax and robust 0.0249 (11/16) |
| random_forest | not significant | not significant (0.8939) |
| gradient_boosting | not significant | not significant (0.1888) |

### The logreg result did not weaken, the correction did

Standard scaling against none for logreg is **12 of 16 at raw
p = 0.0186**, against 10 of 11 at n = 11. The win count and the raw
test both improved. It fails only because Holm multiplies the smallest
of three contrasts by three, giving 0.0557 against a bar of 0.05.

Two of the five new datasets return exactly equal scores for standard
and none (blood_transfusion and phoneme). Wilcoxon discards exact ties,
so adding five datasets added only three usable pairs to this contrast
while leaving the Holm multiplier unchanged. That is the mechanism, and
it is the same family of problem as 4.4.4: the procedure, not the data,
decides what can be reported.

### The SVM result is now the stronger one

At 11 datasets the SVM sat at Friedman 0.0530, just outside. At 16 it
is 0.0154 with three rejected contrasts, and standard scaling has a
confidence interval that **excludes zero** (+0.0036 to +0.1082), which
only 14 of the previous 29 contrasts could claim. This is the
best-supported scaling result the programme has produced, and it
matches the theoretical expectation most strongly: the SVM depends on
inner products and should be the most scale-sensitive model.

### What this means for the write-up

The report currently leads the scaling section with the logreg result.
On the enlarged registry that is no longer the defensible choice. The
SVM result is better supported, agrees with the literature, and has an
interval excluding zero. The logreg finding becomes a near-miss that is
reported honestly as such: a real effect on 12 of 16 datasets that the
correction does not license.

This also sharpens 5b and 5c. The seed instability, the n=11 fragility
and this reversal are three views of one problem, namely that the study
operates close to the resolution limit of its own statistical
procedure. The report should say that once rather than three times.

The imputation seed replication is still running, 1,116 of 2,048 runs.

---

## 5f. Two monitoring errors, and a real effect found while checking

The imputation seed replication reached 798 of 2,048 runs. Nothing is
wrong with it, but two checks on it went wrong, and both are the kind
of mistake that wastes an hour when it is not written down.

### The status column is not called what the query assumed

A progress query counted rows where `status = 'ok'` and returned zero
for every sweep. The engine writes `succeeded`, `failed` and `skipped`.
The sweep was at 734 succeeded, 64 skipped and 0 failed and looked like
a total failure for about a minute.

### Checking the wrong process name, which is how 4t happened

A process check on `python.exe` found one process at 0 CPU seconds and
11 MB after 24 minutes of uptime, which is the exact appearance that
led to a healthy run being killed in 4t.

The process list was read properly this time instead of acted on. The
`python.exe` entry is the virtual environment's launcher stub. The real
worker is its child, **`python3.11.exe`**, at 751 MB across 26 threads.
Measured over 45 seconds it used 55.9 processor seconds, so it is
running on several cores at full load.

The general lesson from 4t was to measure before concluding. The
specific lesson is narrower and more useful: **on this machine the
worker process is not named `python.exe`**, and a check that filters on
that name will always find an idle stub.

### A real difference in the skipped runs

Comparing which runs each seed skipped turned up something worth
keeping. Every skip is `drop_rows`, and seed 1337 skips a superset of
seed 671: 8 against 0 at MCAR 5 per cent, 24 against 20 at MCAR 15 per
cent, never fewer.

The cause is the injector. A different draw places the missing cells in
more distinct rows, and on a wide dataset that is enough for listwise
deletion to empty the training set. digits has 64 features and sonar
60, so at 5 per cent missingness almost every row carries at least one
gap.

This is the guard added after the bodyfat artefact (4.4.3) working on
the replication: rather than scoring a model on whatever fragment
survives deletion, the run is refused. It also means the two seeds
cannot be compared on `drop_rows` by win count alone, because they do
not have the same denominator. That contrast needs its sample size
stated per seed when the replication is analysed.

It is a further argument against `drop_rows` as a default. Whether the
method is usable at all depends on which cells happen to go missing,
not only on how many.

---

## 5g. All four classification arms at 16 datasets, and what the encoding null actually means

Section 5e tested the scaling arm by hand. `docs/analysis/`
`recheck_classification_arms.py` now does all four arms at once, runs
them twice (the original eleven datasets, then all sixteen) and reports
exact ties beside every contrast, so the two registries can be compared
directly rather than from memory.

### The net effect of the five datasets

Three contrasts gained, one lost, all in the scaling arm:

| | before, n=11 | after, n=16 |
|---|---|---|
| svm, standard vs none | not rejected | **rejected**, Holm 0.0071 |
| svm, minmax vs none | not rejected | **rejected**, Holm 0.0249 |
| svm, robust vs none | not rejected | **rejected**, Holm 0.0249 |
| logreg, standard vs none | rejected, Holm 0.0410 | not rejected, 0.0557 |

The SVM standard contrast is the only one whose interval excludes zero
(+0.0036 to +0.1082). It is the best-supported result in the
programme and the write-up should lead with it.

### A third instance of the instability pattern

The selection arm swapped which model reaches Friedman significance.
random_forest went from 0.0386 to 0.0649 and logreg from 0.0659 to
0.0202, in opposite directions, with no surviving contrast on either
side before or after. Nothing was gained or lost in reportable terms,
but it is the same phenomenon as 5b and 5e: results near the threshold
move when the registry changes, and the direction of the move is not
predictable. Three independent sightings of this is enough that the
report should treat it as a finding about the method rather than as a
caveat repeated three times.

### The encoding arm did not move at all, and that is the point

The encoding Friedman values are identical to four decimal places
before and after: 0.2636, 0.3679, 0.7165, 0.3679. Adding five datasets
changed nothing whatsoever.

The reason was checked rather than assumed. The runs exist, all five
datasets against all three encoders, none skipped. But all five are
entirely numeric, so the three encoders are no-ops and return **bit
identical** scores: 20 of 20 new dataset-model cells have onehot,
ordinal and target exactly equal. The test discards them, and the arm
stays at eleven.

Checking the original eleven showed the problem is not confined to the
new datasets. **34 of 44 cells there are also all-equal**, because only
three of the sixteen classification datasets carry categorical features
at all (credit-approval 9, credit-g 13, heart-c 7).

This changes what the encoding null is allowed to say. Across the whole
classification side, 54 of 64 cells apply a treatment that cannot have
an effect. The arm is not evidence that the choice of encoder does not
matter; it is a test conducted almost entirely on data where no encoder
does anything. The report currently states the encoding result as a
null finding and must instead state it as **not tested**, with the cell
count given.

The meta-analysis already said this from the other direction:
categorical fraction predicts encoding sensitivity at rho = 0.882, and
every dataset with no categorical features shows exactly zero spread.
The two analyses agree; only the confirmatory arm was phrased as though
it had answered a question it never put.

### Consequences for the write-up

1. Lead the scaling section with the SVM result, not logreg.
2. Report logreg standard as a near miss at 12 of 16 and Holm 0.0557,
   stated plainly rather than omitted.
3. Restate the encoding result as untested on this registry, with the
   54-of-64 figure, and move it from findings to limitations.
4. State the n of each arm separately. Scaling, selection and tuning
   are at 16 datasets; encoding is still at 11.
5. Consolidate the three instability sightings into one argument.

---

## 5h. How far the no-op problem reaches, and why scaling is the opposite case

Having found that the encoding arm is mostly no-ops (5g), the obvious
question is whether the other arms share the defect. They were counted
rather than assumed. A cell is a no-op when every level returns exactly
the same score, so the comparison carries no information.

| arm | no-op cells | reading |
|---|---|---|
| Encoding, classification | 54 of 64 | registry gap |
| Encoding, regression | 20 of 32 | registry gap |
| Scaling, classification | 22 of 64 | **a result, see below** |
| Selection, classification | 4 of 64 | sound |
| Tuning, classification | 2 of 64 | sound |

Selection and tuning are clean, so their null results are real nulls
and need no qualification. Encoding fails on both sides: five of the
eight regression datasets have no categorical features either, so the
restatement in 5g applies to the whole arm, not only to classification.

### The scaling no-ops mean the opposite thing

22 of 64 looked like the same defect until it was broken down by model:

| model | no-op cells |
|---|---|
| gradient_boosting | 12 of 16 |
| random_forest | 9 of 16 |
| svm | 1 of 16 |
| logreg | 0 of 16 |

Twenty-one of the twenty-two sit in the two tree ensembles, and almost
none in the two scale-sensitive models. These cells are not missing
information. A decision tree splits on rank order, which no monotone
rescaling changes, so an exactly identical score is the predicted
result arriving as a zero rather than as a small number.

The distinction matters for how the report argues. An encoding no-op
means the registry could not pose the question. A scaling no-op on a
tree means the question was posed and the answer is exactly zero, which
is stronger evidence of invariance than a small non-significant
difference would be. The same statistical signature carries opposite
meanings, and the write-up has to separate them rather than report a
single no-op count as a limitation.

It also explains the meta-analysis figure from the other direction:
gradient boosting's median scaling spread of 0.01 per cent is not a
small effect averaged over datasets, it is mostly exact zeros.

---

## 5i. Recounting every headline figure, and two mistakes caught by doing it

The report quotes run totals, dataset counts, cell counts and contrast
counts in fifteen separate places. The registry has grown twice since
those were written, so they were regenerated together rather than
patched one at a time, which is how a set of figures stops agreeing
with itself. `docs/analysis/report_figures.py` is now the single source
for them.

### The script was wrong first, in a way that mattered

The first version omitted the `drop_rows` exclusion that
`master_analysis.py` applies to the six injected sweeps, and reported
21 imputation contrasts heavy with `drop_rows` rows. Those are the
bodyfat artefact (4.4.3): listwise deletion scores the model on
whatever rows survive, so the comparison is not against the same
sample. Including it manufactures contrasts the study had already
withdrawn.

This is worth recording because it is the second time the same
artefact has had to be excluded, and the first time it reappeared
through new analysis code rather than new data. The protocol lives in
`master_analysis.py` and anything that recomputes these figures has to
match it rather than re-derive it.

Once corrected, the script returns **167 cells, exactly the figure the
report already states**. That agreement is the check that the
recomputation follows the established protocol, which makes the
remaining differences real rather than methodological.

### A misreading avoided

The contrast listing showed `logreg` against RMSE, which a logistic
regression cannot produce. The engine was read rather than assumed: the
record stores a model *slot* name, and on a regression target
`piplab.components.models` substitutes the counterpart estimator, so
`logreg` there is `LinearRegression`. The engine documents this in
`MODEL_SUBSTITUTIONS` and the record is sound. The script now prints
the estimator actually fitted, because the slot name invites exactly
this error.

### What actually changed

| figure | report states | record now | why |
|---|---|---|---|
| statistical cells | 167 | 167 | unchanged |
| significant global tests | 28 | 31 | registry growth |
| surviving contrasts | 29 | 34 | registry growth |
| experimental runs | 5,049 | 4,761 | the report's total counted the scaling seed checks as experiments |
| datasets | 26 | 31 | forest_fires plus the five classification datasets |
| measured hours | 83.4 | 85.5 | the new runs |

The run total needs care in the write-up. 4,761 is the experimental
record; the seed replications add 1,422 more at the time of writing,
and they repeat existing work rather than extending coverage, so they
belong in a separate line rather than in the headline figure. The
report currently folds them in, which overstates the experimental
programme.

These are not applied to the report yet. The imputation seed
replication is still running and will change the contrast counts
again, so the fifteen figures are updated in one pass when it lands.

---

## 5j. A figure that kept asserting a superseded result

All nine data figures predated the registry growth, so they were
regenerated. Looking at the output rather than trusting the "ok" line
caught two faults in Figure 4.3, the scaling chart.

### The caption was a string literal

The bars redrew from the current record. The caption did not, because
it was typed into the script, and it went on reading "Logistic
regression is the only model with a Holm-rejected gain (Holm = 0.041,
better on 10 of 11 datasets)". Every part of that is now false: the
support vector machine holds the rejected contrasts, logreg's is at
0.0557, and the arm has sixteen datasets.

A figure that refreshes its data but not its caption is worse than a
stale figure, because the numbers beside the chart look current. The
caption now computes the dataset count and the Holm value from the
record at draw time, so it cannot drift from the result it describes.
This is the same rule already applied to the summary page, where a
hardcoded count was removed for the same reason.

### The axis was clipping the result

`set_ylim(0.6, 0.9)` was fixed when the highest bar was below 0.9. The
new datasets lifted the support vector machine and random forest above
it, so both were cut off at the frame, and the chart could not show
the effect it exists to show. The limits now follow the data with a
margin.

The rebuilt figure makes the argument the section makes: the support
vector machine rises from 0.824 to 0.902, logistic regression moves
less, and the two tree ensembles are visibly flat.

### Why this one mattered

The figure is cited from 4.4.1, and that section was rewritten in the
same sitting to lead with the support vector machine. Had the figure
not been checked by eye, the report would have carried a corrected
paragraph beside a chart captioned with the result it was correcting.
Regenerating an artefact is not the same as verifying it.

---

## 5k. The imputation replication, three sweeps in: half the findings do not reproduce

The three MCAR sweeps of the replication are complete and were
analysed without waiting for MAR.
`docs/analysis/imputation_seed_check.py` does the comparison.

### The script reported 100 per cent first, and that was a bug

The first run returned a reproduction rate of 5 of 5. It also printed
"present in only one seed" against a long list of contrasts, which was
the reason to distrust the number rather than publish it.

The cause: `compare_levels` returns no comparisons when the Friedman
gate does not pass, so no key is written for that cell. The script
read an absent key as missing data and dropped the row. But an absent
key means the cell showed **no effect at all** under that seed, which
is the most important kind of disagreement there is. The rate was
being computed only over cells that cleared the gate under both seeds,
which is precisely the subset guaranteed to agree.

Every candidate contrast is now recorded, including the ones the gate
stopped, and the Friedman verdict is reported alongside.

### The corrected result

| | |
|---|---|
| rejected under 671, reproduced under 1337 | 5 |
| rejected under 671, **not** under 1337 | 5 |
| rejected under 1337, not under 671 | 6 |
| **reproduction rate** | **5 of 10, 50 per cent** |

Agreement on the global test is 21 of 36 cells, or 58 per cent. The
two seeds disagree about whether an effect exists at all in 15 cells.

### Some disagreements are not borderline

A threshold crossing from 0.049 to 0.051 would be unremarkable. These
are not that:

| cell | seed 671 | seed 1337 |
|---|---|---|
| mcar05 svm accuracy | 0.0297 | 0.6483 |
| mcar05 svm f1 | 0.0302 | 0.4169 |
| mcar15 gradient_boosting f1 | 0.6412 | 0.0131 |
| mcar30 regression random_forest | 0.6412 | 0.0084 |

These are reversals, not crossings. The classification side at mcar15
is the clearest case: under seed 671 logreg shows an effect and
gradient boosting does not, and under 1337 it is exactly the other way
round. A reader given one seed would conclude the effect belongs to a
different model family than a reader given the other.

### What survived

The reproducing contrasts are concentrated and interpretable. kNN
against mean imputation on regression at mcar15 holds at 8 of 9
datasets under both seeds, and median against mean on regression holds
at 0 of 9 and 1 of 9, meaning median is reliably worse. The svm kNN
result at mcar30 holds on both metrics. What reproduces is the large,
directionally consistent effects, which is the same conclusion the
scaling replication reached by its own route (5b): the effect-size
threshold, not the p-value, predicts whether a finding will survive a
different draw.

### Consequence for the report

The imputation arm supplies 21 of the study's rejected contrasts and
is presented as its main source of findings. On this evidence that
presentation cannot stand unqualified. Half of the MCAR findings do
not reproduce under a second seed, and the arm's results have to be
reported with that rate attached and with the surviving subset
identified.

MAR is still running. The final figure may move, but not enough to
change the conclusion: these contrasts are not stable at nine
datasets.

---

## 5l. The imputation replication, complete: 35 per cent reproduces

All six sweeps finished: 1,728 runs, no failures. The 2,048 figure
quoted while it ran was an overestimate of my own; 1,728 is the
correct total for six sweeps.

The timeline was reconstructed from the `started_at` and
`wall_seconds` columns rather than estimated, because an earlier note
in this entry guessed at it and guessed wrong:

| | local time |
|---|---|
| first run started | 17 Oct 22:21 |
| last run ended | 18 Oct 00:58 |
| wall span | 2.62 hours |
| sum of individual run durations | 2.60 hours |
| gaps longer than three minutes | none |

The 0.02 hour difference between the span and the sum is scheduling
overhead between runs. The absence of any gap above three minutes
establishes that the machine was awake and working continuously for
the whole sweep, so **2.6 hours is the replication's true cost** and
no part of it is suspended time.

The idle period afterwards is therefore bounded exactly: the sweep
ended at 00:58 and the next check was at 06:19, which is 5 hours 21
minutes during which the machine had simply run out of work. Colile
confirms it was still awake at 03:00 on 37 per cent battery and shut
down when the battery ran out, which matches. An earlier draft of this
entry attributed that window to sleep during the run; that was wrong
and is corrected here.

Skips rise with the missingness rate exactly as 5f predicted: 8, 24
and 36 at MCAR 5, 15 and 30 per cent, all `drop_rows`.

### The headline

| | |
|---|---|
| rejected under 671, reproduced under 1337 | 8 |
| rejected under 671, **not** under 1337 | 15 |
| rejected under 1337, not under 671 | 9 |
| **reproduction rate** | **8 of 23, 35 per cent** |

Agreement on the global test is 50 of 72 cells, 69 per cent. The MCAR
half alone had read 50 per cent; the MAR sweeps are worse, and mar30
loses six of its seven contrasts.

### The clearest single case

`mar30 / random_forest / accuracy` is the starkest result in the
programme: **p = 0.0063 under seed 671 and p = 0.9718 under seed
1337**. The comparison was checked directly rather than trusted. Both
seeds use the same nine datasets at comparable scores, so the registry
is identical and the test is sound. What differs:

| dataset | 671, knn minus mean | 1337, knn minus mean |
|---|---|---|
| digits | +0.0317 | +0.0323 |
| sonar | +0.0769 | -0.0055 |
| wine | +0.0229 | -0.0170 |
| pima | +0.0104 | -0.0261 |
| breast_cancer | +0.0070 | -0.0088 |

Under the first seed kNN beats mean imputation on 8 of 9 datasets with
one tie. Under the second it wins 4 of 9. Only `digits` holds both its
direction and its size. Every other dataset differs by under one
percentage point, and at 30 per cent missingness the sign of that
difference is decided by which cells the injector happened to remove.

This is not a threshold crossing. It is the same comparison returning
opposite answers because the quantity being measured is smaller than
the noise in measuring it.

### Effect size predicts reproducibility here too, but weakly

The 5c analysis was repeated on this arm, over 843 comparisons after
excluding 21 no-ops:

| effect size | agree on direction |
|---|---|
| below 1 percentage point | 205 of 368, **56 per cent** |
| 1 percentage point or more | 371 of 475, **78 per cent** |

Fisher exact test: odds ratio 2.8 at p = 4.9e-12. The direction
matches the scaling finding, derived independently on a different arm,
which is real support for the rule.

The levels do not match, and that matters more than the agreement
does. Scaling gave 93 per cent above the threshold and 29 below. Here
it is 78 and 56. **Fifty-six per cent is barely distinguishable from a
coin.** Raising the bar does not fix it:

| threshold | comparisons | agreement |
|---|---|---|
| 0.5% | 629 | 73% |
| 1% | 475 | 78% |
| 2% | 367 | 84% |
| 5% | 244 | 86% |
| 10% | 183 | 85% |

Agreement plateaus near 85 per cent from 2 per cent upward and never
approaches scaling's 93. There is no effect size at which an
imputation result on nine datasets becomes as dependable as a scaling
result on sixteen. The limit is the sample, not the effect.

### What this does to the study

The imputation arm supplies 21 of the study's rejected contrasts and
the report presents it as the principal source of findings. That
presentation cannot survive this. Two thirds of those contrasts do not
reproduce under a second draw, and the arm has nine datasets against
the scaling arm's sixteen.

The honest position, and the one the report will take:

1. The imputation findings are reported with the 35 per cent
   reproduction rate attached, not as settled results.
2. The eight that reproduced are named, since they are the defensible
   subset. kNN against mean on regression holds across both seeds at
   several rates, and median being worse than mean on regression holds
   at 0 or 1 of 9 datasets under both.
3. The arm's conclusions are stated as provisional pending more
   datasets, with nine named as the binding constraint.
4. The scaling arm becomes the study's strongest evidence, having
   sixteen datasets and a confidence interval excluding zero.

This is the outcome 5d anticipated when the replication was launched,
and it is the reason the v1 and v2 packages were written first. The
finding is uncomfortable but it is the most valuable thing the
instrument has produced: a study that tested its own largest
assumption and reported what it found.

---

## 5m. Separating compute time from calendar time, for the whole programme

Colile has twice had to point out that a stretch of elapsed time was
the machine idle or asleep rather than the study computing, and an
entry in 5l repeated the error from the other direction by assuming
sleep where there was none. The record can settle this exactly, so it
was asked rather than estimated again.

Every run stores `started_at` and its own `wall_seconds`. Summing
`wall_seconds` therefore measures only the time inside runs, and any
interval between them, whether idle, asleep or shut down, is excluded
by construction.

Over the whole programme, all 7,097 runs from 12 to 17 October:

| | |
|---|---|
| calendar span, first run to last | 128.1 hours |
| measured compute, sum of run durations | **89.8 hours** |
| idle, in 11 gaps over ten minutes | 37.9 hours |

The largest gaps are 16.8 hours overnight on 16 to 17 October, 6.3
hours on 12 to 13 October and 4.8 hours on 14 October. None of that
time is in the reported cost.

**The cost figures in the report were never inflated by sleep.** The
85.5 hours quoted for the experimental programme, and the 89.8
including replication, are sums of per-run durations. This is now
checked rather than asserted, and the check is one query, so there is
no reason to estimate it again.

The same query applied to the imputation replication showed no gap
above three minutes across its 1,728 runs, which is what established
that its 2.6 hours is continuous compute.

---

## 5n. The report rebuilt on the final record, and package v3

With the replication complete, the fifteen stale figures identified in
5i were updated in a single pass rather than individually, and the
report was rebuilt as
`Chapters/Pipeline Lab Research Report  _  18 October 2026.docx`.
A new date was used rather than overwriting the 17 October file,
because the content changed materially.

### What changed in the report

Section 4.4.7 gains the imputation replication: two new tables, the
35 per cent reproduction rate, the mar30 random forest case at
p = 0.0063 against 0.9718, and the effect-size comparison against the
scaling arm. The abstract and the conclusion both state the
replication result, since it qualifies the study's central claim and
should not be discoverable only by reading chapter 4.

Three earlier passages were corrected rather than merely renumbered.
The scaling section now leads with the support vector machine. The
encoding section states the arm as untested with the 54 of 64 figure.
The aside about the support vector machine being intermittently
significant under seed 1337 was rewritten, because the enlarged
registry resolved that intermittency in the direction the replication
had indicated, which is a better story than the one it replaced.

### The verification caught six things the rebuild did not

Running the checklist against the built document rather than the
source found:

1. `67 per cent` surviving in a paragraph added by a later script, in
   a back-reference whose line wrapping hid it from a source grep.
2. Table 4.3's per-component hours **all stale**, including 54.6 for
   tuning against a measured 58.1.
3. Table 4.6's cost-by-size figures stale in most cells.
4. Per-model costs stale: 108.4 and 96.8 seconds against measured
   118.5 and 104.5.
5. `228-fold` surviving a replacement that silently did not match.
6. Two apparent style violations, "modeling" and "we", which turned
   out to be inside verified reference titles and were correctly left
   alone.

Point 2 deserves singling out. Correcting the tuning share, the first
attempt divided 54.6 by the new total of 85.5 and wrote 64 per cent.
The arithmetic was right and the answer was wrong, because the
numerator was also stale: tuning actually measured 58.1 hours, giving
68 per cent. **Recomputing a figure from one stale input and one fresh
one produces a number that is new, plausible and incorrect.** The
check that caught it was going back to the database for both values
rather than reusing the one already on the page.

The document now passes: no stale figures, every expected figure
present, no em or en dashes, and every in-text citation matched
against the reference list. 15,499 words, 10 tables, 9 figures, 33
references.

### Package v3

`Submission/ITRI671 Pipeline Lab Submission v3.zip`, 5.2 MB, 35
entries, archive integrity verified. It carries the rebuilt report,
the full run record at 7,097 runs over 31 datasets, and the four
analysis scripts written during this work
(`recheck_classification_arms.py`, `report_figures.py`,
`imputation_seed_check.py`, `imputation_effect_threshold.py`), so
every figure in the report can be regenerated from the database by a
reader.

v1 and v2 remain in place. They were written as fallbacks before the
replication ran, and they are now superseded rather than deleted,
since the point of a dated fallback is that it stays where it was.

---

## 5o. Widening the imputation arm, and a duplicate-row mistake

Four further pieces of work were started on 18 October, following the
replication result in 5l. This entry records the setup and one error
made during it.

### The instrumentation gap is closed

`feature_scale_ratio`, defined as max(std) / median(std) over the
numeric features before any scaling, is now recorded on every run.
The meta-analysis had flagged this as a concrete gap: the study used
`mean_abs_correlation` as a proxy for scale disparity, and that
statistic measures something else entirely, so the house_16H mechanism
could not be tested across the registry.

The new statistic was checked against the case that motivated it:

| dataset | feature_scale_ratio | mean_abs_correlation |
|---|---|---|
| house_16H | **742,937** | 0.1488 |
| wine | 388 | 0.3050 |
| iris | 2.2 | 0.5941 |
| digits | 1.5 | 0.1236 |
| concrete | 1.5 | 0.2075 |

house_16H is separated from ordinary datasets by five orders of
magnitude, while the old proxy ranked it *below* iris. That is direct
evidence the proxy was wrong and the replacement measures the intended
property.

The median is used as the denominator rather than the minimum, so a
single near-constant column cannot send the ratio to infinity. Six
tests cover the behaviour and the full suite passes at 348. Existing
rows read NULL, which the engine's column migration handles already.

### The imputation arm goes from 9 datasets to 14

Seven registry entries qualified and were not in the arm: banknote,
blood_transfusion, climate_sim, phoneme and steel_plates for
classification, house_16H and forest_fires for regression. All are
complete, so an injected rate stays truthful, which is the criterion
that excluded heart-c, credit-approval, colic and autoMpg originally.

Twelve sweeps are queued, six missingness settings under seeds 671 and
1337, so the widened arm can be replicated like for like. 400 runs per
sweep against the previous 288.

### The mistake: two copies of one sweep at once

A single sweep was started first to measure the cost, and the queue
for the remaining eleven was then launched before that sweep had
finished. The queue skips a sweep only when the record already holds
its full 400 runs, and a partially complete sweep does not meet that
test, so it started a second copy of the same configuration.

Two faults, both mine:

1. A first attempt to chain the queue behind the running sweep used a
   detached shell. The harness terminated the child when the wrapper
   exited, so the queue never ran at all and the log was empty. The
   launch message said "queue armed", which was not true. Checking the
   log rather than trusting the message is what caught it.
2. Restarting the queue directly then put two copies of
   `wide_imputation_mcar05_s671` on the machine together.

The duplicate was stopped once the process list confirmed it, and 26
cells had by then been written twice under two `batch_id` values.

**No result is affected.** All 35 overlapping rows are scored
identically across the two batches, which is what a deterministic
engine given the same seed should produce, and is a small unintended
confirmation that it is deterministic. The rows are redundant, not
contradictory.

The record is append-only, so nothing was deleted. The analysis for
this arm selects one batch per configuration instead, and the
duplicate check that already runs before every commit now also covers
the `wide_imputation` sweeps.

The lesson is narrow and worth keeping: **a queue that skips completed
work does not skip work in progress.** Either wait for the running job
or have the queue refuse to start a configuration that already has an
active process.

---

## 5p. The held-out test: the prediction was not confirmed

The study's strongest result, support vector machine scaling, was put
to a pre-registered test on five datasets the study had never used.
The prediction, the datasets, the procedure and the decision rule were
written into `docs/PREREGISTRATION-HELDOUT.md` and **committed to git
at 06:54 (1f82653) before any of the five had been scored**, so the
timestamp establishes that the hypothesis preceded the data.

**The prediction was not confirmed.**

| dataset | none | standard | difference |
|---|---|---|---|
| eeg-eye-state | 0.5512 | 0.6587 | **+0.1075** |
| kc1 | 0.8502 | 0.8530 | +0.0028 |
| mozilla4 | 0.8720 | 0.8736 | +0.0015 |
| diabetes_sylva | 0.7136 | 0.7119 | -0.0017 |
| wall-robot-nav | 0.8906 | 0.8886 | -0.0020 |

Standard scaling won on 3 of 5 at a one-sided Wilcoxon p of 0.3125.
The registered bar was p below 0.05 and at least 4 of 5 wins. Neither
was met. The registered falsification condition, 2 or fewer wins, was
also not met, so the registered verdict is **a failure to confirm
rather than a refutation**, and that is how it is reported.

### The control worked, which matters

Random forest on the same five datasets: 1 win of 5, p = 0.6875,
median difference -0.0001. The control was included to show the test
could distinguish a real effect from a procedure that finds one
everywhere, and it did. The instrument is not manufacturing results.

### What the numbers actually say

The headline of 3 of 5 conceals the shape of the data. One dataset
moved **10.8 percentage points**, the largest single scaling effect
recorded anywhere in this study. The other four moved by less than
0.3 of a percentage point in either direction, which is inside the
band where this study has already shown, twice, that the sign of a
difference is not reproducible.

So the result is not that scaling fails to help support vector
machines. It is that on four of the five datasets there was nothing
to find, and the test counts a 0.15 percentage point win and a 10.8
point win as one each. Wilcoxon on five datasets cannot distinguish
those cases, and the pre-registration said in advance that five
datasets gives a weak test whose smallest attainable p is 0.031.

The honest summary: the effect appeared where it was large and was
absent where it was small, which is consistent with the effect-size
threshold the study established independently in 5c and 5l. That
consistency is real support for the threshold finding, but it is not
what was registered, so it cannot be claimed as a confirmation of the
scaling result.

### A negative result on the new statistic

`feature_scale_ratio`, added hours earlier in 5o, was checked against
these five to see whether it predicts the gain. **It does not.**

| dataset | feature_scale_ratio | svm gain |
|---|---|---|
| kc1 | 2,218 | +0.0028 |
| mozilla4 | 508 | +0.0015 |
| diabetes_sylva | 64 | -0.0017 |
| eeg-eye-state | 9.4 | **+0.1075** |
| wall-robot-nav | 1.3 | -0.0020 |

The dataset that moved has the second *lowest* ratio, and if anything
the relationship runs backwards. This is reported as a negative
result. The statistic does what it was built for, separating
house_16H from ordinary datasets by five orders of magnitude, but
that mechanism is a least-squares solver discarding singular values,
and support vector machine kernel sensitivity is a different thing.
Closing one instrumentation gap did not close the other, and the
report should not imply it did.

### Why this strengthens the study

An examiner's sharpest question about a registry that grew during the
study is whether the findings are an artefact of dataset selection.
Before today there was no answer. Now there is one, it is documented
in advance, and it is unflattering.

A study that pre-registers a test of its own headline result and
reports that the test did not confirm it is more credible than one
that never looked. The 16-dataset result stands on its own evidence
and is not withdrawn, but its generality is now an open question
stated in the text rather than an assumption left for someone else to
find.

---

## 5q. Widened imputation arm, interim: two of six sweep pairs in

The queue is running (started 06:52, roughly 55 to 110 minutes per
sweep depending on missingness rate). mcar05 and mcar15 are complete
under both seeds; mcar30, mar05, mar15, mar30 are not, so this is an
interim reading, not the final one.

### The duplicate count was verified precisely, not estimated

5o reported 26 duplicated cells from checking a 35-row sample. The
full comparison script found 222. Checked directly: `mcar05_s671`
holds two batches, one of 400 rows and one of 222, and all 222
overlapping (dataset, model, imputation) cells were compared at full
precision. **Every one agrees.** mcar15 has one batch per seed at
exactly 400 rows and no duplication at all. The 5o entry undercounted
because it sampled rather than checked the full set; this entry
corrects it. The conclusion is unchanged and now rests on a complete
check: the duplication is redundant, not contradictory, and does not
touch any result.

### Interim reproduction rate

| | 9-dataset arm (final) | 14/11-dataset arm (2 of 6 sweeps) |
|---|---|---|
| reproduced | 8 of 23 | 4 of 7 |
| rate | 35 per cent | 57 per cent |
| global-test agreement | 50 of 72, 69 per cent | 16 of 24, 67 per cent |

The reproduction rate looks improved; the global-test agreement does
not. Seven contrasts is too few to treat the first figure as
established, and it is reported here as an interim reading only. What
is more informative at this stage is the pattern in which cells
changed: several moved from "no global test" under one seed to a
passing Friedman test under the other, at the larger sample, which is
the direction widening the registry should produce if the original
diagnosis was right. This will either firm up or wash out as the
remaining four sweep pairs land, and the final figure is the one that
will be reported.

---

## 5r. Widened imputation arm, all three MCAR sweeps complete

mcar05, mcar15 and mcar30 are now complete under both seeds (7 of 12
sweeps done overall; mar05 through mar30 remain). This is still not
the final figure, but it is a larger and steadier reading than 5q's.

| | 9-dataset arm (final) | 14/11-dataset arm, MCAR only |
|---|---|---|
| reproduced | 8 of 23 | 6 of 10 |
| rate | 35 per cent | **60 per cent** |
| global-test agreement | 50 of 72, 69 per cent | 24 of 36, 67 per cent |

The reproduction rate has held at roughly this level across two
successive checks (57 per cent at 2 sweeps, 60 at 3), which is a
better basis for treating it as real than a single reading would be.
Global-test agreement remains close to the nine-dataset figure rather
than improving with it, which says the extra datasets are helping
contrasts that already passed the gate survive a second seed more than
they are helping new cells pass the gate in the first place.

### One result checked directly: random forest loses badly to kNN at 30 per cent

`regression/rmse_mean/random_forest/knn` under seed 1337 rejects at
p = 0.0195 with kNN beating mean on only 1 of 11 datasets, which reads
as an unusual result worth checking rather than trusting from the
summary line. Checked directly against the per-dataset scores: kNN is
worse than mean on 10 of 11, consistently, with differences from
+0.006 to +1.18 RMSE and one extreme case, **house_16H, at +825**.
That dataset's known scale disparity (feature_scale_ratio of 742,937,
5o) plausibly distorts kNN's distance calculation at high missingness,
compounding across its many imputed cells. The pattern is genuine, not
a data artefact, and is a candidate explanation worth stating if it
survives the mar sweeps too.

The mar05, mar15 and mar30 pairs are still running (queue at 7 of 12,
sweep 8 of 12 under way). The figure above is not final.

---

## 5s. A guard that could not see a deleted class

The `mar15_s671` sweep exited non-zero with 3 failures, the first in
the whole widened arm. The exit code was investigated rather than
written off as the sklearn convergence warning printed beside it, and
it turned out to be a real bug in the engine's own safety check.

### What happened

All three failures were `climate_sim` with `drop_rows`, on logreg, svm
and gradient_boosting, each raising a different single-class error
from inside sklearn. Reproduced directly: climate_sim has a 494 to 46
class split, and at 15 per cent MAR the injector plus listwise
deletion left **70 rows, all of one class**. The 46-member minority
class was removed entirely.

### Why the existing guard missed it

A guard added on 2026-10-13 already refuses a dataset whose smallest
class falls below the fold count. It computes
`y.value_counts().min()`. **`value_counts()` only counts classes that
are present**, so a class deleted outright does not appear in the
tally at all, and `min()` returned 70, the size of the one surviving
class, comfortably above the 10 folds requested. The check passed.

A rare class and an absent class are different failures. The old test
could only ever catch the first.

### The dangerous part was the run that succeeded

Three models crashed, but **random_forest did not: it scored accuracy
1.0 and f1 1.0 on a single-class problem and the record stored that as
a successful result.** A crash is self-announcing. A meaningless 1.0
sitting in the record next to real numbers is not.

Every `drop_rows` classification success in the whole 9,000-row record
was then scanned by re-deriving the post-deletion class count for each
one. **Exactly one contaminated run exists**, this climate_sim case.
It belongs to the widened arm, which is new work that has not entered
any report, so no published figure is affected. The other
accuracy-1.0 runs in the record sit at full row counts on genuinely
easy datasets and are legitimate.

### The fix

The surviving-class count is now checked first and separately, before
the smallest-class test, and refuses with its own message. Verified on
the real failing case: all four models now skip cleanly with a
recorded reason, random_forest included. Two regression tests were
added, one for a class deleted outright and one confirming a rare
class still gets the older, different refusal. Suite at 350 passing.

The affected cells will be re-run with the fix in place so they are
recorded as skips rather than as three failures and one false success.

---

## 5t. Widened arm at five of six pairs: the diagnosis is holding

mar05 and mar15 are now complete under both seeds. Only mar30 remains.

| | 9-dataset arm (final) | widened arm, 5 of 6 pairs |
|---|---|---|
| reproduced | 8 of 23 | 10 of 16 |
| rate | 35 per cent | **62 per cent** |
| global-test agreement | 50 of 72, 69 per cent | **46 of 60, 77 per cent** |

The reproduction rate has now held across four successive readings as
the sample grew: 57 per cent at 2 pairs, 60 at 3, 62 at 5. A figure
that stays put while the denominator doubles is far better evidence
than any single reading.

### A correction to 5r

5r observed that global-test agreement was *not* improving (67 per
cent against the nine-dataset arm's 69) and reasoned from that the
extra datasets were helping already-passing contrasts survive a second
seed rather than helping new cells pass the gate. **With mar05 and
mar15 in, that reading is wrong.** Agreement is now 77 per cent,
clearly above the nine-dataset figure. The MCAR-only reading was
drawn from 36 cells and did not survive the sample doubling.

This is the fourth time in this study that a pattern read off a small
sample has reversed on a larger one, which is the study's own central
finding arriving yet again in its own process. It is recorded rather
than quietly overwritten.

### What this means if mar30 agrees

The original diagnosis in 5l was that the imputation arm's 35 per cent
reproduction rate was caused by its nine-dataset sample rather than by
anything deeper. Adding five classification and two regression
datasets nearly doubled the reproduction rate and lifted global-test
agreement by eight points. That is direct support for the diagnosis,
and it converts the 5l result from an awkward limitation into a
measured relationship between sample size and reproducibility, which
is a considerably stronger contribution.

The final figure waits on mar30.

---

## 5u. The widened imputation arm, complete: the diagnosis was right

All twelve sweeps finished: 4,822 runs over 24.4 hours of queue time.
Two sweeps carried the climate_sim failures described in 5s; those
cells were re-run with the fixed guard before the final analysis, so
the figures below rest on a clean record.

### The headline, on identical cell counts

| | nine datasets | fourteen / eleven datasets |
|---|---|---|
| contrasts reproduced | 8 of 23 | 10 of 17 |
| **reproduction rate** | **35 per cent** | **59 per cent** |
| global-test agreement | 50 of 72, 69 per cent | 54 of 72, **75 per cent** |

Both arms are compared over exactly 72 cells, so the agreement figures
are directly comparable rather than scaled.

The reproduction rate held steady across five readings taken as the
sample grew: 57 per cent at two sweep pairs, 60 at three, 62 at five,
59 at six. A number that stays in a narrow band while its denominator
more than doubles is much better evidence than any single reading, and
the slight fall at the end is the sort of movement a rate of this size
makes on seventeen observations.

### What it establishes

5l reported that the imputation arm reproduced at 35 per cent and
attributed that to its nine-dataset sample rather than to anything
deeper. Adding five classification and two regression datasets raised
reproduction from 35 to 59 per cent and gate agreement from 69 to 75.
**The diagnosis is confirmed by intervention rather than argument.**

This changes what the study can say. The 5l result on its own is a
limitation: most of the main arm's findings do not replicate. With
5u beside it the pair becomes a measured relationship between
registry size and reproducibility, demonstrated by changing the one
variable and observing the effect. That is a contribution rather than
an apology, and it is the strongest methodological result the
programme has produced.

It also sets the honest ceiling. 59 per cent is better than 35 but it
is not high. Fourteen datasets still leave four of every ten
rejected contrasts failing to survive a change of seed, so the
recommendation that follows is not "the problem is solved" but "this
kind of study needs more datasets than the field customarily uses,
and the shortfall is measurable".

### The second false success

5s found one contaminated run and scanned the record for others,
finding none. That scan ran before mar30 had finished. With all twelve
sweeps in there are **two**, the same climate_sim cell at 15 and 30
per cent MAR, both recording accuracy 1.0 on a single-class problem.
Both are now superseded by skips. The scan logic was right; it was run
too early, which is worth noting because an "all clear" on a record
that is still being written is not an all clear.

---

## 5v. Report rebuilt, and a run total that would have overstated the study

The report was rebuilt as
`Chapters/Pipeline Lab Research Report  _  19 October 2026.docx` with
two new sections: 4.4.8 on the widened arm and 4.4.9 on the
pre-registered held-out test. 16,486 words, 12 tables, 9 figures, 33
references, verification clean.

### The totals needed separating, not updating

`report_figures.py` counted as "experimental" anything not named
`seed_check%`. With the widened arm and the held-out set in the
record, it returned **9,891 experimental runs over 36 datasets in
110.1 hours**, and those numbers were nearly written into the report.

They would have overstated the study. The widened arm is a
*replication* of existing sweeps at a larger registry, not new
exploratory coverage, and the held-out five are a separate
confirmatory test that by design took no part in generating any
hypothesis. Counting either as experimental work inflates the
programme.

Broken out properly:

| | runs | hours | datasets |
|---|---|---|---|
| main experimental programme | 4,761 | 85.5 | 31 |
| seed replication, both arms | 2,336 | 4.4 | 22 |
| widened imputation arm | 5,054 | 24.5 | 25 |
| pre-registered held-out test | 20 | 0.1 | 5 |

The main programme figures are **unchanged**: 4,761 runs, 31 datasets,
85.5 hours. That is what the report states, with the rest on their own
lines. The script now excludes all four replication and confirmation
prefixes and carries a comment saying why, so the inflated figure
cannot come back.

This is the same category of error as the stale-numerator mistake in
5n: a number that is arithmetically correct, plausible, and measures
the wrong thing. Both were caught by asking what the figure was
supposed to mean rather than whether it computed.

### Package v4

`Submission/ITRI671 Pipeline Lab Submission v4.zip`, 6.89 MB, 43
entries, integrity verified, SHA-256 beginning 3e690cc6. It adds the
pre-registration document, which is the evidence that the held-out
prediction preceded the data, and the queue runners and config
generators that produced the widened arm.

v1 to v3 remain in place as dated fallbacks.

The third-seed sweeps (option 2) are running, one of six complete at
the time of writing. They will add a third draw to the nine-dataset
imputation arm, matching the scaling arm's three-seed design, and are
reported when they land.

---

## 5w. Three seeds on the imputation arm: 8 per cent survive all of them

The third draw (seed 20260702) completed: 1,728 runs in 4.9 hours,
**zero failures**, with the fixed guard holding throughout. The
nine-dataset imputation arm now has three seeds, matching the scaling
arm's design since 5b.

Three draws permit a measure two cannot: not whether a pair agreed,
but how many of three independent draws rejected each contrast.

| | contrasts | share |
|---|---|---|
| rejected under **3 of 3** seeds | 3 | **8 per cent** |
| rejected under 2 of 3 | 9 | 25 per cent |
| rejected under **1 of 3** | 24 | **67 per cent** |
| ever rejected under any seed | 36 | |

This is markedly worse than the two-seed figure in 5l implied. Two
thirds of everything this arm has ever called significant appears
under exactly one draw of three. **Each of those 24 would have been
reported as a finding had that seed been the only one run**, which is
exactly how a single-seed study is normally conducted.

### The three that survived everything

| sweep | contrast |
|---|---|
| mcar05 | regression, logreg, median against mean |
| mar05 | regression, logreg, median against mean |
| mcar30 | classification, svm, knn against mean |

Median imputation being worse than mean for regression at 5 per cent
missingness is the only result appearing under both mechanisms and all
three seeds. It is the single most dependable imputation finding the
programme has produced, and it is a negative one.

### The seed the study chose is the most generous of the three

The three designs are identical: 288 runs per sweep per seed, the same
nine datasets, near-identical success counts (checked, because an
asymmetry here would have made the comparison meaningless). The number
of contrasts each draw rejects is not:

| seed | contrasts rejected |
|---|---|
| **671** | **23** |
| 1337 | 17 |
| 20260702 | 11 |

Seed 671 is the one the study's findings rest on, and it yields more
than twice as many rejections as 20260702. Run under that seed
instead, this arm would have reported fewer than half its findings.

This is **not** cherry-picking: 671 was fixed before any data was
collected and is documented throughout. That is the point worth
making. An honestly pre-committed, arbitrary choice still determined
more than half of what the arm reported, and no amount of care in
choosing it would have helped, because there is nothing to choose on.
The only defence is to run more than one, which is what this section
does.

### How this sits with 5u

5u widened the registry and raised two-seed reproduction from 35 to 59
per cent. 5w holds the registry at nine and adds a third seed, finding
8 per cent unanimity. The two are consistent and measure different
things: 5u shows the instability shrinks as the registry grows, 5w
shows how severe it is at the original size when examined properly
rather than pairwise.

Together they make the study's central methodological claim concrete:
a preprocessing comparison on roughly ten datasets under one random
seed is close to unreproducible, the deficit is measurable, and it is
substantially fixable by enlarging the registry.

---

## 5x. Table numbering, a verification gate, and package v5

Adding the three-seed section to the report produced a second
"Table 4.10". Checking the rest found the clash was not the only one:
the cost-by-size table had been inserted as 4.6 when 4.5 was free, and
the effect-size table still carried 4.5 while appearing last. Three
numbering faults, two of them pre-existing and none visible in the
source, because a table's number is only wrong relative to the
*order* its captions appear in.

All thirteen tables were renumbered by document position, 4.1 to 4.13,
and the three prose references that introduce them were updated to
match. Numbering is law in this project because sibling chapters
cross-reference it, so this had to be exact rather than approximately
right.

### The verification script had two false positives of its own

Checking the rebuilt document raised three failures, and **two were
defects in the checker, not the report**:

1. It counted any paragraph beginning "Table 4.3" as a caption, so a
   sentence introducing a table ("Table 4.3 summarises the experiments
   that were run") read as a duplicate caption. It now filters on the
   Caption *style*.
2. It screened for the bare string "67 per cent", left over from the
   stale tuning-cost figure. That string now legitimately appears in
   the three-seed table, where 24 of 36 contrasts is 67 per cent. It
   now matches the full claim, "67 per cent of the total compute",
   rather than a number that any result might contain.

A checker that cries wolf is worse than none, because the next real
failure gets waved through. Both were fixed and the gate is now
committed as `docs/analysis/verify_report.py` rather than living in a
scratch directory, which is the same mistake 5v recorded about the
queue runners.

### Final state

The report is `Pipeline Lab Research Report  _  19 October 2026.docx`:
16,845 words, 13 tables, 9 figures, 33 references, verification clean.
Sections 4.4.7 to 4.4.9 now carry the two-seed replication, the
three-seed analysis, the widened registry and the pre-registered
held-out test.

`Submission/ITRI671 Pipeline Lab Submission v5.zip`, 7.48 MB, 45
entries, integrity verified, SHA-256 beginning 437b4963. The record
stands at 13,899 runs over 36 datasets and 119.3 hours of measured
compute, of which 4,761 runs over 31 datasets and 85.5 hours are the
main experimental programme and the rest is replication and
confirmation.

v1 to v4 remain as dated fallbacks.

### Which arms can actually produce a finding

Checked rather than assumed, for all four:

| arm | informative datasets | effective n | can reject? |
|---|---|---|---|
| imputation | 4 (have missing values) | 4 | no, floor 0.125 vs bar 0.0167 |
| encoding | 3 (have categoricals) | 3 | no, floor 0.25 vs bar 0.025 |
| **scaling** | all 19 | 19 | **yes** |
| **selection** | all 19 | 19 | **yes** |

Scaling and selection apply to every numeric dataset, so they keep the
full n and are the two arms that can yield a significant result. The
first two arms are descriptive, and the honest framing for the write-up
is that **two of the five factors cannot be tested for significance on
a dataset collection with naturally occurring missingness and few
categorical features**. Injecting synthetic missingness, or selecting a
collection richer in categorical data, is what would change that - and
both are design decisions for a supervisor, not code changes.

---

## 5. Bugs found by running the thing

Each of these was found by executing real work, not by reading code.

| Bug | How it surfaced | Fix |
|---|---|---|
| **prepfx model key** | Dashboard said `logreg`; prepfx's key is `logistic`. Latent since step 3 | Fixed in adapter, docs and every test. B2 genuinely uses `logreg`, so the two engines differ |
| **prepfx would overwrite real B1 results** | `run_experiment.py` writes `outputs/tables/*.csv` by arm name, unconditionally | `_isolate_outputs_dir` redirects every dashboard run into its own directory. Verified by diffing the real file's bytes |
| **sklearn leaked into the dashboard interpreter** | 16 tests failed on a fresh venv, 0 locally | Extracted import-free `components/budgets.py`, plus two AST guards |
| **FitSpy invented row ids** | False leak report when X became a numpy array | Verified the correct behaviour first, then added an `indexed` flag |
| **LASSO selected zero features** | `ValueError: 0 feature(s)` | `_MinFeatures(minimum=1)` after confirming unwrapped behaviour |
| **Cost estimate priced all tuning at the dearest level** | 5,580 vs true 2,880 | Sum per (technique, model) |
| **`inner_k` silently dead** | `/estimate` passed the whole form to a validator that rejects unknown fields | Fixed plus regression test |
| **Model substitution was silent** | diabetes/logreg gave identical RMSE across all four scalers | Checked it was mathematically correct, then added `models.substitution_note()` |
| **Negative time on a chart axis** | Cost chart showed -2.392 seconds | Axes clamp to zero for non-negative quantities |
| **Explorer dumped 500 rows** | Page was 10,628px tall | Capped at 25 with "show more"; now 2,608px |

Two **environment** failures worth recording because they look like
bugs: a pip hash mismatch caused by a corrupt partial download in the
shared cache (fixed with `--no-cache-dir`), and a timing test that fails
under load but passes in isolation because it measures CPU time while
261 other tests compete for 8 cores.

---

## 6. The analysis UI, and the sync problem it solved

**The gap.** Every lab data endpoint was keyed by a `run_id` held in
`core/runner.py`'s in-memory `_PROCESSES` dict. Two consequences: a
sweep launched at the command line was invisible to the UI, and
restarting the server lost every id. Since all 201 rows were CLI runs,
**the analysis pages could not see a single real result**.

**The decision.** Three options were weighed: copy rows into a dashboard
database, move to a shared central database, or read the engine's
`lab.db` directly. Direct read was chosen: the engine stays the only
writer, nothing is copied so nothing can drift, and the dashboard opens
the file with `mode=ro` so a bug in the UI cannot cost a run. A test
asserts a `DELETE` actually raises, rather than merely asserting that
read-only was requested.

**Auto-refresh.** Pages poll a cheap `/api/analysis/pulse` returning
only mtime and row count, fast while a sweep runs, slow when idle,
stopped while the tab is hidden. Verified live: the dashboard went from
**214 to 253 runs with no reload** while a CLI sweep was running.

**Four pages**, written plain-first with expandable depth so one page
serves a newcomer and a researcher:

- `/dashboard` - counts, sweeps, cost chart, live badge
- `/findings` - the verdict in a sentence, then win/loss bars, then
  three layers of expandable explanation
- `/explorer` - any field against any other, presets, CSV export
- `/guide` - server-rendered prose, loads no page script, so it works
  even if everything else fails

**The agreement that matters.** A test asserts the dashboard's findings
reproduce the engine's own `analyse.py` exactly (Friedman 9.1415,
p 0.027467, Holm 0.041016, 10 of 11 wins). A UI that quietly disagreed
with the thesis would be worse than no UI.

**scipy was added** to the dashboard's requirements for this. It is a
soft dependency: `findings.py` degrades with a clear message if it is
absent, and the existing guard keeping sklearn out of the costing path
is untouched.

---

## 7. UI simplification

Audited for emoji and found four real ones in the nav, written as
numeric entities (`&#128194;` and friends) so a plain text search missed
them, plus geometric glyphs and a `&rsaquo;` breadcrumb separator.

The frontend is now **ASCII-only**, enforced by 47 guard tests that
check source files and rendered pages for non-ASCII, numeric entities
and named glyph entities. The guard is non-vacuous: injecting an emoji
into a template makes it fail at both the file and rendered-page level.

Visual language: white surfaces, one blue accent (`#1a73e8`), text-only
navigation, no shadows, and every corner square through a single
`--radius: 0` token. Colour is never the only channel: every status
prints its word and the sortable table spells out "(asc)" / "(desc)"
rather than drawing an arrow.

---

## 8. Open items

### Nothing is blocking. These are choices, not defects.

| Item | State | Why it matters | Cost |
|---|---|---|---|
| **Four factors unrun** | Only `scaling` has sweeps. Imputation, encoding, selection and tuning have configs but no runs | This is the bulk of the remaining research. Imputation is the natural next one | ~15 min for imputation on small datasets |
| **adult, bank-marketing** | adult has 1 of 8 runs, bank-marketing 0 | The only datasets large enough to address SQ3, effects moderated by sample size | 4 to 8 hours; SVM is O(n^2) on 45,000+ rows |
| **Regression arm is a null at n = 8** | Friedman p = 0.2561 | Reported as a finding with a mechanism, not a failure. A seventh and eighth dataset were added and the effect dissolved, which is the result | none, it is done |
| **Repeated holdout** | Built and gated, never run | A robustness check that would support Chapter 1 rather than contradict it | one sweep on the four large datasets |
| **Bayesian tuning** | **Fixed and verified 2026-10-12.** Was silently broken: optuna-integration was missing. Now 16 of 16 tuning runs succeed | Ready for the tuning sweep | done |
| **Lab dataset upload** | Refused with an explanation | Needs the additive user-dataset hook B1 and B2 received | small |
| **Nothing committed to git** | Neither `pipeline-lab/` nor `pipeline-lab-engine/` | Per git-hygiene this is the user's call, never automatic | your decision |
| **Thesis positioning** | Lab results come from a broader design than the pre-registered B1/B2 arms | How they sit beside the frozen record is a supervisor conversation | a conversation |

### Known limitations, stated rather than fixed

- **OFAT cannot detect interactions.** A factorial follow-up would be
  needed, and is not feasible on this hardware.
- **Timings are machine-bound.** This is why the machine fingerprint,
  CPU, RAM and every library version are stored with each run.
- **These are public benchmark datasets.** A finding here is evidence
  about what usually happens, which is a good default and a poor
  guarantee.
- The B2 design notes still say B2 uploads append to `datasets/catalogue.csv`;
  it is actually `datasets/user_catalogue.csv`.

### Decisions already taken, for the record

These were resolved during the work and do not need revisiting unless
the user disagrees:

| Decision | Choice | Date |
|---|---|---|
| Evaluation protocol | k-fold k = 10 executes; split ratios recorded as declared metadata | 2026-10-09 |
| Post-hoc test | Friedman, then baseline-referenced Wilcoxon with Holm. Not Nemenyi, not Bonferroni | 2026-10-09 |
| Encoding | Promoted to a real sixth factor | 2026-10-09 |
| Engine separation | Third engine, so neither frozen repo is modified | 2026-10-09 |
| UI data access | Read engine `lab.db` directly, read-only. No copy, no sync | 2026-10-12 |
| UI refresh | Poll a cheap pulse endpoint, back off when idle | 2026-10-12 |
| Explanation style | Plain by default, expandable depth | 2026-10-12 |
| scipy in the dashboard | Added as a soft dependency for the Findings page | 2026-10-12 |

---

## 9. How to carry on

```bash
# Run a sweep (engine)
cd "ITRI671 Project/pipeline-lab-engine"
.venv/Scripts/python.exe run_experiment.py --config configs/<name>.yaml

# Read what it found, from the command line
PYTHONPATH=src .venv/Scripts/python.exe analyse.py --config <sweep-name>

# Or start the UI and read it there
cd "671 Research June/pipeline-lab" && start.bat
```

Tests: `pytest` in `pipeline-lab-engine/` (262) and
`pipeline-lab/backend/` (250). Two are environment-sensitive and are
documented above rather than hidden: a provenance timing test that fails
under parallel load, and B2 subprocess smoke tests that time out on a
memory-constrained machine.

The record is an ordinary SQLite database with one `runs` table, so any
SQL tool can read it directly.
