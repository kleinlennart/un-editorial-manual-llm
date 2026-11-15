from __future__ import annotations

import argparse
import sys

from . import ROOT


def cmd_fetch(args) -> int:
    from .fetch import Crawler

    crawler = Crawler(ROOT / "snapshots", delay=args.delay)
    result = crawler.crawl()
    for url in result["pdfs"]:
        if "spell_print" in url:
            path = crawler.download_pdf(url, ROOT / "snapshots" / "pdf")
            print(f"pdf {path.name}")
    print(f"{len(result['pages'])} pages, {len(result['pdfs'])} PDFs, {len(result['errors'])} errors")
    for e in result["errors"]:
        print("ERROR", e, file=sys.stderr)
    return 1 if result["errors"] else 0


def cmd_build(args) -> int:
    from . import llmstxt, updates_log
    from .build import build

    manifest = build(ROOT)
    upd = manifest.by_slug().get("updates")
    if upd:
        entries = updates_log.write(
            ROOT / "snapshots" / "html" / "updates.html", upd.source_url, ROOT / "data" / "updates.json"
        )
        print(f"{len(entries)} update-log entries")
    llmstxt.write(manifest, ROOT / "content", ROOT)
    print(f"{len(manifest.pages)} pages in {len(manifest.groups)} groups; last change {manifest.last_changed()}")
    return 0


def cmd_validate(args) -> int:
    from .validate import validate

    report = validate(ROOT, use_git=not args.no_git)
    for w in report.warnings:
        print("warning:", w)
    for e in report.errors:
        print("ERROR:", e, file=sys.stderr)
    print("validation", "passed" if report.ok else "FAILED")
    return 0 if report.ok else 1


def cmd_sync(args) -> int:
    rc = cmd_fetch(args)
    if rc:
        return rc
    cmd_build(args)
    return cmd_validate(args)


def cmd_site(args) -> int:
    from .site import render, stage

    stage(ROOT)
    if args.render:
        out = render(ROOT)
        print(f"rendered site to {out.relative_to(ROOT)}")
    else:
        print("staged site inputs; preview with: quarto preview site")
    return 0


def cmd_pr_body(args) -> int:
    from .prbody import pr_body

    print(pr_body(ROOT))
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="unem", description="UN Editorial Manual for LLMs")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("fetch", help="crawl un.org and snapshot body HTML (+ spelling PDF)")
    p.add_argument("--delay", type=float, default=10.0)
    p.set_defaults(func=cmd_fetch)

    sub.add_parser("build", help="offline: snapshots → content, manifest, llms.txt").set_defaults(func=cmd_build)

    p = sub.add_parser("validate", help="validation gate")
    p.add_argument("--no-git", action="store_true", help="skip comparison with HEAD manifest")
    p.set_defaults(func=cmd_validate)

    p = sub.add_parser("sync", help="fetch + build + validate")
    p.add_argument("--delay", type=float, default=10.0)
    p.add_argument("--no-git", action="store_true")
    p.set_defaults(func=cmd_sync)

    p = sub.add_parser("site", help="stage Quarto site inputs (and optionally render)")
    p.add_argument("--render", action="store_true", help="quarto render + copy raw .md and llms files")
    p.set_defaults(func=cmd_site)
    sub.add_parser("pr-body", help="markdown summary of changes vs HEAD").set_defaults(func=cmd_pr_body)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
