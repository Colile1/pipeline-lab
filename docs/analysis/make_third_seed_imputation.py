"""Third seed for the nine-dataset imputation arm, matching the
scaling arm's three-seed design (671, 1337, 20260702).

Option 2 from the "what else can be done" discussion: the imputation
replication so far used two seeds (671, 1337) and found 35 per cent
reproduction. The scaling arm's own threshold result rests on three
seeds, which is the better-grounded design, because it measures a
rate across replications rather than a single pass/fail. This adds
the third draw at the same nine-dataset size as the original arm, so
it is directly comparable with 5l rather than with the widened arm
being tested separately.

Written but not launched immediately: the widened-imputation queue
(5o) is using the machine's cores, and starting this alongside it
would repeat that exact mistake. Launch after the queue clears.
"""
import pathlib
import re

CONFIGS = pathlib.Path(
    r"C:/Users/Colile/Documents/School/NWU/S1/ITRI671 Project/pipeline-lab-engine/configs"
)
SEED = 20260702
SWEEPS = ["mcar05", "mcar15", "mcar30", "mar05", "mar15", "mar30"]

HEADER = """# third_seed_imputation_{tag}: the {tag} injected imputation sweep,
# nine datasets (matching ofat_imputation_{tag} exactly), under a
# third random seed.
#
# Written 2026-10-18. The imputation replication (PROCESS-LOG 5l) used
# two seeds and found 35 per cent reproduction. The scaling arm's
# effect-size threshold rests on three seeds (671, 1337, 20260702),
# which measures a rate across replications rather than a single
# pass/fail. This sweep adds the third draw at the original
# nine-dataset size, so it is comparable with 5l rather than with the
# widened fourteen/eleven-dataset arm being tested separately.
#
# A separate config name keeps the three seeds from being pooled.
"""

for tag in SWEEPS:
    src = (CONFIGS / f"ofat_imputation_{tag}.yaml").read_text(encoding="utf-8")
    body = "\n".join(l for l in src.splitlines() if l.strip() and not l.startswith("#"))
    body = re.sub(r"^name: .*$", f"name: third_seed_imputation_{tag}", body, count=1, flags=re.M)
    body = re.sub(r"^seed: .*$", f"seed: {SEED}", body, count=1, flags=re.M)
    out = CONFIGS / f"third_seed_imputation_{tag}.yaml"
    out.write_text(HEADER.format(tag=tag) + body + "\n", encoding="utf-8")
    print("wrote", out.name)
