# Scope decisions — resolved against your own March 2026 sources

Updated 2026-10-09 after reading the documents you pointed me at:

- `ITRI671 Project/31 Maarch analysis/Chapter_1_Colile.docx` (31 Mar, 64KB)
- `ITRI671 Project/31 Maarch analysis/methodology_analysis_Colile.docx` (31 Mar, 73KB)
- `ITRI671 Project/30 March/research_proposal_rewritten_Colile.docx`
- `671 Research June/research proposal Colile 21 April .docx`

These are more specific than the April proposal and they **already
decide** most of what I had listed as open. Where that happened I have
recorded your own documented choice rather than re-asking.

---

## Your methodology analysis already selected these

From `methodology_analysis_Colile.docx` §2, "Overview of Methodological
Dimensions" — your selected approach, with reasons given in the body:

| Dimension | Your selected approach |
|---|---|
| Research design | Controlled experiment |
| Experimental design | **OFAT with systematic variation** |
| Dataset selection | Diverse benchmark suite (OpenML / UCI) |
| Evaluation protocol | **Stratified k-fold CV, k = 10** |
| Statistical testing | Friedman + Wilcoxon post-hoc, Bonferroni |
| Performance metrics | **Accuracy + F1 (classification); RMSE (regression)** |
| Analytical approach | Two-stage: statistical comparison, then mechanistic explanation |

---

## Decision 1 — the 70/15/15 split ⚠ CONFLICTS WITH YOUR OWN CHAPTER 1

This needs your attention, because what you asked me for contradicts a
choice you made and justified in writing.

`methodology_analysis_Colile.docx` §6.1 considers the train-test split
and **rejects it**, in your own words:

> "A single train-test split produces a performance estimate that is
> sensitive to the particular partition chosen... there is no basis for
> assessing the variance of the performance estimate, which means the
> comparison between pipeline configurations rests on a single,
> potentially unrepresentative measurement."
>
> **Lesson for this research:** "A single train-test split is
> insufficient for a study that aims to produce statistically reliable
> comparisons. Performance estimates must be replicated across multiple
> data partitions."

Cited support: Lones et al. (2024) on misleading ML evaluations; Arlot
and Celisse (2010) on CV bias/variance. §6.3 then selects stratified
k-fold at **k = 10**.

So a 70/15/15 split is not a missing feature — it is an approach your
methodology chapter examined and ruled out with citations. Building it
as the primary evaluation path would put the artefact in direct conflict
with Chapter 1, and any results from it would be hard to defend in the
same thesis.

**What the plan does instead (unchanged from the earlier decision, now
better justified):** k-fold CV at k=10 is what runs. The split ratios
are still *recorded* on every run as requested — `split_train`,
`split_val`, `split_test`, user-editable, defaulting to 70/15/15 — with
`split_applied = false` and a `split_note` citing the §6.1 rationale.
That way the field exists for your trend analysis and the UI honours
your request, while nothing fabricates a validation metric that no run
computed.

**Three ways forward — your call:**

- **A (recommended): keep k-fold as the real protocol**, record split
  ratios as declared-but-not-applied metadata. Consistent with Chapter 1.
- **B: add a genuine repeated holdout as a *secondary*, clearly-labelled
  protocol** (e.g. 30 random 70/15/15 splits, reporting mean ± sd). This
  answers §6.1's actual objection — the objection was to a *single*
  split, not to holdout as such — so it could be defended as a
  robustness check alongside k-fold rather than instead of it. More work,
  but methodologically honest and genuinely new evidence.
- **C: single 70/15/15 split as the primary protocol.** Does exactly what
  you asked, but contradicts your own §6.1 and its citations. I would
  want you to confirm explicitly, in writing, before building this.

---

## Decision 2 — extra model metrics ✔ RESOLVED: match your methodology

`methodology_analysis_Colile.docx` §2 selects
"task-appropriate multi-metric selection" and names it precisely:
**accuracy and F1-score for classification, RMSE for regression** —
the same set both existing engines already compute. §9 of that document
argues the choice (accuracy alone is misleading under class imbalance;
F1 covers it; RMSE for regression).

So the earlier "Option B: add precision/recall/ROC-AUC" would have
departed from a documented decision. **The plan now records exactly your
selected metrics**, plus — and this is additive, not a methodology
change — the **standard deviation across folds** for each, and
`n_features_in` / `n_features_selected`. Those are properties of the
k-fold run you already specified, not new metrics.

If you *do* want ROC-AUC etc. for richer trends, that is a deliberate
amendment to §9 and should be noted as such in the chapter. Say the word
and I will add them behind a clearly-labelled "beyond the registered
metric set" flag.

---

## Decision 3 — sweep scale ✔ RESOLVED: OFAT, as you selected

`methodology_analysis_Colile.docx` §2 selects **"OFAT with systematic
variation"** over full factorial and over search-based/AutoML. §4 of that
document argues it: full factorial across five components is
combinatorially infeasible and confounds attribution, while OFAT
isolates each component's effect against a fixed baseline.

`Chapter_1_Colile.docx` §1.7.3 goes further and specifies the artefact's
own interface in these terms: *"running an experiment will involve
specifying the component to vary, the technique options to evaluate, the
baseline configuration for all other components, and the dataset
collection to use."*

**That is a direct specification of the composer UI.** The card grid in
`PLAN.md` implements exactly it: the baseline column is the fixed
configuration, and each additional column varies one component against
it. Full factorial stays technically possible but is behind an explicit
cost confirmation, and OFAT is the default — matching your design rather
than overriding it.

For reference, the infeasibility is real on this machine: full factorial
is 4 scaling × 4 imputation × 5 selection × 4 model × 4 tuning × ~17
datasets ≈ **21,760 runs**, on hardware that has already hit 0 bytes
free disk and runs at ~2 GB free RAM. OFAT per component is roughly
17 datasets × 4 models × 4 techniques ≈ **272 runs** per component
sweep — about 1,400 runs for all five components, which is feasible.

---

## Baselines — now specified, from Chapter 1's own table

`Chapter_1_Colile.docx` names the baseline for each component explicitly
(the April version did not). The composer's "baseline" column is
pre-filled with these:

| Component | Baseline (per your Chapter 1) | Other candidates |
|---|---|---|
| Feature scaling | **No scaling** | Standard, MinMax, Robust |
| Missing value imputation | **Row deletion** | mean, median, KNN |
| Feature selection | **No selection** | Chi-square, mutual info, RFE, LASSO |
| Model type | (no baseline — all four compared) | logreg, RF, SVM, GB |
| Hyperparameter tuning | **No tuning** | random search, grid search, Bayesian |

Note two differences from the current B1/B2 artefacts, both of which the
new engine must implement:
- **Row deletion is the imputation baseline**, not an afterthought.
  Neither existing engine implements it at all.
- **k = 10**, matching your methodology, not prepfx's k=5 arms.

---

## Dataset collection — expanded per Chapter 1

`Chapter_1_Colile.docx` §1.7.2 specifies **15–20 datasets** (the current
artefacts have 24 for B1 and 12 for B2), selected by pre-specified
criteria: domain variety; a mix of **binary classification, multi-class
classification, and regression**; a range of sample sizes and
dimensionalities; missing values present in at least a subset; varying
class imbalance. Sources restricted to UCI and OpenML; no proprietary or
synthetic data.

The existing B2 catalogue (12 datasets, characterised) and B1 registry
(24) already satisfy most of these criteria and are reusable as the
starting collection — worth confirming against the criteria rather than
re-selecting from scratch.

---

## Still genuinely open (not blocking step 1)

- **Optuna** is not installed in either `.venv`. Bayesian optimisation
  needs it in the new engine's own environment. Grid and random search
  need nothing new (sklearn 1.9.0 has both).
- **Categorical encoding** is a pipeline stage in your §1.2.1 prose but
  is *not* one of the five components in either Chapter 1's or the April
  proposal's comparison table, and both engines hardcode OneHot. The plan
  keeps it as a grid row with OneHot as the only option, so it is visible
  but not silently treated as a sixth experimental factor. Add
  ordinal/target encoding as options if you want it varied.
- **Statistical testing.** Your methodology selects Friedman + Wilcoxon
  post-hoc with **Bonferroni** correction. Both existing engines
  implement Friedman + Nemenyi instead (prepfx's `friedman.py`). Worth
  deciding whether the new engine follows your Chapter 1 (Bonferroni) or
  the existing artefacts (Nemenyi) — they give different post-hoc
  results, and the chapters already report Nemenyi-based CDs.
- **Thesis positioning.** This engine implements the *original* five-
  component design, which is broader than the two-factor arms already
  written up. How its results sit alongside the frozen B1/B2 record is a
  supervisor conversation.
