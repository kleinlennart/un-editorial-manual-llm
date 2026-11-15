"""llms.txt must parse with the reference parser from llmstxt.org (llms-txt package)."""

from pathlib import Path

import pytest
from llms_txt import parse_llms_file

from unem.llmstxt import DISCLAIMER
from unem.manifest import Manifest

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def manifest():
    m = Manifest.load(ROOT / "manifest.json")
    if m is None:
        pytest.skip("run `unem build` first")
    return m


def test_llms_txt_parses(manifest):
    parsed = parse_llms_file((ROOT / "llms.txt").read_text(encoding="utf-8"))
    assert parsed.title == "United Nations Editorial Manual"
    assert DISCLAIMER in parsed.summary
    sections = parsed.sections
    assert "Style" in sections and "Optional" in sections
    listed = [l["url"] for links in sections.values() for l in links]
    # Every mirrored page is listed exactly once.
    assert len(listed) == len(set(listed)) == len(manifest.pages)


def test_llms_full_contains_every_page(manifest):
    full = (ROOT / "llms-full.txt").read_text(encoding="utf-8")
    for p in manifest.pages:
        assert f"page: {p.slug} |" in full
