from pathlib import Path

from unem.updates_log import parse

FIX = Path(__file__).parent / "fixtures" / "html" / "updates.html"
URL = "https://www.un.org/dgacm/content/editorial-manual/updates"


def test_years_inferred_and_ordered():
    entries = parse(FIX.read_text(encoding="utf-8"), URL)
    assert len(entries) > 100
    dates = [e["date"] for e in entries]
    assert dates == sorted(dates, reverse=True), "log must be reverse chronological"
    first = entries[0]
    assert first["date"].endswith("-10-23")
    assert first["slug"] == "abbreviations"
    assert "GNI" in first["change"]
