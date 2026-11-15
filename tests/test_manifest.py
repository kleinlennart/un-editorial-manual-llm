from datetime import date

from unem.manifest import Manifest, Page, carry_dates


def _page(slug, sha):
    return Page(slug=slug, title=slug, group="g", source_url="u", path=f"en/{slug}.md", sha256=sha, last_changed="", chars=1)


def test_carry_dates_only_changes_on_hash_change():
    old_pages = [_page("a", "h1"), _page("b", "h2")]
    for p in old_pages:
        p.last_changed = "2026-01-01"
    prev = Manifest(language="en", index_url="", groups=["g"], pages=old_pages)
    new = [_page("a", "h1"), _page("b", "CHANGED"), _page("c", "h3")]
    carry_dates(new, prev, date(2026, 11, 15))
    assert [p.last_changed for p in new] == ["2026-01-01", "2026-11-15", "2026-11-15"]


def test_strip_front_matter():
    assert Manifest.strip_front_matter("---\ntitle: x\n---\n\n# X\n") == "\n# X\n"
