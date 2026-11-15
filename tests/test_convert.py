"""Golden tests: representative snapshot HTML must convert to the committed Markdown."""

from pathlib import Path

import pytest

from unem.convert import convert_page, first_sentence, rewrite_href

FIX = Path(__file__).parent / "fixtures"
BASE = "https://www.un.org/dgacm/en/content/editorial-manual/"
CASES = ["spelling", "abbreviations", "capitalization", "tables", "updates", "footnotes/chap-04", "country-names"]
KNOWN = set(CASES) | {"policy-questions", "res-dec-index", "para-subpara", "numbers-dates-time", "headings"}


@pytest.mark.parametrize("slug", CASES)
def test_golden(slug, request):
    html = (FIX / "html" / f"{slug}.html").read_text(encoding="utf-8")
    heading, md = convert_page(html, slug, BASE + slug, KNOWN)
    out = f"# {heading}\n\n{md}"
    golden = FIX / "md" / f"{slug}.md"
    if request.config.getoption("--update-goldens") or not golden.exists():
        golden.parent.mkdir(parents=True, exist_ok=True)
        golden.write_text(out, encoding="utf-8")
    assert out == golden.read_text(encoding="utf-8")


def test_deterministic():
    html = (FIX / "html" / "spelling.html").read_text(encoding="utf-8")
    assert convert_page(html, "spelling", BASE + "spelling", KNOWN) == convert_page(
        html, "spelling", BASE + "spelling", KNOWN
    )


def test_no_code_blocks_from_indentation():
    import re

    for slug in CASES:
        html = (FIX / "html" / f"{slug}.html").read_text(encoding="utf-8")
        _, md = convert_page(html, slug, BASE + slug, KNOWN)
        lines = md.splitlines()
        for i, line in enumerate(lines):
            if re.match(r"^ {4,}\S", line) and not re.match(r"^\s*([-*+]|\d+\.) ", line):
                prev = next(l for l in reversed(lines[:i]) if l.strip())
                assert prev.lstrip()[:1] in "-*+0123456789" or prev.startswith(" "), (slug, line)


def test_spelling_structure():
    html = (FIX / "html" / "spelling.html").read_text(encoding="utf-8")
    _, md = convert_page(html, "spelling", BASE + "spelling", KNOWN)
    assert "## A {#a}" in md
    assert "- amid (not “amidst”)" in md or '- amid (not "amidst")' in md
    assert "  - after-effect" in md  # indented sub-entry became a nested list item
    assert "[B](#b)" not in md  # A–Z navigation bar removed


@pytest.mark.parametrize(
    "href,cur,expected",
    [
        ("spelling", "capitalization", "spelling.md"),
        ("https://www.un.org/dgacm/en/content/editorial-manual/abbreviations#S", "updates", "abbreviations.md#S"),
        ("http://www.un.org/dgacm/content/editorial-manual/spelling#r", "updates", "spelling.md#r"),
        ("../spelling", "footnotes/chap-04", "../spelling.md"),
        ("/dgacm/sites/x.pdf", "spelling", "https://www.un.org/dgacm/sites/x.pdf"),
        ("#a", "spelling", "#a"),
        ("unknown-page", "spelling", "https://www.un.org/dgacm/en/content/editorial-manual/unknown-page"),
    ],
)
def test_rewrite_href(href, cur, expected):
    known = {"spelling", "capitalization", "abbreviations", "updates", "footnotes/chap-04"}
    assert rewrite_href(href, BASE + cur, cur, known) == expected


def test_first_sentence():
    assert first_sentence("## H\n\nThis is the first sentence of the page. Second.") == "This is the first sentence of the page."
