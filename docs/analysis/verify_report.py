"""Verification gate for the built report.

Checks the document rather than the source, because several defects
have only ever shown up after the build: a caption that refreshed
while its hardcoded numbers did not, a table number duplicated by an
insertion, a stale figure surviving in a cell.

Two lessons are baked in. Caption checks filter on the Caption STYLE,
because a paragraph that opens "Table 4.3 summarises..." is prose
introducing a table, not a second caption. And stale-figure checks
match the surrounding claim, not a bare number: screening for
"67 per cent" flagged the three-seed result, which legitimately
contains that figure.
"""
import re
import sys

from docx import Document

PATH = (r"C:\Users\Colile\Documents\School\NWU\S1\ITRI671 Project"
        r"\671 Research June\Chapters\Pipeline Lab Research Report  _  19 October 2026.docx")

# Each stale entry carries enough context to identify the claim.
STALE = [
    "5,049 recorded runs", "over 26 datasets", "83.4 hours", "54.6 of the",
    "67 per cent of the total compute", "21 of the 25", "28 produced",
    "29 pairwise", "twenty cells", "rho = 0.882", "108.4 seconds",
    "random forest 96.8", "228-fold", "further 2,336 runs",
    "\u2014", "\u2013", "\u2212",
]
REQUIRED = [
    "4,761", "31 datasets", "85.5", "58.1", "68 per cent of the total compute",
    "0.0071", "23 of the 34", "34 contrasts", "8 of 23", "54 of the 64",
    "0.9718", "118.5", "224-fold", "7,449", "59 per cent", "10 of 17",
    "5,054", "0.3125", "eeg-eye-state", "20260702", "23 contrasts",
]


def main():
    d = Document(PATH)
    body = "\n".join(x.text for x in d.paragraphs)
    cells = "\n".join(c.text for t in d.tables for r in t.rows for c in r.cells)
    full = body + "\n" + cells
    problems = []

    # Captions: filter on style, not on the text opening with "Table".
    caps = [x.text.strip() for x in d.paragraphs
            if x.style.name == "Caption" and x.text.strip().startswith("Table ")]
    nums = [re.match(r"Table (\d+\.\d+)", c).group(1) for c in caps]
    want = [f"4.{i}" for i in range(1, len(nums) + 1)]
    if nums != want:
        problems.append(f"table numbering not sequential: {nums}")

    refs = set(re.findall(r"Table (\d+\.\d+)", full))
    dangling = sorted(refs - set(nums))
    if dangling:
        problems.append(f"references to non-existent tables: {dangling}")

    for v in STALE:
        if v in full:
            problems.append(f"stale figure present: {v!r}")
    for v in REQUIRED:
        if v not in full:
            problems.append(f"required figure missing: {v!r}")

    refsec = full.split("References")[-1]
    cites = set(re.findall(
        r"\(([A-Z][A-Za-z\u00C0-\u024F'\-]+"
        r"(?: (?:and|&) [A-Z][A-Za-z\u00C0-\u024F'\-]+)?(?:, [a-z]+\.)?),? (\d{4})[a-z]?\)",
        full))
    unver = [f"{a} {y}" for a, y in sorted(cites) if a.split()[-1] not in refsec]
    if unver:
        problems.append(f"citations not in reference list: {unver}")

    print(f"tables {len(d.tables)}  captions {len(nums)}  "
          f"images {len(d.inline_shapes)}  words {len(full.split()):,}")
    print(f"table numbers: {', '.join(nums)}")
    if problems:
        print("\nPROBLEMS:")
        for p in problems:
            print("  -", p)
        print("\nVERDICT: FAIL")
        return 1
    print("\nVERDICT: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
