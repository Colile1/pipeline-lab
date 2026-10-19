"""Widen the imputation arm from 9 scored datasets per task to 14.

The imputation replication reproduced only 8 of 23 contrasts under a
second seed, and the diagnosis was the sample: nine datasets per task
against the scaling arm's sixteen. The direct test of that diagnosis
is to add datasets and run the replication again.

Seven registry entries qualify and are not yet in the arm. All are
complete (no natural NaN, so an injected rate stays truthful), have at
least two numeric columns, and are under 25,000 rows:

  classification: banknote, blood_transfusion, climate_sim, phoneme,
                  steel_plates
  regression:     house_16H, forest_fires

That takes classification from 9 to 14 and regression from 9 to 11.
forest_fires carries two categorical columns, so it is included for
regression on the same footing as the existing entries, which the
injector handles by blanking numeric cells only.

Both seeds are written at once: 671 to match the original design and
1337 for the replication, so the comparison is like for like.
"""
import pathlib
import re

CONFIGS = pathlib.Path(
    r"C:/Users/Colile/Documents/School/NWU/S1/ITRI671 Project/pipeline-lab-engine/configs"
)

ADD = [
    "banknote", "blood_transfusion", "climate_sim", "phoneme", "steel_plates",
    "house_16H", "forest_fires",
]

SWEEPS = [("mcar", 0.05), ("mcar", 0.15), ("mcar", 0.30),
          ("mar", 0.05), ("mar", 0.15), ("mar", 0.30)]

HEADER = """# Imputation at {pct}% injected {mech_up} missingness, widened registry,
# seed {seed}.
#
# Written 2026-10-18. The imputation replication (PROCESS-LOG 5l)
# reproduced 8 of 23 contrasts under a second seed, and attributed the
# instability to the sample: nine scored datasets per task against the
# scaling arm's sixteen. This sweep tests that diagnosis directly by
# adding the seven registry entries that qualify and were not already
# in the arm, taking classification to 14 and regression to 11.
#
# Added: banknote, blood_transfusion, climate_sim, phoneme,
# steel_plates (classification); house_16H, forest_fires (regression).
# All are complete, so an injected rate remains truthful, which is the
# same criterion that excluded heart-c, credit-approval, colic and
# autoMpg from the original sweeps.
#
# Both seeds are run so the widened arm can be replicated like for
# like. A separate config name keeps these from being pooled with the
# nine-dataset results, which measure a different thing.
"""


def main():
    src = (CONFIGS / "ofat_imputation_mcar15.yaml").read_text(encoding="utf-8")
    base = [l for l in src.splitlines() if l.strip() and not l.startswith("#")]
    body = "\n".join(base)

    existing = re.search(r"^datasets: \[(.+)\]$", body, re.M).group(1)
    datasets = [d.strip() for d in existing.split(",")]
    widened = datasets + [d for d in ADD if d not in datasets]

    written = []
    for mech, rate in SWEEPS:
        for seed in (671, 1337):
            tag = f"{mech}{int(rate * 100):02d}"
            name = f"wide_imputation_{tag}_s{seed}"
            text = body
            text = re.sub(r"^name: .*$", f"name: {name}", text, count=1, flags=re.M)
            text = re.sub(r"^seed: .*$", f"seed: {seed}", text, count=1, flags=re.M)
            text = re.sub(r"^datasets: \[.+\]$",
                          "datasets: [" + ", ".join(widened) + "]",
                          text, count=1, flags=re.M)
            text = re.sub(r"^  rate: .*$", f"  rate: {rate}", text, count=1, flags=re.M)
            text = re.sub(r"^  mechanism: .*$", f"  mechanism: {mech}",
                          text, count=1, flags=re.M)
            head = HEADER.format(pct=int(rate * 100), mech_up=mech.upper(), seed=seed)
            out = CONFIGS / f"{name}.yaml"
            out.write_text(head + text + "\n", encoding="utf-8")
            written.append(out.name)

    print(f"datasets per sweep: {len(widened)}")
    print(f"added: {[d for d in ADD if d not in datasets]}")
    for w in written:
        print("  wrote", w)


if __name__ == "__main__":
    main()
