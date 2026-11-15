from pathlib import Path

from bs4 import BeautifulSoup

from unem.fetch import INDEX_URL, canonical_path, parse_index_groups, slug_for

FIX = Path(__file__).parent / "fixtures" / "html"


def test_canonical_path_variants():
    base = "/dgacm/en/content/editorial-manual"
    assert canonical_path("/dgacm/content/editorial-manual/updates") == base + "/updates"
    assert canonical_path("/dgacm/en/content/editorial-manual/Punctuation/") == base + "/punctuation"
    assert canonical_path("/dgacm/en/content/editorial-manual") == base
    assert canonical_path("/dgacm/en/content/other") is None
    assert slug_for(base) == "index"
    assert slug_for(base + "/footnotes/chap-04") == "footnotes/chap-04"


def test_index_groups():
    body = BeautifulSoup((FIX / "index.html").read_text(encoding="utf-8"), "lxml")
    groups = parse_index_groups(body, INDEX_URL)
    assert groups["spelling"] == ("Style", "Spelling (printer-friendly version)") or groups["spelling"][0] == "Style"
    assert groups["footnotes/index"][0] == "Editorial guidelines"
    assert {g for g, _ in groups.values()} >= {"Editorial guidelines", "Format", "Style", "Basic documents"}
