"""Markdown PR body for the weekly sync: what changed, and what the official log says."""

from __future__ import annotations

import json
from pathlib import Path

from .manifest import Manifest
from .validate import previous_manifest, validate


def pr_body(root: Path) -> str:
    new = Manifest.load(root / "manifest.json")
    old = previous_manifest(root)
    if new is None:
        return "manifest.json missing"
    newp = new.by_slug()
    oldp = old.by_slug() if old else {}
    added = sorted(set(newp) - set(oldp))
    removed = sorted(set(oldp) - set(newp))
    changed = sorted(s for s in set(newp) & set(oldp) if newp[s].sha256 != oldp[s].sha256)

    log_path = root / "data" / "updates.json"
    log = json.loads(log_path.read_text(encoding="utf-8")) if log_path.exists() else []
    old_log = {(e["date"], e["page"], e["change"]) for e in _old_log(root)}
    new_log = [e for e in log if (e["date"], e["page"], e["change"]) not in old_log]

    out = ["## Upstream changes to the UN Editorial Manual", ""]
    if not (added or removed or changed):
        out.append("No content changes.")
    for label, slugs in (("Added", added), ("Changed", changed), ("Removed", removed)):
        if slugs:
            out.append(f"**{label}:**")
            for s in slugs:
                p = newp.get(s) or oldp[s]
                old_chars = oldp[s].chars if s in oldp else 0
                new_chars = newp[s].chars if s in newp else 0
                out.append(f"- `{s}`: {p.title} ([source]({p.source_url})) {old_chars} → {new_chars} chars")
            out.append("")
    if new_log:
        out += ["### New entries in the official updates log", "", "| Date | Page | Change |", "|---|---|---|"]
        for e in new_log:
            out.append(f"| {e['date']} | {e['page']} | {e['change'].replace('|', '\\|')} |")
        out.append("")

    report = validate(root)
    out.append("### Validation")
    out.append("")
    out.append("✅ passed" if report.ok else "❌ FAILED")
    for e in report.errors:
        out.append(f"- ERROR: {e}")
    if report.warnings:
        out.append("")
        out.append("<details><summary>Warnings</summary>")
        out.append("")
        out += [f"- {w}" for w in report.warnings]
        out.append("")
        out.append("</details>")
    out += ["", "Review the content diff, then merge to publish (site, llms.txt)."]
    return "\n".join(out)


def _old_log(root: Path) -> list[dict]:
    import subprocess

    try:
        raw = subprocess.run(
            ["git", "show", "HEAD:data/updates.json"], cwd=root, capture_output=True, text=True, check=True
        ).stdout
        return json.loads(raw)
    except Exception:
        return []
