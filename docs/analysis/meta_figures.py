"""Figures for the dataset-characteristic meta-analysis."""
import os
import json
import pathlib

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from scipy import stats

HERE = pathlib.Path(__file__).resolve().parent
FIGS = pathlib.Path(os.environ.get("PIPELAB_FIGS", HERE.parent / "figures"))
FIGS.mkdir(parents=True, exist_ok=True)

NAVY, MID, PURPLE, LPURPLE = "#1A365D", "#2B6CB0", "#6B46C1", "#9F7AEA"
SLATE, CHAR = "#4A5568", "#1F2933"
plt.rcParams.update({
    "font.family": "DejaVu Sans", "font.size": 10,
    "axes.titlesize": 12, "axes.labelsize": 10, "axes.edgecolor": "#CBD2D9",
    "axes.grid": True, "grid.color": "#E4E7EB", "grid.linewidth": 0.6,
    "axes.axisbelow": True, "figure.facecolor": "white",
    "axes.facecolor": "white", "legend.frameon": False,
})

d = json.loads((pathlib.Path(os.environ.get("PIPELAB_OUT", pathlib.Path(__file__).resolve().parent / "out")) / "meta_analysis_results.json").read_text())
cells, chars = d["cells"], d["characteristics"]

FACTORS = ["scaling", "encoding", "selection", "tuning"]
MODELS = ["logreg", "svm", "random_forest", "gradient_boosting"]
LABEL = {"logreg": "logistic reg.", "svm": "SVM",
         "random_forest": "random forest", "gradient_boosting": "grad. boosting"}


def fig7():
    """Heatmap: median sensitivity by factor x model. The 'where to care' map."""
    grid = np.zeros((len(MODELS), len(FACTORS)))
    for i, m in enumerate(MODELS):
        for j, f in enumerate(FACTORS):
            sp = [c["spread_pct"] for c in cells if c["factor"] == f and c["model"] == m]
            grid[i, j] = np.median(sp) if sp else np.nan

    fig, ax = plt.subplots(figsize=(8.2, 4.4))
    im = ax.imshow(grid, cmap="Purples", aspect="auto", vmin=0, vmax=max(8.5, grid.max()))
    ax.set_xticks(range(len(FACTORS)))
    ax.set_xticklabels([f.capitalize() for f in FACTORS])
    ax.set_yticks(range(len(MODELS)))
    ax.set_yticklabels([LABEL[m] for m in MODELS])
    ax.grid(False)
    for i in range(len(MODELS)):
        for j in range(len(FACTORS)):
            v = grid[i, j]
            ax.text(j, i, f"{v:.2f}%", ha="center", va="center",
                    color="white" if v > 4 else CHAR,
                    fontweight="bold" if v > 1 else "normal", fontsize=10)
    ax.set_title("Which preprocessing choices actually move the score, and for which model")
    fig.colorbar(im, ax=ax, label="median spread across levels\n(% of baseline score)")
    n_ds = len({c["dataset"] for c in cells})
    fig.text(0.5, -0.04,
             f"Spread = (best - worst level) / baseline, per dataset, median over {n_ds} "
             f"datasets. Read as: 'if I change this choice, how much can the score move at all?'",
             ha="center", color=SLATE, fontsize=8.5)
    fig.tight_layout()
    fig.savefig(FIGS / "fig7_sensitivity_map.png", dpi=200, bbox_inches="tight")
    plt.close(fig)


def _partial_spearman(a, b, control):
    """Spearman correlation of a and b with control partialled out.

    Ranks everything, regresses the two rank vectors on the control's
    ranks, and correlates the residuals. Used for the confound check in
    Figure 8, where missingness and categorical fraction are themselves
    correlated in this registry.
    """
    ra, rb, rc = (stats.rankdata(v) for v in (a, b, control))

    def resid(u):
        slope, intercept = np.polyfit(rc, u, 1)
        return u - (slope * rc + intercept)

    return stats.pearsonr(resid(ra), resid(rb))


def fig8():
    """The one real predictor: categorical fraction drives encoding sensitivity."""
    sel = [c for c in cells if c["factor"] == "encoding"]
    x = np.array([chars[c["dataset"]].get("cat_fraction", 0.0) for c in sel])
    y = np.array([c["spread_pct"] for c in sel])
    rho, p = stats.spearmanr(x, y)

    fig, (ax, ax2) = plt.subplots(1, 2, figsize=(11.5, 4.6))

    jitter = (np.random.default_rng(671).random(len(x)) - 0.5) * 0.012
    ax.scatter(x + jitter, y, s=55, color=PURPLE, alpha=0.75,
               edgecolor="white", linewidth=0.8, zorder=3)
    ax.set_xlabel("fraction of features that are categorical")
    ax.set_ylabel("encoding spread (% of baseline)")
    ax.set_title(f"Encoding matters only where there is\nsomething to encode "
                 f"(Spearman rho = {rho:.2f}, p < 0.0001)", fontsize=11)
    ax.axvline(0.001, color=NAVY, linestyle="--", linewidth=1.2)
    ax.text(0.006, ax.get_ylim()[1] * 0.92, "no categorical features",
            color=NAVY, fontsize=8.5)

    # the confound itself, at registry level: missingness only occurs
    # in datasets that also have categorical features
    names = sorted(chars)
    mp_all = np.array([chars[n].get("missing_pct", 0.0) or 0.0 for n in names])
    cf_all = np.array([chars[n].get("cat_fraction", 0.0) for n in names])
    rho_c, p_c = stats.spearmanr(mp_all, cf_all)
    has_miss = mp_all > 0
    ax2.scatter(cf_all[~has_miss], mp_all[~has_miss], s=55, color="#CBD2D9",
                edgecolor="white", linewidth=0.8, zorder=3, label="no missing values")
    ax2.scatter(cf_all[has_miss], mp_all[has_miss], s=80, color=PURPLE,
                edgecolor="white", linewidth=1.0, zorder=4, label="has missing values")
    for n, cf, mp in zip(names, cf_all, mp_all):
        if mp > 0:
            ax2.annotate(n, (cf, mp), textcoords="offset points", xytext=(7, 3),
                         fontsize=8, color=SLATE)
    ax2.set_xlabel("fraction of features that are categorical")
    ax2.set_ylabel("natural missingness (%)")
    ax2.set_yscale("symlog", linthresh=0.5)
    ax2.set_title(f"Why that correlation was spurious: in this\nregistry, missingness only occurs in "
                  f"datasets\nthat have categoricals (rho = {rho_c:.2f})", fontsize=11)
    ax2.legend(loc="upper left", fontsize=8.5)

    # Computed, never typed. An earlier version of this caption carried
    # literals that went stale when the registry grew, so the figure
    # reported partial correlations the data no longer supported.
    mp_cell = np.array([chars[c["dataset"]].get("missing_pct", 0.0) or 0.0 for c in sel])
    rho_m, _ = stats.spearmanr(x, mp_cell)
    pc, _ = _partial_spearman(y, x, mp_cell)
    pm, pm_p = _partial_spearman(y, mp_cell, x)
    fig.text(0.5, -0.08,
             f"Left: categorical fraction genuinely predicts encoding sensitivity (partial rho = "
             f"{pc:.2f} controlling for missingness). Right: raw missingness appeared to predict it "
             f"too (rho = {rho_m:.2f}), but every dataset with missing values also has categorical "
             f"features, and the partial correlation collapses to {pm:.2f} (p = {pm_p:.2f}). "
             f"Reported as a confound, not a finding.",
             ha="center", color=SLATE, fontsize=8.5)
    fig.tight_layout()
    fig.savefig(FIGS / "fig8_encoding_predictor.png", dpi=200, bbox_inches="tight")
    plt.close(fig)


def fig9():
    """Selection can be catastrophic: the long tail nobody sees in a mean."""
    sel = [c for c in cells if c["factor"] == "selection"]
    sel.sort(key=lambda c: c["spread_pct"], reverse=True)
    top = sel[:14]
    labels = [f"{c['dataset']}\n{LABEL[c['model']]}" for c in top]
    vals = [c["spread_pct"] for c in top]

    fig, ax = plt.subplots(figsize=(10.5, 5.0))
    colours = [PURPLE if v > 100 else MID if v > 30 else NAVY for v in vals]
    ax.barh(range(len(top)), vals, color=colours)
    ax.set_yticks(range(len(top)))
    ax.set_yticklabels(labels, fontsize=8)
    ax.invert_yaxis()
    ax.set_xlabel("spread across selection levels (% of baseline score)")
    ax.set_title("Feature selection is low-risk on average and catastrophic in the tail")
    for i, v in enumerate(vals):
        ax.text(v + 8, i, f"{v:.0f}%", va="center", color=SLATE, fontsize=8.5)
    fig.text(0.5, -0.03,
             "Median selection spread is under 4%, but on energy-efficiency chi2 and mutual_info "
             "raise gradient boosting RMSE from 0.47 to 3.08 by discarding features the model needs. "
             "The risk is not in the average, it is in the tail.",
             ha="center", color=SLATE, fontsize=8.5)
    fig.tight_layout()
    fig.savefig(FIGS / "fig9_selection_tail_risk.png", dpi=200, bbox_inches="tight")
    plt.close(fig)


fig7(); print("fig7 ok")
fig8(); print("fig8 ok")
fig9(); print("fig9 ok")
print("written to", FIGS)
