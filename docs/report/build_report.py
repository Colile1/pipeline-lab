"""Build the standalone research report as a .docx.

Formatting follows the ITRI 671 guidelines: 12 pt body, 1.5 line
spacing, title page with the required details, table of contents, list
of tables and list of figures. The contents pages are inserted as Word
field codes so that Word populates them with correct page numbers when
the reader refreshes (Ctrl+A then F9).
"""
import pathlib
import re

from docx import Document
from docx.enum.section import WD_SECTION
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_BREAK
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Inches, Pt, RGBColor

HERE = pathlib.Path(__file__).resolve().parent
FIGS = pathlib.Path(
    r"C:/Users/Colile/Documents/School/NWU/S1/ITRI671 Project/671 Research June/pipeline-lab/docs/figures"
)
OUT = pathlib.Path(
    r"C:/Users/Colile/Documents/School/NWU/S1/ITRI671 Project/671 Research June/Chapters/"
    r"Pipeline Lab Research Report  _  25 October 2026.docx"
)

ns = {}
exec((HERE / "report_content.py").read_text(encoding="utf-8"), ns)
CONTENT = ns["CONTENT"]
REFS = [r for r in (HERE / "verified_refs.txt").read_text(encoding="utf-8").splitlines() if r.strip()]

BLACK = RGBColor(0, 0, 0)
doc = Document()

# ---- base styles -----------------------------------------------------
normal = doc.styles["Normal"]
normal.font.name = "Calibri"
normal.font.size = Pt(12)
normal.paragraph_format.line_spacing = 1.5
normal.paragraph_format.space_after = Pt(8)
normal.element.rPr.rFonts.set(qn("w:eastAsia"), "Calibri")

for name, size, bold in (("Heading 1", 16, True), ("Heading 2", 14, True),
                         ("Heading 3", 12, True)):
    st = doc.styles[name]
    st.font.name = "Calibri"
    st.font.size = Pt(size)
    st.font.bold = bold
    st.font.color.rgb = BLACK
    st.paragraph_format.space_before = Pt(14 if name == "Heading 1" else 10)
    st.paragraph_format.space_after = Pt(6)
    st.paragraph_format.line_spacing = 1.25

for s in doc.sections:
    s.left_margin = s.right_margin = Inches(1.0)
    s.top_margin = s.bottom_margin = Inches(1.0)


def para(text, size=12, bold=False, align=None, italic=False, space_after=8):
    p = doc.add_paragraph()
    p.paragraph_format.line_spacing = 1.5
    p.paragraph_format.space_after = Pt(space_after)
    if align is not None:
        p.alignment = align
    r = p.add_run(text)
    r.font.size = Pt(size)
    r.font.bold = bold
    r.font.italic = italic
    r.font.name = "Calibri"
    return p


def field(instr):
    """Insert a Word field (used for the TOC and the figure/table lists)."""
    p = doc.add_paragraph()
    r = p.add_run()
    fld = OxmlElement("w:fldChar"); fld.set(qn("w:fldCharType"), "begin")
    itxt = OxmlElement("w:instrText"); itxt.set(qn("xml:space"), "preserve")
    itxt.text = instr
    sep = OxmlElement("w:fldChar"); sep.set(qn("w:fldCharType"), "separate")
    hint = OxmlElement("w:t")
    hint.text = "Right-click and choose Update Field, or press Ctrl+A then F9."
    end = OxmlElement("w:fldChar"); end.set(qn("w:fldCharType"), "end")
    for el in (fld, itxt, sep, hint, end):
        r._r.append(el)
    return p


def page_break():
    doc.add_paragraph().add_run().add_break(WD_BREAK.PAGE)


def add_caption(text, kind):
    """Caption paragraph that the List of Figures/Tables can pick up."""
    p = doc.add_paragraph()
    p.paragraph_format.space_after = Pt(12)
    p.paragraph_format.line_spacing = 1.0
    p.alignment = WD_ALIGN_PARAGRAPH.LEFT
    r = p.add_run(text)
    r.font.size = Pt(10)
    r.font.italic = True
    r.font.name = "Calibri"
    try:
        p.style = doc.styles["Caption"]
        for run in p.runs:
            run.font.size = Pt(10)
            run.font.italic = True
            run.font.color.rgb = BLACK
            run.font.name = "Calibri"
    except KeyError:
        pass
    return p


def add_references():
    """The NWU-Harvard reference list, alphabetical, hanging indent."""
    doc.add_heading("References", level=1)
    for ref in sorted(REFS, key=lambda s: s.lower()):
        p = doc.add_paragraph()
        p.paragraph_format.line_spacing = 1.5
        p.paragraph_format.space_after = Pt(8)
        p.paragraph_format.left_indent = Inches(0.5)
        p.paragraph_format.first_line_indent = Inches(-0.5)
        p.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
        r = p.add_run(ref)
        r.font.size = Pt(12)
        r.font.name = "Calibri"


# ===================== render ========================================
figure_no = 0
refs_done = False
for kind, value in CONTENT:
    if kind == "title":
        for _ in range(5):
            doc.add_paragraph()
        para(value, size=22, bold=True, align=WD_ALIGN_PARAGRAPH.CENTER, space_after=10)
    elif kind == "subtitle":
        para(value, size=13, italic=True, align=WD_ALIGN_PARAGRAPH.CENTER, space_after=30)
    elif kind == "titlemeta":
        for line in value:
            para(line, size=12, align=WD_ALIGN_PARAGRAPH.CENTER, space_after=2)
    elif kind == "h1":
        doc.add_heading(value, level=1)
    elif kind == "h2":
        doc.add_heading(value, level=2)
    elif kind == "h3":
        doc.add_heading(value, level=3)
    elif kind == "p":
        p = para(value)
        p.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
    elif kind == "b":
        p = doc.add_paragraph(value, style="List Bullet")
        p.paragraph_format.line_spacing = 1.5
        p.paragraph_format.space_after = Pt(4)
        for r in p.runs:
            r.font.size = Pt(12)
            r.font.name = "Calibri"
    elif kind == "tbl":
        caption, rows = value
        t = doc.add_table(rows=len(rows), cols=len(rows[0]))
        t.style = "Table Grid"
        for i, row in enumerate(rows):
            for j, cell in enumerate(row):
                c = t.cell(i, j)
                c.text = ""
                cp = c.paragraphs[0]
                cp.paragraph_format.line_spacing = 1.0
                cp.paragraph_format.space_after = Pt(2)
                run = cp.add_run(str(cell))
                run.font.size = Pt(10)
                run.font.bold = (i == 0)
                run.font.name = "Calibri"
        add_caption(caption, "table")
    elif kind == "fig":
        fname, caption = value
        path = FIGS / fname
        if path.exists():
            doc.add_picture(str(path), width=Inches(6.2))
            doc.paragraphs[-1].alignment = WD_ALIGN_PARAGRAPH.CENTER
            add_caption(caption, "figure")
        else:
            para(f"[missing figure: {fname}]", italic=True)
    elif kind == "pg":
        page_break()
    elif kind == "refs":
        add_references()
        refs_done = True

# ---- references ------------------------------------------------------
# Rendered where the content places a ("refs", None) marker, so that
# appendices can follow the reference list as the guidelines require.
# A document without the marker still gets its references at the end.
if not refs_done:
    add_references()

# ---- front matter inserted at the start ------------------------------
front = doc.add_paragraph()
body = doc.element.body
front_elems = []

def mk(text, style=None, size=12, bold=False, align=None, spacing=1.5):
    p = doc.add_paragraph()
    p.paragraph_format.line_spacing = spacing
    if align is not None:
        p.alignment = align
    r = p.add_run(text)
    r.font.size = Pt(size)
    r.font.bold = bold
    r.font.name = "Calibri"
    front_elems.append(p._p)
    return p

# build front matter at the end, then move it into position
mk("Table of Contents", size=16, bold=True)
toc = field(r'TOC \o "1-3" \h \z \u'); front_elems.append(toc._p)
brk = doc.add_paragraph(); brk.add_run().add_break(WD_BREAK.PAGE); front_elems.append(brk._p)

mk("List of Tables", size=16, bold=True)
lot = field(r'TOC \h \z \c "Table"'); front_elems.append(lot._p)
mk("List of Figures", size=16, bold=True)
lof = field(r'TOC \h \z \c "Figure"'); front_elems.append(lof._p)
brk2 = doc.add_paragraph(); brk2.add_run().add_break(WD_BREAK.PAGE); front_elems.append(brk2._p)

# locate the paragraph that ends the title page (first page break)
children = list(body)
first_break = None
for i, el in enumerate(children):
    if el.tag.endswith("}p") and el.findall(".//" + qn("w:br")):
        for br in el.findall(".//" + qn("w:br")):
            if br.get(qn("w:type")) == "page":
                first_break = i
                break
    if first_break is not None:
        break

anchor = children[first_break]
for el in front_elems:
    body.remove(el)
    anchor.addnext(el)
    anchor = el

body.remove(front._p)

# ---- page numbers in the footer --------------------------------------
sec = doc.sections[0]
fp = sec.footer.paragraphs[0]
fp.alignment = WD_ALIGN_PARAGRAPH.CENTER
r = fp.add_run()
for tag, attr, text in (("w:fldChar", "begin", None),
                        ("w:instrText", None, "PAGE"),
                        ("w:fldChar", "end", None)):
    el = OxmlElement(tag)
    if attr:
        el.set(qn("w:fldCharType"), attr)
    if text:
        el.set(qn("xml:space"), "preserve")
        el.text = text
    r._r.append(el)

OUT.parent.mkdir(parents=True, exist_ok=True)
doc.save(str(OUT))
print("saved:", OUT)

d2 = Document(str(OUT))
words = sum(len(p.text.split()) for p in d2.paragraphs)
print(f"paragraphs: {len(d2.paragraphs)}, words: {words:,}, "
      f"tables: {len(d2.tables)}, references: {len(REFS)}")
