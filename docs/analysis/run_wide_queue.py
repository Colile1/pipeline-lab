"""Run the widened imputation sweeps one after another.

Twelve sweeps, six missingness settings under two seeds. They are run
sequentially rather than in parallel: the engine already uses several
cores per run, so running sweeps alongside each other would contend
for the same cores and make the recorded wall_seconds meaningless as
a cost measure.

Each sweep is skipped if the record already holds its full 400 runs,
so the queue can be restarted after an interruption without
duplicating work. Progress is printed with timings and a running
total, and a failure in one sweep does not stop the rest.
"""
import datetime
import pathlib
import sqlite3
import subprocess
import sys

ENGINE = pathlib.Path(
    r"C:/Users/Colile/Documents/School/NWU/S1/ITRI671 Project/pipeline-lab-engine"
)
PY = ENGINE / ".venv" / "Scripts" / "python.exe"
DB = ENGINE / "outputs" / "lab.db"
EXPECTED = 400  # 25 datasets x 4 techniques x 4 models

SWEEPS = [
    f"wide_imputation_{mech}{pct:02d}_s{seed}"
    for mech in ("mcar", "mar")
    for pct in (5, 15, 30)
    for seed in (671, 1337)
]


def done(name):
    """How many runs the record already holds for this sweep."""
    if not DB.exists():
        return 0
    with sqlite3.connect(f"file:{DB}?mode=ro", uri=True) as conn:
        return conn.execute(
            "select count(*) from runs where config_name = ?", (name,)
        ).fetchone()[0]


def main():
    started = datetime.datetime.now()
    print(f"queue of {len(SWEEPS)} sweeps, started {started:%H:%M:%S}", flush=True)
    for i, name in enumerate(SWEEPS, 1):
        have = done(name)
        if have >= EXPECTED:
            print(f"[{i}/{len(SWEEPS)}] {name}: already complete ({have}), skipping",
                  flush=True)
            continue
        cfg = ENGINE / "configs" / f"{name}.yaml"
        if not cfg.is_file():
            print(f"[{i}/{len(SWEEPS)}] {name}: NO CONFIG at {cfg}, skipping", flush=True)
            continue
        t0 = datetime.datetime.now()
        print(f"[{i}/{len(SWEEPS)}] {name}: starting at {t0:%H:%M:%S} "
              f"(have {have})", flush=True)
        result = subprocess.run(
            [str(PY), "-u", "run_experiment.py", "--config", f"configs/{name}.yaml"],
            cwd=str(ENGINE), capture_output=True, text=True,
        )
        mins = (datetime.datetime.now() - t0).total_seconds() / 60
        got = done(name)
        status = "ok" if result.returncode == 0 else f"EXIT {result.returncode}"
        print(f"[{i}/{len(SWEEPS)}] {name}: {status}, {got} runs, {mins:.1f} min",
              flush=True)
        if result.returncode != 0:
            tail = (result.stderr or result.stdout or "").strip().splitlines()[-6:]
            for line in tail:
                print(f"      | {line}", flush=True)

    total = (datetime.datetime.now() - started).total_seconds() / 60
    print(f"\nqueue finished in {total:.1f} min", flush=True)
    with sqlite3.connect(f"file:{DB}?mode=ro", uri=True) as conn:
        for name in SWEEPS:
            n, ok, sk, fl = conn.execute(
                "select count(*), sum(status='succeeded'), sum(status='skipped'), "
                "sum(status='failed') from runs where config_name = ?", (name,)
            ).fetchone()
            print(f"  {name:34s} {n:4d} runs  ok={ok} skip={sk} fail={fl}")


if __name__ == "__main__":
    sys.exit(main())
