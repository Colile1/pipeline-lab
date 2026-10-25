"""Master figures for the Pipeline Lab programme.

House palette (plain-material-ui / NWU deck style): deep blue is the
baseline or reference series, purple is the result being argued for,
slate for muted labels. No decorative colour.
"""
import os
import json
import pathlib
import sqlite3
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

DB = os.environ.get("PIPELAB_DB", r"C:/Users/Colile/Documents/School/NWU/S1/ITRI671 Project/pipeline-lab-engine/outputs/lab.db")
SCRATCH = pathlib.Path(os.environ.get("PIPELAB_OUT", pathlib.Path(__file__).resolve().parent / "out"))
SCRATCH.mkdir(parents=True, exist_ok=True)
FIGS = pathlib.Path(os.environ.get("PIPELAB_FIGS", r"C:/Users/Colile/Documents/School/NWU/S1/ITRI671 Project/671 Research June/pipeline-lab/docs/figures"))
FIGS.mkdir(parents=True, exist_ok=True)

NAVY, MID, PURPLE, LPURPLE = "#1A365D", "#2B6CB0", "#6B46C1", "#9F7AEA"
SLATE, CHAR, TINT = "#4A5568", "#1F2933", "#F5F0FF"

plt.rcParams.update({
    "font.family": "DejaVu Sans", "font.size": 10,
    "axes.titlesize": 12, "axes.titleweight": "semibold",
    "axes.labelsize": 10, "axes.edgecolor": "#CBD2D9",
    "axes.grid": True, "grid.color": "#E4E7EB", "grid.linewidth": 0.6,
    "axes.axisbelow": True, "figure.facecolor": "white",
    "axes.facecolor": "white", "legend.frameon": False,
})

res = json.loads((SCRATCH / "master_results.json").read_text())
resdr = json.loads((SCRATCH / "master_results_droprows.json").read_text())


# ---- Figure 1: the whole programme, effect vs significance ------------
def fig1():
    """Every tested cell: how many cleared the global test, by factor."""
    factors = ["scaling", "encoding", "imputation", "selection", "tuning"]
    tested, sig = [], []
    for f in factors:
        cells = [e for e in res if e["vary"] == f]
        tested.append(len(cells))
        sig.append(sum(1 for e in cells if e["significant"]))

    fig, ax = plt.subplots(figsize=(9, 4.6))
    x = np.arange(len(factors))
    ax.bar(x, tested, 0.58, label="cells tested", color=NAVY)
    ax.bar(x, sig, 0.58, label="global test significant", color=PURPLE)
    for i, (t, s) in enumerate(zip(tested, sig)):
        ax.text(i, t + 0.8, str(t), ha="center", color=SLATE, fontsize=9)
        if s:
            ax.text(i, s / 2, str(s), ha="center", color="white",
                    fontsize=9, fontweight="bold")
    ax.set_xticks(x)
    ax.set_xticklabels([f.capitalize() for f in factors])
    ax.set_ylabel("(model x metric x sweep) cells")
    ax.set_title("Where the five factors actually produced a detectable effect")
    ax.legend(loc="upper right")
    fig.text(0.5, -0.02,
             "Each cell is one model, one metric, one sweep, tested with Friedman at alpha = 0.05. "
             "Imputation dominates because it was swept at six injected missingness settings.",
             ha="center", color=SLATE, fontsize=8.5)
    fig.tight_layout()
    fig.savefig(FIGS / "fig1_effects_by_factor.png", dpi=200, bbox_inches="tight")
    plt.close(fig)


def _fig2_caption_facts():
    """Return (dataset count, SVM standard-vs-none Holm p) for the caption.

    Computed from the record so the caption cannot drift away from the
    result it describes, which is what happened when it was a literal.
    """
    import sys
    sys.path.insert(0, os.environ.get("PIPELAB_ENGINE_SRC", r"C:/Users/Colile/Documents/School/NWU/S1/ITRI671 Project/pipeline-lab-engine/src"))
    from piplab.statistics.tests import compare_levels

    conn = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
    rows = conn.execute("""
        select dataset, scaling, accuracy_mean from runs
        where config_name='ofat_scaling_v2' and status='succeeded'
          and task_type='classification' and accuracy_mean is not null
          and model='svm'""").fetchall()
    conn.close()
    table = {}
    for d, lv, v in rows:
        table.setdefault(d, {})[lv] = v
    levels = sorted({lv for v in table.values() for lv in v})
    complete = {d: v for d, v in table.items() if len(v) == len(levels)}
    datasets = sorted(complete)
    scores = {lv: [complete[d][lv] for d in datasets] for lv in levels}
    res = compare_levels(scores, "none", higher_is_better=True)
    p = next(c.p_adjusted for c in res.comparisons if c.level == "standard")
    return len(datasets), p


# ---- Figure 2: scaling, the model-dependence headline -----------------
def fig2():
    """Scaling effect per model: SVM and logreg move, trees do not."""
    conn = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
    rows = conn.execute("""
        select model, scaling, avg(accuracy_mean) from runs
        where config_name='ofat_scaling_v2' and status='succeeded'
          and task_type='classification' and accuracy_mean is not null
        group by model, scaling""").fetchall()
    conn.close()
    data = {}
    for m, s, v in rows:
        data.setdefault(m, {})[s] = v
    models = ["logreg", "svm", "random_forest", "gradient_boosting"]
    levels = ["none", "standard", "minmax", "robust"]
    colours = {"none": NAVY, "standard": PURPLE, "minmax": LPURPLE, "robust": MID}

    fig, ax = plt.subplots(figsize=(9, 4.6))
    w, x = 0.2, np.arange(len(models))
    for i, lv in enumerate(levels):
        vals = [data[m][lv] for m in models]
        ax.bar(x + (i - 1.5) * w, vals, w, label=lv, color=colours[lv])
    ax.set_xticks(x)
    ax.set_xticklabels(["Logistic\nregression", "SVM", "Random\nforest", "Gradient\nboosting"])
    ax.set_ylabel("mean accuracy across datasets")
    # Fit the axis to the bars with a margin. A hardcoded ceiling of 0.9
    # clipped the SVM and random forest bars once the registry grew, so
    # the figure could not show the effect it exists to show.
    allv = [data[m][lv] for m in models for lv in levels]
    lo, hi = min(allv), max(allv)
    pad = (hi - lo) * 0.25 or 0.01
    ax.set_ylim(max(0.0, lo - pad), min(1.0, hi + pad))
    ax.set_title("Scaling: the effect is a property of the model, not the pipeline")
    ax.legend(ncol=4, loc="upper center", bbox_to_anchor=(0.5, -0.12))
    # The caption states the tested result, so it is computed rather
    # than typed. A hardcoded caption survived the registry growth and
    # went on asserting a superseded finding against refreshed data.
    n_ds, svm_gain = _fig2_caption_facts()
    fig.text(0.5, -0.09,
             f"ofat_scaling_v2, {n_ds} classification datasets. The support vector machine is "
             f"the only model with Holm-rejected gains (standard vs none, Holm = "
             f"{svm_gain:.4f}). The two tree ensembles return identical scores in most cells.",
             ha="center", color=SLATE, fontsize=8.5)
    fig.tight_layout()
    fig.savefig(FIGS / "fig2_scaling_by_model.png", dpi=200, bbox_inches="tight")
    plt.close(fig)


# ---- Figure 3: imputation, the two questions give two answers ---------
def fig3():
    """knn vs mean across rate and mechanism, classification and regression."""
    sweeps = [("mcar05", "MCAR 5%"), ("mcar15", "MCAR 15%"), ("mcar30", "MCAR 30%"),
              ("mar05", "MAR 5%"), ("mar15", "MAR 15%"), ("mar30", "MAR 30%")]
    fig, axes = plt.subplots(1, 2, figsize=(11, 4.4))
    for ax, (metric, title, better) in zip(
        axes, [("accuracy_mean", "Classification (accuracy)", "higher"),
               ("rmse_mean", "Regression (RMSE)", "lower")]):
        models = ["logreg", "svm", "random_forest", "gradient_boosting"]
        grid = np.full((len(models), len(sweeps)), np.nan)
        for j, (key, _) in enumerate(sweeps):
            cfg = f"ofat_imputation_{key}"
            for i, m in enumerate(models):
                cell = next((e for e in res if e["config"] == cfg and e["model"] == m
                             and e["metric"] == metric), None)
                if not cell:
                    continue
                c = next((c for c in cell["comparisons"] if c["level"] == "knn"), None)
                # signed -log10 p: positive when knn rejected and better
                if c and c["rejected"]:
                    grid[i, j] = 1.0 if c["n_improved"] > c["n_pairs"] / 2 else -1.0
                else:
                    grid[i, j] = 0.0
        cmap = matplotlib.colors.ListedColormap(["#C05621", "#EDF2F7", PURPLE])
        ax.imshow(grid, cmap=cmap, vmin=-1, vmax=1, aspect="auto")
        ax.set_xticks(range(len(sweeps)))
        ax.set_xticklabels([s[1] for s in sweeps], rotation=45, ha="right", fontsize=8.5)
        ax.set_yticks(range(len(models)))
        ax.set_yticklabels(["logreg", "SVM", "rand. forest", "grad. boost"], fontsize=9)
        ax.set_title(title, fontsize=11)
        ax.grid(False)
        for i in range(len(models)):
            for j in range(len(sweeps)):
                if grid[i, j] == 1.0:
                    ax.text(j, i, "+", ha="center", va="center",
                            color="white", fontweight="bold")
    fig.suptitle("kNN imputation against mean: where it is actually rejected",
                 fontsize=12, fontweight="semibold", y=1.02)
    fig.text(0.5, -0.14,
             "Purple + = kNN significantly better than mean after Holm. Grey = no licensed difference. "
             "9 datasets per cell. Imputer choice matters only where missingness is heavy and controlled.",
             ha="center", color=SLATE, fontsize=8.5)
    fig.tight_layout()
    fig.savefig(FIGS / "fig3_imputation_knn_vs_mean.png", dpi=200, bbox_inches="tight")
    plt.close(fig)


# ---- Figure 4: the drop_rows artefact ---------------------------------
def fig4():
    """drop_rows 'wins' on regression only because it is scored on fewer rows."""
    conn = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
    rows = conn.execute("""
        select dataset, imputation, rmse_mean, n_rows, n_rows_before_deletion
        from runs where config_name='ofat_imputation_mcar15' and model='logreg'
          and task_type='regression' and status='succeeded'
        order by dataset""").fetchall()
    conn.close()
    ds = sorted({r[0] for r in rows})
    keep_pct, ratio = [], []
    for d in ds:
        dr = next(r for r in rows if r[0] == d and r[1] == "drop_rows")
        mn = next(r for r in rows if r[0] == d and r[1] == "mean")
        keep_pct.append(100.0 * dr[3] / dr[4])
        ratio.append(dr[2] / mn[2])

    fig, ax = plt.subplots(figsize=(9, 4.8))
    ax.scatter(keep_pct, ratio, s=90, color=PURPLE, zorder=3, edgecolor="white", linewidth=1.2)
    for d, x, y in zip(ds, keep_pct, ratio):
        ax.annotate(d, (x, y), textcoords="offset points", xytext=(6, 5),
                    fontsize=8, color=SLATE)
    ax.axhline(1.0, color=NAVY, linewidth=1.4, linestyle="--")
    ax.text(ax.get_xlim()[1], 1.005, "equal RMSE", ha="right", va="bottom",
            color=NAVY, fontsize=8.5)
    ax.set_xlabel("rows drop_rows kept (% of the dataset)")
    ax.set_ylabel("drop_rows RMSE / mean-imputation RMSE")
    ax.set_title("Why 'deleting beats imputing' on regression is an artefact, not a finding")
    fig.text(0.5, -0.04,
             "MCAR 15%, logistic/linear regression. The fewer rows drop_rows keeps, the better its RMSE looks: "
             "it is scored on an easy complete-case remnant (bodyfat: 38 of 252 rows), not on the same test data.",
             ha="center", color=SLATE, fontsize=8.5)
    fig.tight_layout()
    fig.savefig(FIGS / "fig4_droprows_artefact.png", dpi=200, bbox_inches="tight")
    plt.close(fig)


# ---- Figure 5: tuning, cost against benefit ---------------------------
def fig5():
    """Tuning on large datasets: gradient boosting is the only real gain."""
    conn = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
    rows = conn.execute("""
        select dataset, model, tuning, f1_mean, rmse_mean from runs
        where config_name='ofat_tuning_large' and status='succeeded'""").fetchall()
    conn.close()
    pairs = [("adult", "f1"), ("bank-marketing", "f1"), ("house_16H", "rmse")]
    models = ["logreg", "random_forest", "gradient_boosting"]
    levels = ["grid", "random", "bayesian"]
    fig, axes = plt.subplots(1, 3, figsize=(12, 4.2), sharey=True)
    for ax, (dset, kind) in zip(axes, pairs):
        idx = 3 if kind == "f1" else 4
        base = {m: next((r[idx] for r in rows if r[0] == dset and r[1] == m
                         and r[2] == "none"), None) for m in models}
        w, x = 0.25, np.arange(len(models))
        for i, lv in enumerate(levels):
            gains = []
            for m in models:
                v = next((r[idx] for r in rows if r[0] == dset and r[1] == m
                          and r[2] == lv), None)
                b = base[m]
                if v is None or b is None:
                    gains.append(0.0)
                elif kind == "f1":
                    gains.append(100.0 * (v - b))          # percentage points
                else:
                    gains.append(100.0 * (b - v) / b)      # % RMSE reduction
            ax.bar(x + (i - 1) * w, gains, w, label=lv,
                   color=[NAVY, MID, PURPLE][i])
        ax.axhline(0, color=CHAR, linewidth=1)
        ax.set_xticks(x)
        ax.set_xticklabels(["logreg", "rand.\nforest", "grad.\nboost"], fontsize=9)
        ax.set_title(f"{dset}\n({'F1 points gained' if kind=='f1' else '% RMSE reduced'})",
                     fontsize=10.5)
    axes[0].set_ylabel("improvement over no tuning")
    axes[-1].legend(title="search", loc="upper left", fontsize=9)
    fig.suptitle("Tuning on the three large datasets: one model benefits, two barely move",
                 fontsize=12, fontweight="semibold", y=1.03)
    fig.text(0.5, -0.06,
             "ofat_tuning_large, ~30 hours of compute. Logistic regression on house_16H is absent: "
             "LinearRegression has no hyperparameter to search, so those runs were correctly skipped.",
             ha="center", color=SLATE, fontsize=8.5)
    fig.tight_layout()
    fig.savefig(FIGS / "fig5_tuning_cost_benefit.png", dpi=200, bbox_inches="tight")
    plt.close(fig)


# ---- Figure 6: protocol agreement -------------------------------------
def fig6():
    """Repeated holdout reproduces k-fold on the same datasets."""
    conn = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
    kf = conn.execute("""
        select dataset, model, scaling, accuracy_mean, rmse_mean from runs
        where config_name in ('ofat_scaling_large','ofat_scaling_v2')
          and status='succeeded'""").fetchall()
    ho = conn.execute("""
        select dataset, model, scaling, accuracy_mean, rmse_mean from runs
        where config_name='holdout_large' and status='succeeded'""").fetchall()
    conn.close()
    xs, ys, labels = [], [], []
    for d, m, s, acc, rmse in ho:
        match = next((r for r in kf if r[0] == d and r[1] == m and r[2] == s), None)
        if not match:
            continue
        a, b = (acc, match[3]) if acc is not None else (rmse, match[4])
        if a is None or b is None:
            continue
        # normalise regression onto a comparable 0-1 scale by ratio
        if acc is None:
            a, b = 1.0, b / a if a else None
            continue
        xs.append(b); ys.append(a); labels.append(f"{d}/{m}")

    fig, ax = plt.subplots(figsize=(6.4, 6.0))
    lo = min(xs + ys) - 0.01; hi = max(xs + ys) + 0.01
    ax.plot([lo, hi], [lo, hi], color=NAVY, linestyle="--", linewidth=1.4,
            label="perfect agreement")
    ax.scatter(xs, ys, s=70, color=PURPLE, edgecolor="white", linewidth=1.1, zorder=3)
    ax.set_xlim(lo, hi); ax.set_ylim(lo, hi)
    ax.set_xlabel("accuracy under 10-fold cross-validation")
    ax.set_ylabel("accuracy under 30x repeated 70/15/15 holdout")
    ax.set_title("The scaling result does not depend on the\nevaluation protocol")
    ax.legend(loc="upper left")
    fig.text(0.5, -0.03,
             "Each point is one (dataset, model, scaler) cell measured under both protocols, "
             "on adult and bank-marketing. Points on the line agree.",
             ha="center", color=SLATE, fontsize=8.5)
    fig.tight_layout()
    fig.savefig(FIGS / "fig6_protocol_agreement.png", dpi=200, bbox_inches="tight")
    plt.close(fig)
    return len(xs)


fig1(); print("fig1 ok")
fig2(); print("fig2 ok")
fig3(); print("fig3 ok")
fig4(); print("fig4 ok")
fig5(); print("fig5 ok")
n6 = fig6(); print(f"fig6 ok ({n6} paired cells)")
print("\nwritten to", FIGS)
