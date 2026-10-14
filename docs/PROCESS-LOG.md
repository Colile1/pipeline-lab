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
