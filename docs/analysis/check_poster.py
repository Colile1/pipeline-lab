"""Verify the built poster. Catches what an earlier filtered check missed.

The first version of this check only looked at shapes inside a y-window,
so a whole section that fell off the bottom of the page was invisible to
it. This checks every shape against the page, then reports columns.
"""
import pathlib

from pptx import Presentation
from pptx.util import Emu

SRC = pathlib.Path(
    r"C:/Users/Colile/Documents/School/NWU/S1/ITRI671 Project/671 Research June/September/"
    r"ITRI671 Pipeline Lab Poster A2 Landscape BW _ 17 October 2026 FINAL (editable).pptx"
)
prs = Presentation(str(SRC))
PW = Emu(prs.slide_width).inches
PH = Emu(prs.slide_height).inches
s = prs.slides[0]

print(f"page {PW:.2f} x {PH:.2f} in, {len(s.shapes)} shapes")

def label(sh):
    if sh.has_text_frame and sh.text_frame.text.strip():
        return sh.text_frame.text[:58].replace("\n", " / ")
    return "[figure or rule]"

# 1. nothing off the page, in any direction
problems = []
for sh in s.shapes:
    L = Emu(sh.left or 0).inches
    T = Emu(sh.top or 0).inches
    R = L + Emu(sh.width or 0).inches
    B = T + Emu(sh.height or 0).inches
    if T < -0.01 or L < -0.01 or B > PH + 0.01 or R > PW + 0.01:
        problems.append((T, B, R, label(sh)))

print("\n1. off-page shapes:")
if problems:
    for T, B, R, txt in sorted(problems):
        print(f"   top={T:6.2f} bottom={B:6.2f} right={R:6.2f}  {txt}")
else:
    print("   none")

# 2. column balance, using the GROWN height of each text box.
#    A box is created 0.3in tall and PowerPoint grows it to fit, so the
#    declared height says nothing about where the text really ends. An
#    earlier version of this check used the declared height and passed a
#    poster whose last section spilled a full 2.5in past the footer.
from PIL import ImageFont

_REG = ImageFont.truetype(r"C:/Windows/Fonts/calibri.ttf", 400)
_BOLD = ImageFont.truetype(r"C:/Windows/Fonts/calibrib.ttf", 400)
COL_W = 5.10


def grown_height(sh):
    """Height the text actually occupies, in inches."""
    if not sh.has_text_frame or not sh.text_frame.text.strip():
        return Emu(sh.height or 0).inches
    total = 0.0
    for para in sh.text_frame.paragraphs:
        txt = "".join(r.text for r in para.runs)
        if not txt.strip():
            continue
        run = para.runs[0]
        size = run.font.size.pt if run.font.size else 12
        font = _BOLD if run.font.bold else _REG
        limit = COL_W * 72.0
        scale = size / 400.0
        lines, cur = 1, ""
        for word in txt.split():
            trial = word if not cur else cur + " " + word
            if font.getlength(trial) * scale <= limit:
                cur = trial
            else:
                lines += 1
                cur = word
        total += lines * (size * 1.22 / 72.0) + 0.07
    return total


print("\n2. column content, measured from grown text (footer at 15.94):")
for cx, name in {0.71: "C1", 6.33: "C2", 11.96: "C3", 17.58: "C4"}.items():
    items = [sh for sh in s.shapes
             if abs(Emu(sh.left or 0).inches - cx) < 0.05
             and 4.2 < Emu(sh.top or 0).inches < 15.94]
    if items:
        b = max(Emu(sh.top).inches + grown_height(sh) for sh in items)
        state = "SPILLS PAST FOOTER" if b > 15.94 else "ok"
        print(f"   {name}: text ends {b:5.2f} in  {state}")

# 3. overlapping text blocks within a column
print("\n3. overlaps within a column:")
found = False
for cx in (0.71, 6.33, 11.96, 17.58):
    items = sorted(
        [sh for sh in s.shapes
         if abs(Emu(sh.left or 0).inches - cx) < 0.05
         and sh.has_text_frame and sh.text_frame.text.strip()
         and Emu(sh.height or 0).inches > 0.2],
        key=lambda x: Emu(x.top).inches)
    for a, b in zip(items, items[1:]):
        a_end = Emu(a.top).inches + Emu(a.height).inches
        if a_end > Emu(b.top).inches + 0.02:
            found = True
            print(f"   {label(a)[:40]} -> {label(b)[:40]}")
if not found:
    print("   none detected (note: boxes auto-grow, so this is advisory)")

# 4. figures present
figs = [sh for sh in s.shapes if sh.shape_type == 13]
print(f"\n4. figures embedded: {len(figs)}")

print("\nVERDICT:", "PASS" if not problems else "FAIL - shapes off page")
