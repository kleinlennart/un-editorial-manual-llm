"""Offline build: snapshots → content/en/*.md → manifest.json → llms.txt."""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import yaml
from bs4 import BeautifulSoup

from . import ROOT
from .convert import convert_page, first_sentence
from .fetch import INDEX_URL, parse_index_groups
from .manifest import Manifest, Page, carry_dates

LANG = "en"
ABOUT_GROUP = "About the manual"


def load_crawl(snap: Path) -> dict:
    return json.loads((snap / "crawl.json").read_text(encoding="utf-8"))


def index_groups(snap: Path) -> tuple[list[str], dict[str, tuple[str, str]]]:
    body = BeautifulSoup((snap / "html" / "index.html").read_text(encoding="utf-8"), "lxml")
    mapping = parse_index_groups(body, INDEX_URL)
    groups: list[str] = []
    for g, _ in mapping.values():
        if g not in groups:
            groups.append(g)
    return groups, mapping


def front_matter(meta: dict) -> str:
    return "---\n" + yaml.safe_dump(meta, sort_keys=False, allow_unicode=True, width=1000) + "---\n\n"


def build(root: Path = ROOT, today: date | None = None) -> Manifest:
    today = today or date.today()
    snap = root / "snapshots"
    content_root = root / "content"
    out_dir = content_root / LANG
    crawl = load_crawl(snap)
    groups, mapping = index_groups(snap)
    groups = groups + [ABOUT_GROUP]
    known = {p["slug"] for p in crawl["pages"]}
    index_order = list(mapping.keys())

    # Pages not on the index inherit the group of their parent: the folder index
    # (footnotes/chap-NN → footnotes/index) or the first indexed page linking to them.
    hubs = {"index", "updates"}
    parent_of: dict[str, str] = {}
    for p in crawl["pages"]:
        s = p["slug"]
        if s in mapping:
            continue
        folder = s.rsplit("/", 1)[0] + "/index" if "/" in s else None
        if folder in mapping:
            parent_of[s] = folder
            continue
        for q in sorted(crawl["pages"], key=lambda q: index_order.index(q["slug"]) if q["slug"] in mapping else 10**6):
            if q["slug"] in mapping and q["slug"] not in hubs and s in q.get("links", []):
                parent_of[s] = q["slug"]
                break

    def sort_key(slug: str) -> tuple:
        if slug in mapping:
            return (index_order.index(slug), 0, slug)
        if slug in parent_of:
            return (index_order.index(parent_of[slug]), 1, slug)
        return (len(index_order), 0, slug)

    pages: list[Page] = []
    bodies: dict[str, str] = {}
    written: set[Path] = set()
    for cp in sorted(crawl["pages"], key=lambda p: sort_key(p["slug"])):
        slug = cp["slug"]
        html = (snap / "html" / f"{slug}.html").read_text(encoding="utf-8")
        heading, body = convert_page(html, slug, cp["url"], known)
        if slug in mapping:
            group, title = mapping[slug]
        else:
            parent = parent_of.get(slug)
            group = mapping[parent][0] if parent in mapping else ABOUT_GROUP
            title = heading or slug
        if slug == "index":
            title = "United Nations Editorial Manual Online"
        # Chapter pages (e.g. footnotes/chap-04) are titled "<section>: <chapter>".
        if "/" in slug and not slug.endswith("/index"):
            folder = slug.rsplit("/", 1)[0] + "/index"
            section = mapping[folder][1] if folder in mapping else ""
            title = f"{section}: {heading}" if section and heading else (heading or slug)
        md_body = f"# {title}\n\n{body}"
        sha = Manifest.hash_text(md_body)
        page = Page(
            slug=slug,
            title=title,
            group=group,
            source_url=cp["url"],
            path=f"{LANG}/{slug}.md",
            sha256=sha,
            last_changed="",
            chars=len(md_body),
            description=first_sentence(body),
        )
        pages.append(page)
        bodies[slug] = md_body

    previous = Manifest.load(root / "manifest.json")
    carry_dates(pages, previous, today)

    for page in pages:
        md_body_path = out_dir / f"{page.slug}.md"
        md_body_path.parent.mkdir(parents=True, exist_ok=True)
        meta = {
            "title": page.title,
            "group": page.group,
            "source_url": page.source_url,
            "last_changed": page.last_changed,
            "sha256": page.sha256,
            "disclaimer": "Unofficial mirror. © United Nations. Always check the source_url.",
        }
        md_body_path.write_text(front_matter(meta) + bodies[page.slug], encoding="utf-8")
        written.add(md_body_path)

    # Remove pages that disappeared upstream.
    for stale in out_dir.rglob("*.md"):
        if stale not in written:
            stale.unlink()

    used_groups = [g for g in groups if any(p.group == g for p in pages)]
    manifest = Manifest(language=LANG, index_url=INDEX_URL, groups=used_groups, pages=pages, pdfs=crawl["pdfs"])
    manifest.dump(root / "manifest.json")
    return manifest
