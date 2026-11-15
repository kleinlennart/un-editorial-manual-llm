"""Crawl the UN Editorial Manual Online and snapshot each page's body HTML.

Only the main content region (``.field-name-body``) is stored, so snapshot
diffs reflect content changes rather than volatile page chrome.
"""

from __future__ import annotations

import hashlib
import json
import re
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from urllib.parse import urljoin, urlparse, urlunparse

import httpx
from bs4 import BeautifulSoup

ORIGIN = "https://www.un.org"
BASE_PATH = "/dgacm/en/content/editorial-manual"
INDEX_URL = ORIGIN + BASE_PATH
# robots.txt asks for Crawl-delay: 10
CRAWL_DELAY = 10.0
USER_AGENT = "Mozilla/5.0 (compatible; un-editorial-manual-llm/0.1; +https://github.com/kleinlennart/un-editorial-manual-llm)"
PDF_DIR_MARKER = "/Documents_Editorial_manual/"
BODY_SELECTOR = ".field-name-body .field-item"


@dataclass
class FetchedPage:
    slug: str
    url: str
    status: int
    title: str
    group: str | None
    body_sha256: str
    links: list[str] = field(default_factory=list)


def canonical_path(path: str) -> str | None:
    """Map a URL path to the canonical ``/dgacm/en/content/editorial-manual/...`` form.

    Returns None for paths outside the manual.
    """
    # The server is case-insensitive and pages link to e.g. both "Punctuation" and
    # "punctuation"; lower-case to avoid duplicates (and collisions on macOS filesystems).
    path = path.rstrip("/").lower()
    path = re.sub(r"^/dgacm/content/editorial-manual", BASE_PATH, path)
    if path == BASE_PATH or path.startswith(BASE_PATH + "/"):
        return path
    return None


def slug_for(path: str) -> str:
    rest = path[len(BASE_PATH):].strip("/")
    return rest or "index"


def normalize_link(href: str, page_url: str) -> str:
    absolute = urljoin(page_url, href.strip())
    p = urlparse(absolute)
    return urlunparse((p.scheme, p.netloc, p.path, "", "", ""))


def extract_body(html: str) -> BeautifulSoup | None:
    soup = BeautifulSoup(html, "lxml")
    return soup.select_one(BODY_SELECTOR)


def parse_index_groups(body: BeautifulSoup, page_url: str) -> dict[str, tuple[str, str]]:
    """From the index page, map slug -> (group heading, link text)."""
    groups: dict[str, tuple[str, str]] = {}
    for h2 in body.select("h2.blue-line-title"):
        group = " ".join(h2.get_text(" ", strip=True).split())
        cell = h2.find_parent("td") or h2.parent
        for a in cell.select("ul a[href]"):
            url = normalize_link(a["href"], page_url)
            p = urlparse(url)
            if p.netloc and p.netloc != "www.un.org":
                continue
            cp = canonical_path(p.path)
            if cp is None:
                continue
            title = " ".join(a.get_text(" ", strip=True).replace("\xa0", " ").split())
            groups.setdefault(slug_for(cp), (group, title))
    return groups


class Crawler:
    def __init__(self, out_dir: Path, delay: float = CRAWL_DELAY, client: httpx.Client | None = None):
        self.out_dir = out_dir
        self.delay = delay
        self.client = client or httpx.Client(
            headers={"User-Agent": USER_AGENT}, follow_redirects=True, timeout=60
        )
        self._last = 0.0

    def get(self, url: str) -> httpx.Response:
        wait = self.delay - (time.monotonic() - self._last)
        if wait > 0:
            time.sleep(wait)
        try:
            return self.client.get(url)
        finally:
            self._last = time.monotonic()

    def fetch_page(self, path: str) -> tuple[httpx.Response, str]:
        """Fetch a canonical path; fall back to the language-less URL (used by e.g. /updates)."""
        url = ORIGIN + path
        r = self.get(url)
        if r.status_code == 404:
            alt = ORIGIN + path.replace("/dgacm/en/", "/dgacm/", 1)
            r = self.get(alt)
            url = alt
        return r, url

    def crawl(self, log=print) -> dict:
        html_dir = self.out_dir / "html"
        html_dir.mkdir(parents=True, exist_ok=True)
        queue = [BASE_PATH]
        seen: set[str] = set()
        pages: list[FetchedPage] = []
        pdfs: set[str] = set()
        groups: dict[str, tuple[str, str]] = {}
        errors: list[str] = []

        while queue:
            path = queue.pop(0)
            if path in seen:
                continue
            seen.add(path)
            slug = slug_for(path)
            r, url = self.fetch_page(path)
            log(f"{r.status_code} {slug}")
            if r.status_code != 200:
                errors.append(f"{r.status_code} {url}")
                continue
            body = extract_body(r.text)
            if body is None:
                errors.append(f"no body region: {url}")
                continue
            if slug == "index":
                groups = parse_index_groups(body, url)

            links: list[str] = []
            for a in body.select("a[href]"):
                href = a["href"]
                if href.startswith(("mailto:", "#", "javascript:")):
                    continue
                link = normalize_link(href, url)
                p = urlparse(link)
                if p.netloc == "www.un.org" and PDF_DIR_MARKER in p.path and p.path.lower().endswith(".pdf"):
                    pdfs.add(link)
                    continue
                if p.netloc != "www.un.org":
                    continue
                cp = canonical_path(p.path)
                if cp and cp not in seen:
                    queue.append(cp)
                    links.append(slug_for(cp))

            body_html = body.decode_contents().strip() + "\n"
            target = html_dir / f"{slug}.html"
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(body_html, encoding="utf-8")
            page_title = BeautifulSoup(r.text, "lxml").title
            pages.append(
                FetchedPage(
                    slug=slug,
                    url=url,
                    status=r.status_code,
                    title=(page_title.get_text(strip=True) if page_title else slug),
                    group=None,
                    body_sha256=hashlib.sha256(body_html.encode()).hexdigest(),
                    links=sorted(set(links)),
                )
            )

        for p in pages:
            if p.slug in groups:
                p.group, p.title = groups[p.slug]

        result = {
            "index_url": INDEX_URL,
            "pages": [asdict(p) for p in sorted(pages, key=lambda p: p.slug)],
            "pdfs": sorted(pdfs),
            "errors": errors,
        }
        (self.out_dir / "crawl.json").write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n")
        return result

    def download_pdf(self, url: str, dest_dir: Path) -> Path:
        dest_dir.mkdir(parents=True, exist_ok=True)
        r = self.get(url)
        r.raise_for_status()
        dest = dest_dir / Path(urlparse(url).path).name
        dest.write_bytes(r.content)
        return dest
