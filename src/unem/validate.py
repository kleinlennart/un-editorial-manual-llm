"""Validation gate: refuse to publish a broken or truncated mirror."""

from __future__ import annotations

import json
import re
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import unquote

from . import ROOT
from .build import index_groups, load_crawl
from .manifest import Manifest

SHRINK_LIMIT = 0.30
LINK_RE = re.compile(r"\]\(([^)\s]+)\)")
ANCHOR_DEF_RE = re.compile(r'\{#([^}]+)\}|<a id="([^"]+)"></a>')


@dataclass
class Report:
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.errors


def previous_manifest(root: Path) -> Manifest | None:
    """The manifest as committed at HEAD (the last reviewed state)."""
    try:
        raw = subprocess.run(
            ["git", "show", "HEAD:manifest.json"], cwd=root, capture_output=True, text=True, check=True
        ).stdout
    except (subprocess.CalledProcessError, FileNotFoundError):
        return None
    d = json.loads(raw)
    from .manifest import Page

    d["pages"] = [Page(**p) for p in d["pages"]]
    return Manifest(**d)


def spelling_entries_md(md: str) -> int:
    return sum(1 for line in md.splitlines() if re.match(r"^\s*- \S", line))


def spelling_entries_pdf(pdf: Path) -> int:
    from pypdf import PdfReader

    text = "\n".join(page.extract_text() or "" for page in PdfReader(str(pdf)).pages)
    lines = [l.strip() for l in text.splitlines()]
    # Entry lines: start with a letter, *, or digit; skip single-letter section headers and page furniture.
    return sum(1 for l in lines if len(l) > 1 and re.match(r"^[\*A-Za-z0-9\"“(]", l))


def validate(root: Path = ROOT, previous: Manifest | None = None, use_git: bool = True) -> Report:
    r = Report()
    crawl = load_crawl(root / "snapshots")
    for e in crawl.get("errors", []):
        r.errors.append(f"fetch: {e}")

    manifest = Manifest.load(root / "manifest.json")
    if manifest is None:
        r.errors.append("manifest.json missing")
        return r
    pages = manifest.by_slug()

    # Every section linked from the index must be mirrored.
    _, mapping = index_groups(root / "snapshots")
    for slug in mapping:
        if slug not in pages:
            r.errors.append(f"missing section from index: {slug}")

    # Compare with the last reviewed state.
    prev = previous if previous is not None else (previous_manifest(root) if use_git else None)
    if prev is not None:
        if len(manifest.pages) < len(prev.pages):
            gone = sorted(set(prev.by_slug()) - set(pages))
            r.errors.append(f"page count dropped {len(prev.pages)} → {len(manifest.pages)}: {gone}")
        for slug, old in prev.by_slug().items():
            new = pages.get(slug)
            if new and old.chars and new.chars < old.chars * (1 - SHRINK_LIMIT):
                r.errors.append(f"{slug} shrank {old.chars} → {new.chars} chars (>{int(SHRINK_LIMIT*100)}%)")

    # Links.
    content_root = root / "content"
    anchors: dict[str, set[str]] = {}
    for p in manifest.pages:
        text = (content_root / p.path).read_text(encoding="utf-8")
        anchors[p.path] = {a or b for a, b in ANCHOR_DEF_RE.findall(text)}
    for p in manifest.pages:
        text = (content_root / p.path).read_text(encoding="utf-8")
        for href in LINK_RE.findall(text):
            if re.match(r"^[a-z]+:", href):
                if "/content/editorial-manual" in href:
                    r.warnings.append(f"{p.slug}: link to un.org manual page not in mirror: {href}")
                continue
            target, _, frag = href.partition("#")
            frag = unquote(frag)
            tpath = (Path(p.path).parent / target).as_posix() if target else p.path
            tpath = str(Path(tpath)).replace("\\", "/")
            # normalise ../
            parts: list[str] = []
            for part in tpath.split("/"):
                if part == "..":
                    parts.pop() if parts else None
                elif part not in ("", "."):
                    parts.append(part)
            tpath = "/".join(parts)
            if not (content_root / tpath).exists():
                r.errors.append(f"{p.slug}: broken link {href}")
            elif frag and frag not in anchors.get(tpath, set()):
                r.warnings.append(f"{p.slug}: anchor not found {href}")

    # Spelling list vs printer-friendly PDF.
    spelling = pages.get("spelling")
    pdfs = sorted((root / "snapshots" / "pdf").glob("spell_print*.pdf"))
    if spelling and pdfs:
        n_md = spelling_entries_md((content_root / spelling.path).read_text(encoding="utf-8"))
        n_pdf = spelling_entries_pdf(pdfs[-1])
        ratio = n_md / n_pdf if n_pdf else 0
        msg = f"spelling entries: mirror={n_md} pdf≈{n_pdf} (ratio {ratio:.2f})"
        if not 0.8 <= ratio <= 1.25:
            r.errors.append(msg)
        else:
            r.warnings.append(msg)
    elif spelling:
        r.warnings.append("spelling PDF not downloaded; count cross-check skipped")
    return r
