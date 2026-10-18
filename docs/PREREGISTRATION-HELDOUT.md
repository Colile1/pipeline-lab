# Pre-registration: held-out confirmation of the scaling result

**Written 18 October 2026, before any of the datasets named below had
been scored on this arm.** Colile Sibanda, ITRI671, North-West
University.

This document exists to make one test falsifiable. Every finding in
the study so far was produced on a registry that grew while the study
ran, and datasets were added partly in response to what earlier
results showed. That is defensible for exploratory work and it is
documented in the process log, but it means no result so far is a
clean confirmation: the data that produced a hypothesis cannot also
test it.

The prediction, the datasets, the procedure and the decision rule are
all fixed here in advance. The test is run once. Whatever it returns
is reported.

---

## 1. The prediction

**Standard scaling improves support vector machine classification
accuracy relative to no scaling, on datasets this study has never
used.**

Stated so it can fail:

- **Primary:** the Wilcoxon signed-rank test of standard scaling
  against no scaling, on SVM accuracy across the held-out datasets,
  returns a one-sided p-value below 0.05 in favour of standard
  scaling.
- **Secondary, directional:** standard scaling wins on at least 4 of
  the 5 held-out datasets.
- **Falsified if:** the direction reverses, or the win count is 2 or
  fewer.

The prediction follows from the study's strongest existing result:
SVM standard-vs-none at Holm 0.0071 on 16 datasets, with a bootstrap
interval of +0.0036 to +0.1082 that excludes zero. It also follows
from theory, since the radial basis kernel depends on Euclidean
distances that unequal feature scales distort.

## 2. The tree-ensemble control

A second prediction is registered to show the test can distinguish a
real effect from a procedure that always finds one:

**Random forest accuracy does not change materially with scaling on
the same held-out datasets**, with no significant Wilcoxon result and
most datasets returning exactly identical scores.

If the SVM prediction holds and the control also "holds" in the sense
of showing an effect, the instrument is suspect rather than the
theory.

## 3. The held-out datasets

Five OpenML classification datasets, none registered in this engine at
any point, none scored on any arm, and none inspected before this
document was written. They were chosen on three criteria only:
complete (no missing values), entirely numeric, and binary or
multi-class with at least 300 rows.

| name | OpenML id | why it qualifies |
|---|---|---|
| diabetes_sylva | 41945 | numeric, complete, moderate size |
| mozilla4 | 1046 | numeric, complete, 15,545 rows |
| eeg-eye-state | 1471 | numeric, complete, 14,980 rows |
| wall-robot-nav | 1497 | numeric, complete, multi-class |
| kc1 | 1067 | numeric, complete, software defect data |

Any dataset that fails to load, turns out to carry missing values, or
turns out to be already registered under another name is dropped and
reported as dropped. It is **not** replaced, because choosing a
replacement after seeing the others would reintroduce the problem this
document exists to prevent.

## 4. Procedure, fixed in advance

- Levels: `none` (baseline) and `standard` only. The other scalers are
  not part of this prediction and are not tested, so no multiplicity
  correction is required and none will be applied.
- Models: `svm` (the prediction) and `random_forest` (the control).
- Protocol: stratified 10-fold cross-validation, seed 671, matching
  the main study exactly.
- Metric: accuracy.
- Test: Wilcoxon signed-rank over datasets, one-sided, alpha = 0.05.
- Effect size: median difference with a bootstrap confidence interval,
  as elsewhere in the study.

## 5. What will be reported

The result, whichever way it falls, in the report's results chapter
and in the process log. Specifically:

- If the prediction holds, it is reported as a confirmation on data
  that played no part in generating the hypothesis, which is the
  strongest claim this study will be able to make.
- If it fails, it is reported as a failure to confirm, and the scaling
  result is restated as registry-dependent. The existing 16-dataset
  result is not withdrawn, because it stands on its own evidence, but
  its generality is then openly in question.
- If some datasets drop out, the reduced sample size is stated and the
  test is run on what remains, with the loss of power acknowledged.

Five datasets is a small sample and the test is correspondingly weak:
the smallest attainable one-sided Wilcoxon p-value at n = 5 is 0.031,
so the prediction can only just reach significance even if every
dataset agrees. This is stated here in advance so that a narrow miss
is not later presented as a success, nor a narrow pass as decisive.
