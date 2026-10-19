"""Re-run the climate_sim cells that the broken guard mishandled.

The deleted-class guard (fixed in 91043ee) let `drop_rows` on
climate_sim through at 15 and 30 per cent MAR, where listwise deletion
removes the entire 46-member minority class. Three models then crashed
inside sklearn and random_forest recorded accuracy 1.0 on a
single-class problem, which is the worse outcome because it looks like
a result.

These configs re-run only that dataset under the same seed and
settings, so the cells are recorded as skips with a stated reason. A
full sweep re-run would cost hours and change nothing else: every
other cell in those sweeps was scored correctly.

The config name is kept identical to the original so the rows land in
the same sweep. The record is append-only, so the old rows stay; the
analysis takes the most recent row per cell, which is how the earlier
duplicate was handled (5o).
"""
import pathlib
import re

CONFIGS = pathlib.Path(
    r"C:/Users/Colile/Documents/School/NWU/S1/ITRI671 Project/pipeline-lab-engine/configs"
)

HEADER = """# Re-run of the climate_sim cells in {name}.
#
# Written 2026-10-19. The deleted-class guard bug (PROCESS-LOG 5s,
# fixed in 91043ee) meant these four cells were recorded as three
# sklearn crashes and one false success at accuracy 1.0 on a
# single-class problem. With the guard fixed they are refused with a
# stated reason instead.
#
# Only climate_sim is listed; every other cell in the parent sweep was
# scored correctly and is not touched. The config NAME deliberately
# matches the parent sweep so the corrected rows join it, and the
# analysis takes the most recent row per cell.
"""

for tag in ["mar15", "mar30"]:
    name = f"wide_imputation_{tag}_s671"
    src = (CONFIGS / f"{name}.yaml").read_text(encoding="utf-8")
    body = "\n".join(l for l in src.splitlines() if l.strip() and not l.startswith("#"))
    body = re.sub(r"^datasets: \[.+\]$", "datasets: [climate_sim]", body, count=1, flags=re.M)
    out = CONFIGS / f"rerun_climate_sim_{tag}.yaml"
    out.write_text(HEADER.format(name=name) + body + "\n", encoding="utf-8")
    print("wrote", out.name)
    for line in body.splitlines():
        if line.startswith(("name:", "seed:", "datasets:", "techniques:")):
            print("   ", line)
