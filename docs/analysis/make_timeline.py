"""Figure 5.1: planned assessment windows against dated evidence of work.

Every bar is sourced. Planned windows come from the module's
Continuous Assessment Plan (Rubrics/Assessment+Plan+ITRI671+VC+2026.pdf).
Actual windows come from evidence that carries its own date: the
dated chapter-draft filenames, the git histories of the three
artefact repositories, the signed ethics form and training
certificates, and the started_at column of the run record. Nothing is
estimated, so the figure can be checked against the files it names.
"""
import datetime as dt
import os
import pathlib

import matplotlib

matplotlib.use("Agg")
import matplotlib.dates as mdates
import matplotlib.pyplot as plt

FIGS = pathlib.Path(os.environ.get(
    "PIPELAB_FIGS",
    r"C:/Users/Colile/Documents/School/NWU/S1/ITRI671 Project/671 Research June/pipeline-lab/docs/figures",
))
FIGS.mkdir(parents=True, exist_ok=True)

NAVY, LIGHT, PURPLE, SLATE = "#1A365D", "#C9D6E8", "#6B46C1", "#4A5568"


def d(s):
    return dt.date.fromisoformat(s)


# (label, planned window or None, actual window or None, source of the actual dates)
ROWS = [
    ("Research proposal (Chapter 1)", ("2026-04-07", "2026-04-20"),
     ("2026-04-21", "2026-04-21"), "proposal file dated 21 April"),
    ("Ethics clearance", ("2026-03-30", "2026-03-30"),
     ("2026-08-30", "2026-08-31"), "TRREE certificates and signed form"),
    ("Chapters 2 and 3", ("2026-05-25", "2026-06-17"),
     ("2026-06-02", "2026-06-22"), "dated chapter drafts"),
    ("Iteration 1 artefact", None,
     ("2026-06-10", "2026-07-17"), "repository history"),
    ("Iteration 2 artefact", None,
     ("2026-07-02", "2026-10-08"), "repository history"),
    ("Chapter 4 (empirical study)", ("2026-08-17", "2026-09-14"),
     ("2026-07-03", "2026-07-03"), "dated chapter draft"),
    ("Pipeline Lab and experiments", None,
     ("2026-10-12", "2026-10-19"), "run record and repository history"),
    ("Final report (Chapters 1 to 5)", ("2026-10-05", "2026-10-19"),
     ("2026-10-17", "2026-10-19"), "dated report files"),
]


def main():
    fig, ax = plt.subplots(figsize=(10, 4.8))
    one_day = dt.timedelta(days=1)
    for i, (label, planned, actual, _src) in enumerate(ROWS):
        y = len(ROWS) - 1 - i
        if planned:
            a, b = d(planned[0]), d(planned[1])
            ax.barh(y + 0.18, (b - a + one_day).days, left=a, height=0.32,
                    color=LIGHT, edgecolor=NAVY, linewidth=0.6)
        if actual:
            a, b = d(actual[0]), d(actual[1])
            ax.barh(y - 0.18, (b - a + one_day).days, left=a, height=0.32,
                    color=NAVY)
    ax.set_yticks(range(len(ROWS)))
    ax.set_yticklabels([r[0] for r in reversed(ROWS)], fontsize=9)
    ax.xaxis.set_major_locator(mdates.MonthLocator())
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%b"))
    ax.set_xlim(d("2026-03-15"), d("2026-10-31"))
    ax.grid(axis="x", color="#E4E7EB", linewidth=0.6)
    ax.set_axisbelow(True)
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    ax.set_title("Planned assessment windows against dated evidence of the work",
                 fontsize=11, fontweight="bold")
    from matplotlib.patches import Patch
    ax.legend(handles=[Patch(facecolor=LIGHT, edgecolor=NAVY, label="planned (assessment plan)"),
                       Patch(facecolor=NAVY, label="actual (dated evidence)")],
              loc="lower left", fontsize=8.5, frameon=False)
    fig.text(0.5, -0.02,
             "Sources: Continuous Assessment Plan; dated chapter files; repository histories; "
             "signed ethics form and TRREE certificates; run record.",
             ha="center", color=SLATE, fontsize=8)
    fig.tight_layout()
    out = FIGS / "fig10_project_timeline.png"
    fig.savefig(out, dpi=200, bbox_inches="tight")
    plt.close(fig)
    print("written", out)


if __name__ == "__main__":
    main()
