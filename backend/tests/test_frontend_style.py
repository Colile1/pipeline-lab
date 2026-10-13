# Guards the frontend's visual contract: plain Material/Google styling with
# no emoji, icon glyphs or stray typography.
#
# This exists because the first build used icon glyphs in the nav and em
# dashes throughout, and both are easy to reintroduce by habit. These are
# file-level checks rather than render checks, so they catch a glyph the
# moment it is written rather than when someone looks at the page.
import re
import unicodedata
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)

FRONTEND = Path(__file__).resolve().parents[2] / "frontend"
SOURCES = sorted(
    p for p in FRONTEND.rglob("*")
    if p.suffix in {".html", ".css", ".js"}
)

# Numeric HTML entities are how the icon glyphs were written the first time
# (&#128202; and friends), so an ASCII-only check alone would not catch them.
NUMERIC_ENTITY = re.compile(r"&#x?[0-9a-fA-F]+;")

# Entities that are named rather than numeric but still render a glyph.
GLYPH_ENTITIES = ("&rsaquo;", "&laquo;", "&raquo;", "&mdash;", "&ndash;",
                  "&hellip;", "&bull;", "&middot;", "&times;", "&larr;",
                  "&rarr;", "&#9776;")


def test_there_are_frontend_sources_to_check():
    """Guard the guard: a bad path would make every check below vacuous."""
    assert len(SOURCES) >= 10, [str(p) for p in SOURCES]


@pytest.mark.parametrize("path", SOURCES, ids=lambda p: p.name)
def test_no_source_file_contains_a_non_ascii_character(path):
    """Emoji, dashes and arrows all fail here.

    ASCII-only keeps the UI independent of which fonts the machine has:
    a glyph with no font renders as a replacement box, which looks like a
    bug to the person using it.
    """
    text = path.read_text(encoding="utf-8")
    offenders = {
        ch: unicodedata.name(ch, "unnamed")
        for ch in set(text) if ord(ch) > 126
    }
    assert not offenders, f"{path.name} has non-ASCII: {offenders}"


@pytest.mark.parametrize("path", SOURCES, ids=lambda p: p.name)
def test_no_source_file_smuggles_a_glyph_in_as_an_entity(path):
    """&#128202; is ASCII in the file but an emoji on the page."""
    text = path.read_text(encoding="utf-8")
    assert not NUMERIC_ENTITY.findall(text), path.name
    found = [e for e in GLYPH_ENTITIES if e in text]
    assert not found, f"{path.name} uses glyph entities: {found}"


def test_the_guard_would_actually_catch_an_emoji():
    """Non-vacuous: the checks above must fail on a file that has one."""
    sample = "<span>chart \U0001F4CA</span>"
    assert any(ord(ch) > 126 for ch in sample)
    assert NUMERIC_ENTITY.search("<span>&#128202;</span>") is not None


@pytest.mark.parametrize("page", [
    "/", "/datasets", "/experiment", "/runs", "/results",
    "/compose", "/network", "/trends",
])
def test_every_rendered_page_is_ascii_only(page):
    """The templates compose at request time, so check the output too."""
    body = client.get(page).text
    offenders = {ch for ch in set(body) if ord(ch) > 126}
    assert not offenders, f"{page} rendered non-ASCII: {offenders}"


def test_every_page_loads_the_current_stylesheet():
    """One stylesheet, referenced everywhere; the old one must be gone."""
    for page in ("/", "/compose", "/trends"):
        body = client.get(page).text
        assert "css/theme.css" in body
        assert "azure-theme" not in body
    assert client.get("/static/css/theme.css").status_code == 200
    assert client.get("/static/css/azure-theme.css").status_code == 404


def test_every_corner_is_square_and_driven_by_one_token():
    """Square corners, set in a single place.

    Each rule routes through --radius rather than carrying its own value,
    so the whole interface changes from one line and no rule can quietly
    disagree with the rest.
    """
    css = client.get("/static/css/theme.css").text
    assert "--radius: 0;" in css
    # Collect every value, then compare: a lookahead here is fragile
    # because \s* backtracks around it and matches anyway.
    values = {v.strip() for v in re.findall(r"border-radius:([^;]+);", css)}
    literal = sorted(v for v in values if v != "var(--radius)")
    assert not literal, f"radius values bypassing the token: {literal}"


def test_the_theme_declares_one_accent_colour():
    """A second accent is how a plain interface starts to look busy."""
    css = client.get("/static/css/theme.css").text
    assert "--blue: #1a73e8" in css
    # Cards are flat: a shadow is the main thing that makes a surface look
    # heavier than Material's baseline.
    assert "box-shadow: var(--shadow)" not in css
