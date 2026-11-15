"""Generate llms.txt and llms-full.txt from the manifest (https://llmstxt.org/)."""

from __future__ import annotations

from pathlib import Path

from .manifest import Manifest

SITE_URL = "https://kleinlennart.github.io/un-editorial-manual-llm/"

DISCLAIMER = (
    "Unofficial resource. Not produced or endorsed by the United Nations. "
    "Content reproduced from the United Nations Editorial Manual "
    "(un.org/dgacm/en/content/editorial-manual), © United Nations. Always check the source."
)

SUMMARY = (
    "Markdown mirror of the United Nations Editorial Manual Online, the authoritative "
    "statement of the style to be followed in drafting, editing and reproducing United "
    "Nations documents, publications and other written material (spelling, capitalization, "
    "abbreviations, numbers, footnotes, document formats)."
)

# Pages listed under "## Optional": useful context that can be skipped for a shorter prompt.
OPTIONAL_SLUGS = {"updates", "abouteditors", "contact", "index"}


def _md_url(path: str, base: str) -> str:
    return base.rstrip("/") + "/" + path


def build_llms_txt(manifest: Manifest, base: str = SITE_URL) -> str:
    lines = [
        "# United Nations Editorial Manual",
        "",
        f"> {SUMMARY} {DISCLAIMER}",
        "",
        "Usage notes:",
        "",
        "- Each link points to a verbatim Markdown copy of one manual page; the `source_url` in its front matter is the canonical un.org page.",
        "- The online Oxford Dictionary (British English) is the spelling authority; the Spelling page lists United Nations preferences and exceptions.",
        f"- Mirror of the English manual. Last upstream content change: {manifest.last_changed()}.",
        f"- All pages in one file: [llms-full.txt]({_md_url('llms-full.txt', base)})",
        "",
    ]
    listed: set[str] = set()
    for group in manifest.groups:
        pages = [p for p in manifest.pages_in_group(group) if p.slug not in OPTIONAL_SLUGS]
        if not pages:
            continue
        lines.append(f"## {group}")
        lines.append("")
        for p in pages:
            desc = f": {p.description}" if p.description else ""
            lines.append(f"- [{p.title}]({_md_url(p.path, base)}){desc}")
            listed.add(p.slug)
        lines.append("")
    optional = [p for p in manifest.pages if p.slug not in listed]
    if optional:
        lines.append("## Optional")
        lines.append("")
        for p in optional:
            desc = f": {p.description}" if p.description else ""
            lines.append(f"- [{p.title}]({_md_url(p.path, base)}){desc}")
        lines.append("")
    return "\n".join(lines)


def build_llms_full(manifest: Manifest, content_root: Path) -> str:
    parts = [
        "# United Nations Editorial Manual (full text)",
        "",
        f"> {SUMMARY} {DISCLAIMER}",
        "",
    ]
    for p in manifest.ordered_pages():
        body = Manifest.strip_front_matter((content_root / p.path).read_text(encoding="utf-8"))
        parts.append("---")
        parts.append("")
        parts.append(f"<!-- page: {p.slug} | source: {p.source_url} | last_changed: {p.last_changed} -->")
        parts.append("")
        parts.append(body.strip())
        parts.append("")
    return "\n".join(parts)


def write(manifest: Manifest, content_root: Path, out_dir: Path, base: str = SITE_URL) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "llms.txt").write_text(build_llms_txt(manifest, base), encoding="utf-8")
    (out_dir / "llms-full.txt").write_text(build_llms_full(manifest, content_root), encoding="utf-8")
