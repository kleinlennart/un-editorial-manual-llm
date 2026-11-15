"""Parse the manual's official updates log into structured, dated entries.

The log is one table in reverse chronological order. Year markers are rows whose
first cell is a bold four-digit year. Rows above the first marker belong to the
current year (marker year + 1).
"""

from __future__ import annotations

import json
import re
from datetime import date, datetime
from pathlib import Path

from bs4 import BeautifulSoup

from .convert import _md, rewrite_href
from .fetch import canonical_path, slug_for
from urllib.parse import urljoin, urlparse

YEAR_RE = re.compile(r"^(19|20)\d{2}$")
DATE_RE = re.compile(r"^(\d{1,2})\s+([A-Za-z]+)$")


def _clean(s: str) -> str:
    return " ".join(s.replace("\xa0", " ").split())


def parse(html: str, page_url: str) -> list[dict]:
    soup = BeautifulSoup(html, "lxml")
    table = soup.find("table")
    if table is None:
        return []
    rows = table.find_all("tr")
    first_year = next(
        (int(_clean(r.find(["td", "th"]).get_text())) for r in rows
         if r.find(["td", "th"]) and YEAR_RE.match(_clean(r.find(["td", "th"]).get_text()))),
        None,
    )
    year = (first_year + 1) if first_year else None
    entries: list[dict] = []
    for tr in rows:
        cells = tr.find_all(["td", "th"], recursive=False)
        if not cells:
            continue
        first = _clean(cells[0].get_text())
        if YEAR_RE.match(first):
            year = int(first)
            continue
        m = DATE_RE.match(first)
        if not m or year is None or len(cells) < 3:
            continue
        try:
            d = datetime.strptime(f"{m.group(1)} {m.group(2)} {year}", "%d %B %Y").date()
        except ValueError:
            continue
        a = cells[1].find("a", href=True)
        slug = anchor = None
        if a:
            u = urlparse(urljoin(page_url, a["href"]))
            cp = canonical_path(u.path)
            if cp:
                slug = slug_for(cp)
                anchor = u.fragment or None
        change = re.sub(r"\\?\n+", " ", _md(cells[2].decode_contents())).strip()
        entries.append({
            "date": d.isoformat(),
            "page": _clean(cells[1].get_text()),
            "slug": slug,
            "anchor": anchor,
            "change": change,
        })
    return entries


def write(snapshot: Path, page_url: str, out: Path) -> list[dict]:
    entries = parse(snapshot.read_text(encoding="utf-8"), page_url)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(entries, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return entries


def entries_for(entries: list[dict], slugs: set[str], since: str | None = None) -> list[dict]:
    return [e for e in entries if e["slug"] in slugs and (since is None or e["date"] >= since)]
