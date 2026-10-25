"""Verification gate for the built report.

Checks the document rather than the source, because several defects
have only ever shown up after the build: a caption that refreshed
while its hardcoded numbers did not, a table number duplicated by an
insertion, a stale figure surviving in a cell, an abstract that grew
past its limit with a fragment of an earlier edit inside it.

Lessons baked in. Caption checks filter on the Caption STYLE, because
a paragraph that opens "Table 4.3 summarises..." is prose introducing
a table, not a second caption. Stale-figure checks match the
surrounding claim, not a bare number: screening for "67 per cent"
flagged the three-seed result, which legitimately contains it. Body
tables are numbered 4.x and appendix tables A.1, B.1 and so on, and
the two series are checked separately.

Usage: python verify_report.py [path-to-docx]
"""
import re
import sys

from docx import Document

DEFAULT = (r"C:\Users\Colile\Documents\School\NWU\S1\ITRI671 Project"
           r"\671 Research June\Chapters\Pipeline Lab Research Report  _  25 October 2026.docx")

STALE = [
    "5,049 recorded runs", "over 26 datasets", "83.4 hours", "54.6 of the",
    "67 per cent of the total compute", "21 of the 25", "28 produced",
    "29 pairwise", "twenty cells", "rho = 0.882", "108.4 seconds",
    "random forest 96.8", "228-fold", "further 2,336 runs",
    "twenty of its twenty-five", "no ethical clearance beyond",
    "additional random seeds. Of 167",
    "\u2014", "\u2013", "\u2212",
]
REQUIRED = [
    "4,761", "31 datasets", "85.5", "58.1", "68 per cent of the compute",
    "0.0071", "23 of the 34", "34 contrasts", "54 of the 64",
    "0.9718", "118.5", "224-fold", "7,449", "59 per cent", "10 of 17",
    "5,054", "0.3125", "eeg-eye-state", "20260702", "23 contrasts",
    "26 of its 31", "31 August 2026", "Figure 5.1", "Appendix A", "Appendix D",
]
ABSTRACT_RANGE = (150, 300)


def main(path):
    d = Document(path)
    paras = d.paragraphs
    body = "\n".join(x.text for x in paras)
    cells = "\n".join(c.text for t in d.tables for r in t.rows for c in r.cells)
    full = body + "\n" + cells
    problems = []

    caption_text = [x.text.strip() for x in paras if x.style.name == "Caption"]
    nums = [re.match(r"Table (\d+\.\d+)", c).group(1)
            for c in caption_text if re.match(r"Table \d+\.\d+", c)]
    want = [f"4.{i}" for i in range(1, len(nums) + 1)]
    if nums != want:
        problems.append(f"body table numbering not sequential: {nums}")
    app = [re.match(r"Table ([A-Z])\.\d+", c).group(1)
           for c in caption_text if re.match(r"Table [A-Z]\.\d+", c)]
    if app != sorted(app):
        problems.append(f"appendix tables out of order: {app}")
    figs = [re.match(r"Figure (\d+\.\d+)", c).group(1)
            for c in caption_text if re.match(r"Figure \d+\.\d+", c)]
    if len(figs) != len(set(figs)):
        problems.append(f"duplicate figure numbers: {figs}")

    refs = set(re.findall(r"Table (\d+\.\d+)", full))
    dangling = sorted(refs - set(nums))
    if dangling:
        problems.append(f"references to non-existent tables: {dangling}")
    fig_refs = set(re.findall(r"Figure (\d+\.\d+)", full))
    if sorted(fig_refs - set(figs)):
        problems.append(f"references to non-existent figures: {sorted(fig_refs - set(figs))}")

    heads = [i for i, x in enumerate(paras) if x.style.name.startswith("Heading")]
    a = next(i for i in heads if paras[i].text.strip() == "Abstract")
    b = next(i for i in heads if paras[i].text.strip().startswith("Chapter 1"))
    abstract_words = sum(len(x.text.split()) for x in paras[a + 1:b])
    if not ABSTRACT_RANGE[0] <= abstract_words <= ABSTRACT_RANGE[1]:
        problems.append(f"abstract is {abstract_words} words, outside {ABSTRACT_RANGE}")

    ref_head = max(i for i in heads if paras[i].text.strip() == "References")
    app_heads = [i for i in heads if paras[i].text.strip().startswith("Appendix ")]
    if app_heads and min(app_heads) < ref_head:
        problems.append("an appendix appears before the reference list")

    for v in STALE:
        if v in full:
            problems.append(f"stale figure present: {v!r}")
    for v in REQUIRED:
        if v not in full:
            problems.append(f"required figure missing: {v!r}")

    end = min(app_heads) if app_heads else len(paras)
    refsec = "\n".join(x.text for x in paras[ref_head + 1:end])
    cites = set(re.findall(
        r"\(([A-Z][A-Za-z\u00C0-\u024F'\-]+"
        r"(?: (?:and|&) [A-Z][A-Za-z\u00C0-\u024F'\-]+)?(?:, [a-z]+\.)?),? (\d{4})[a-z]?\)",
        body[:body.rfind("References")]))
    unver = [f"{c} {y}" for c, y in sorted(cites) if c.split()[-1] not in refsec]
    if unver:
        problems.append(f"citations not in reference list: {unver}")

    print(f"file: {path.split(chr(92))[-1]}")
    print(f"tables {len(d.tables)}  body captions {len(nums)}  appendix tables {len(app)}  "
          f"figures {len(figs)}  images {len(d.inline_shapes)}  words {len(full.split()):,}")
    print(f"table numbers: {', '.join(nums)}")
    print(f"figure numbers: {', '.join(figs)}")
    print(f"appendices: {[paras[i].text.strip()[:40] for i in app_heads]}")
    print(f"abstract: {abstract_words} words")
    if problems:
        print("\nPROBLEMS:")
        for p in problems:
            print("  -", p)
        print("\nVERDICT: FAIL")
        return 1
    print("\nVERDICT: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1] if len(sys.argv) > 1 else DEFAULT))
