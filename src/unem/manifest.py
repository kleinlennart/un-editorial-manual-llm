"""Manifest of mirrored pages: the single index every downstream artefact reads."""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, field
from datetime import date
from pathlib import Path


@dataclass
class Page:
    slug: str
    title: str
    group: str
    source_url: str
    path: str  # relative to content root, e.g. "en/spelling.md"
    sha256: str
    last_changed: str
    chars: int
    description: str = ""


@dataclass
class Manifest:
    language: str
    index_url: str
    groups: list[str]
    pages: list[Page]
    pdfs: list[str] = field(default_factory=list)

    # ---- io ---------------------------------------------------------------
    @classmethod
    def load(cls, path: Path) -> "Manifest | None":
        if not path.exists():
            return None
        d = json.loads(path.read_text(encoding="utf-8"))
        d["pages"] = [Page(**p) for p in d["pages"]]
        return cls(**d)

    def dump(self, path: Path) -> None:
        d = asdict(self)
        path.write_text(json.dumps(d, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    # ---- queries ----------------------------------------------------------
    def by_slug(self) -> dict[str, Page]:
        return {p.slug: p for p in self.pages}

    def pages_in_group(self, group: str) -> list[Page]:
        return [p for p in self.pages if p.group == group]

    def ordered_pages(self) -> list[Page]:
        """Pages in manual order: by group, then the order they were added."""
        order = {g: i for i, g in enumerate(self.groups)}
        return sorted(self.pages, key=lambda p: order.get(p.group, len(order)))

    def last_changed(self) -> str:
        return max((p.last_changed for p in self.pages), default="")

    # ---- helpers ----------------------------------------------------------
    @staticmethod
    def hash_text(text: str) -> str:
        return hashlib.sha256(text.encode("utf-8")).hexdigest()

    @staticmethod
    def strip_front_matter(text: str) -> str:
        if text.startswith("---\n"):
            end = text.find("\n---\n", 4)
            if end != -1:
                return text[end + 5 :]
        return text


def carry_dates(new_pages: list[Page], previous: Manifest | None, today: date) -> None:
    """Keep last_changed for pages whose content hash is unchanged (avoids no-op diffs)."""
    prev = previous.by_slug() if previous else {}
    for p in new_pages:
        old = prev.get(p.slug)
        p.last_changed = old.last_changed if old and old.sha256 == p.sha256 else today.isoformat()
