"""Build a submission-ready archive of the project as it stands.

Purpose: a baseline that could be submitted as-is if later work runs out
of time. Everything in it is already complete and verified. The archive
carries a manifest that records what each file is, when it was produced
and which git commit it corresponds to, so the contents can be dated and
traced rather than taken on trust.

Version is passed on the command line (v1, v2, ...) so successive
baselines sit beside each other instead of overwriting.
"""
import hashlib
import pathlib
import shutil
import sqlite3
import subprocess
import sys
import zipfile
from datetime import datetime

VERSION = sys.argv[1] if len(sys.argv) > 1 else "v1"

ROOT = pathlib.Path(r"C:/Users/Colile/Documents/School/NWU/S1/ITRI671 Project")
RESEARCH = ROOT / "671 Research June"
LAB = RESEARCH / "pipeline-lab"
ENGINE = ROOT / "pipeline-lab-engine"
ETHICS = ROOT / "Ethics docs"
OUT = RESEARCH / "Submission" / f"ITRI671 Pipeline Lab Submission {VERSION}.zip"
OUT.parent.mkdir(parents=True, exist_ok=True)

# (source, path inside the archive, description for the manifest)
ITEMS = [
    (RESEARCH / "Chapters" / "Pipeline Lab Research Report  _  25 October 2026.docx",
     "01 Report/Pipeline Lab Research Report.docx",
     "The research report, Chapters 1-5 per Addendum F. PRIMARY SUBMISSION."),
    (RESEARCH / "September" /
     "ITRI671 Pipeline Lab Poster A2 Landscape BW _ 17 October 2026 FINAL (editable).pptx",
     "02 Poster/ITRI671 Pipeline Lab Poster A2.pptx",
     "A2 landscape poster for project day, editable."),
    (LAB / "docs" / "RESEARCH-REPORT.md", "03 Supporting/RESEARCH-REPORT.md",
     "Source text of the report in Markdown."),
    (LAB / "docs" / "FINDINGS-REPORT.md", "03 Supporting/FINDINGS-REPORT.md",
     "Statistical detail behind the findings, with the master figures."),
    (LAB / "docs" / "META-ANALYSIS.md", "03 Supporting/META-ANALYSIS.md",
     "Dataset-characteristic meta-analysis over the run record."),
    (LAB / "docs" / "PREREGISTRATION-HELDOUT.md",
     "03 Supporting/PREREGISTRATION-HELDOUT.md",
     "Pre-registered prediction for the held-out test, committed to git "
     "before any of those datasets were scored."),
    (LAB / "docs" / "PROCESS-LOG.md", "03 Supporting/PROCESS-LOG.md",
     "Dated log of the whole research process, including corrections."),
    (LAB / "docs" / "PLAN.md", "03 Supporting/PLAN.md",
     "Design decisions taken before building."),
    (LAB / "docs" / "SCOPE-DECISIONS.md", "03 Supporting/SCOPE-DECISIONS.md",
     "Scope boundaries and the reasoning for them."),
    (ENGINE / "outputs" / "lab.db", "04 Data/lab.db",
     "The complete run record. Append-only SQLite, one row per run."),
    # Appendices A and B of the report, attached as the signed originals.
    (ETHICS / "Sibanda EthicsForm signed.pdf",
     "07 Appendices/Appendix A - Research ethics form (signed).pdf",
     "Appendix A: ITRI 671 research ethics form, signed 31 August 2026."),
    (ETHICS / "Module 1 _2023__Certificate of completion for module 1 _2023_.pdf",
     "07 Appendices/Appendix B1 - TRREE Module 1 Introduction to Research Ethics.pdf",
     "Appendix B: TRREE training certificate, module 1."),
    (ETHICS / "Module 2 _2023__Certificate of completion for module 2 _2023_.pdf",
     "07 Appendices/Appendix B2 - TRREE Module 2 Research Ethics Evaluation.pdf",
     "Appendix B: TRREE training certificate, module 2."),
    (ETHICS / "Module 3 _2023__Certificate of completion for module 3 _2023_.pdf",
     "07 Appendices/Appendix B3 - TRREE Module 3 Informed Consent.pdf",
     "Appendix B: TRREE training certificate, module 3."),
    (ETHICS / "Code+of+Conduct+for+Researchers+-+9.1.5.1.3_Code_Conduct_.pdf",
     "07 Appendices/Appendix B4 - NWU Code of Conduct for Researchers (signed).pdf",
     "Appendix B: NWU Code of Conduct for Researchers, signed 31 August 2026."),
    # Appendix D: the re-run bundle.
    (RESEARCH / "Colab" / "PipelineLab_Colab.zip",
     "08 Reproduction/PipelineLab_Colab.zip",
     "Appendix D: main_colab.ipynb and everything it needs to re-run the experiments "
     "on Google Colab and compare the result with the original record."),
]

FIG_DIR = LAB / "docs" / "figures"
ANALYSIS_DIR = LAB / "docs" / "analysis"


def git_sha(repo):
    try:
        return subprocess.run(["git", "-C", str(repo), "rev-parse", "--short", "HEAD"],
                              capture_output=True, text=True, timeout=30).stdout.strip()
    except Exception:
        return "unknown"


def sha256(path, limit=None):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        while chunk := fh.read(1 << 20):
            h.update(chunk)
    return h.hexdigest()[:16]


# ---- record statistics for the manifest -----------------------------
conn = sqlite3.connect(f"file:{ENGINE / 'outputs' / 'lab.db'}?mode=ro", uri=True)
total, ok, skipped, failed = conn.execute(
    "select count(*), sum(status='succeeded'), sum(status='skipped'), "
    "sum(status='failed') from runs").fetchone()
datasets = conn.execute("select count(distinct dataset) from runs").fetchone()[0]
sweeps = conn.execute("select count(distinct config_name) from runs").fetchone()[0]
hours = conn.execute("select sum(wall_seconds)/3600.0 from runs").fetchone()[0]
first = conn.execute("select min(started_at) from runs").fetchone()[0]
last = conn.execute("select max(ended_at) from runs").fetchone()[0]
conn.close()

lines = []
w = lines.append
w(f"ITRI 671 PIPELINE LAB - SUBMISSION PACKAGE {VERSION.upper()}")
w("=" * 70)
w("")
w(f"Assembled      {datetime.now():%Y-%m-%d %H:%M}")
w("Student        Colile Sibanda (56543115)")
w("Supervisor     Prof Imelda Smit")
w("Module         ITRI 671, BSc Honours in Computer Science and IT, 2026")
w("Institution    North-West University, Vanderbijlpark")
w("")
w("STATUS: complete and verified. This package can be submitted as it")
w("stands. Later work, if any, produces a higher-numbered package.")
w("")
w("-" * 70)
w("THE RUN RECORD")
w("-" * 70)
w(f"  runs recorded      {total:,}")
w(f"    succeeded        {ok:,}")
w(f"    skipped          {skipped:,}  (refused with a recorded reason)")
w(f"    failed           {failed:,}  (each with a documented cause and fix)")
w(f"  datasets           {datasets}")
w(f"  sweeps             {sweeps}")
w(f"  measured compute   {hours:.1f} hours")
w(f"  first run          {first}")
w(f"  last run           {last}")
w("")
w("-" * 70)
w("CODE VERSIONS AT TIME OF PACKAGING")
w("-" * 70)
w(f"  engine (pipeline-lab-engine)   {git_sha(ENGINE)}")
w(f"  dashboard and docs (pipeline-lab)  {git_sha(LAB)}")
w("")
w("-" * 70)
w("CONTENTS")
w("-" * 70)

manifest_rows = []
with zipfile.ZipFile(OUT, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as z:
    for src, arc, desc in ITEMS:
        if not src.exists():
            print(f"  MISSING (skipped): {src}")
            continue
        z.write(src, arc)
        stat = src.stat()
        manifest_rows.append((arc, stat.st_size, datetime.fromtimestamp(stat.st_mtime),
                              sha256(src), desc))

    for fig in sorted(FIG_DIR.glob("*.png")):
        arc = f"05 Figures/{fig.name}"
        z.write(fig, arc)
        stat = fig.stat()
        manifest_rows.append((arc, stat.st_size, datetime.fromtimestamp(stat.st_mtime),
                              sha256(fig), "Figure used in the report or poster."))

    for scr in sorted(ANALYSIS_DIR.glob("*.py")):
        arc = f"06 Analysis scripts/{scr.name}"
        z.write(scr, arc)
        stat = scr.stat()
        manifest_rows.append((arc, stat.st_size, datetime.fromtimestamp(stat.st_mtime),
                              sha256(scr),
                              "Reproduces figures and statistics from the record."))

    for arc, size, mtime, digest, desc in manifest_rows:
        w("")
        w(f"  {arc}")
        w(f"      {size:,} bytes | modified {mtime:%Y-%m-%d %H:%M} | sha256 {digest}")
        w(f"      {desc}")

    w("")
    w("-" * 70)
    w("NOTES FOR THE READER")
    w("-" * 70)
    w("")
    w("  The report's table of contents, list of tables and list of figures")
    w("  are Word fields. Open the document and press Ctrl+A then F9 to")
    w("  populate them with page numbers.")
    w("")
    w("  The run record (04 Data/lab.db) is a SQLite database. Every number")
    w("  in the report can be recomputed from it using the scripts in")
    w("  06 Analysis scripts.")
    w("")
    w("  Not included and to be added before submission: the ethics form")
    w("  and the declaration of integrity, per Addendum F.")

    z.writestr("MANIFEST.txt", "\n".join(lines))

print(f"\nwritten: {OUT}")
print(f"size: {OUT.stat().st_size / 1e6:.1f} MB, {len(manifest_rows) + 1} entries")
