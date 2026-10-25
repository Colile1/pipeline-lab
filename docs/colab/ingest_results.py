"""Bring a Colab results zip back into the project for package v7.

Usage: python ingest_results.py <PipelineLab_Colab_Results_<profile>.zip>

Unpacks the zip into 671 Research June/Colab/results/<profile>/, checks
that it is complete and trustworthy, and prints the facts the report's
reproduction section needs. It refuses to call a re-run a reproduction
if the library versions did not match the pins, because then a
difference in scores could come from the libraries rather than the study.
"""
import json
import os
import pathlib
import sys
import zipfile

DEST = pathlib.Path(os.environ.get("PIPELAB_RESULTS_DEST",
    r"C:/Users/Colile/Documents/School/NWU/S1/ITRI671 Project/671 Research June/Colab/results"))


def main(zip_path):
    zip_path = pathlib.Path(zip_path)
    with zipfile.ZipFile(zip_path) as z:
        assert z.testzip() is None, "the results zip is corrupt"
        env = json.loads(z.read("environment.json"))
        profile = env["profile"]
        out = DEST / profile
        out.mkdir(parents=True, exist_ok=True)
        z.extractall(out)

    problems = []
    for need in ("lab_colab.db", "comparison_summary.json", "COLAB_RESULTS.md", "environment.json"):
        if not (out / need).exists():
            problems.append(f"missing {need}")
    if env["mismatch"]:
        problems.append(f"library versions differ from the pins: {env['mismatch']}")
    if "Linux" not in env["env"]["platform"]:
        # A re-run on the original machine is not an independent reproduction,
        # and must not be reported as the Colab result.
        problems.append(f"not produced on Colab (platform: {env['env']['platform']})")

    cmp = json.loads((out / "comparison_summary.json").read_text(encoding="utf-8"))
    done = len(list((out / "chunks").glob("*.done.json")))
    errors = len(list((out / "chunks").glob("*.error.txt")))
    md = (out / "COLAB_RESULTS.md").read_text(encoding="utf-8")
    complete = "Profile complete: yes" in md

    pct = lambda a, b: f"{100.0 * a / b:.1f}" if b else "n/a"
    facts = {
        "profile": profile,
        "profile_complete": complete,
        "chunks_done": done,
        "chunks_with_errors": errors,
        "environment": env["env"],
        "versions_match_pins": not env["mismatch"],
        "cells_compared": cmp["cells_compared"],
        "status_agree_pct": pct(cmp["status_agree"], cmp["cells_compared"]),
        "both_succeeded": cmp["both_succeeded"],
        "folds_identical": cmp["folds_identical"],
        "folds_identical_pct": pct(cmp["folds_identical"], cmp["both_succeeded"]),
        "max_abs_diff": cmp["max_abs_diff"],
        "mismatching_cells": len(cmp["mismatches"]),
    }
    (out / "v7_facts.json").write_text(json.dumps(facts, indent=1), encoding="utf-8")

    print(f"unpacked to {out}")
    for k, v in facts.items():
        if k != "environment":
            print(f"  {k:22s} {v}")
    e = env["env"]
    print(f"  environment            Python {e['python']}, {e['cpus']} CPUs, {e['platform']}")
    if not complete:
        problems.append("the profile did not finish; the figures cover a partial run")
    if errors:
        problems.append(f"{errors} chunk(s) recorded an engine error")
    print("\nREADY FOR v7" if not problems else "\nCHECK BEFORE v7:\n  - " + "\n  - ".join(problems))
    return 0 if not problems else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1]))
