"""Deterministic HTML → Markdown conversion of manual pages.

No LLM is involved. The same snapshot always yields byte-identical Markdown.
"""

from __future__ import annotations

import posixpath
import re
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup, NavigableString, Tag
from markdownify import MarkdownConverter

from .fetch import ORIGIN, canonical_path, slug_for

ANCHOR_TOKEN = "\u27e6anchor:{}\u27e7"  # ⟦anchor:x⟧, swapped for real anchors after markdownify
ANCHOR_RE = re.compile("\u27e6anchor:([^\u27e7]+)\u27e7")
ICON_MARKER = "/images/icons/"
BLOCK_TAGS = {"p", "div", "ul", "ol", "table", "h1", "h2", "h3", "h4", "h5", "h6", "blockquote"}


class _MD(MarkdownConverter):
    def convert_img(self, el, text, parent_tags):  # keep images, absolute URLs set beforehand
        alt = el.attrs.get("alt", "") or ""
        src = el.attrs.get("src", "")
        return f"![{alt}]({src})"


def _md(html: str | Tag) -> str:
    return _MD(
        heading_style="ATX",
        bullets="-",
        strong_em_symbol="*",
        escape_underscores=False,
        newline_style="BACKSLASH",
    ).convert(str(html))


def _text(el: Tag) -> str:
    return " ".join(el.get_text(" ", strip=True).replace("\xa0", " ").split())


# ---------------------------------------------------------------------------
# link handling


def rewrite_href(href: str, page_url: str, cur_slug: str, known: set[str]) -> str:
    href = href.strip()
    if href.startswith(("mailto:", "#")):
        return href
    absolute = urljoin(page_url, href)
    p = urlparse(absolute)
    if p.netloc in ("www.un.org", "un.org"):
        cp = canonical_path(p.path)
        if cp is not None:
            target = slug_for(cp)
            if target in known:
                rel = posixpath.relpath(target + ".md", posixpath.dirname(cur_slug) or ".")
                return rel + (f"#{p.fragment}" if p.fragment else "")
        return "https://www.un.org" + p.path + (f"?{p.query}" if p.query else "") + (f"#{p.fragment}" if p.fragment else "")
    return absolute


# ---------------------------------------------------------------------------
# tables


def _cell_lines(cell: Tag) -> list[tuple[int, str]]:
    """Split a layout cell into (indent_level, inline_html) lines on <br> and block boundaries."""
    lines: list[tuple[int, str]] = []
    buf: list[str] = []

    def flush():
        raw = "".join(buf)
        buf.clear()
        lead = re.match(r"^[\s\xa0]*", raw.replace("&nbsp;", "\xa0")).group(0)
        nbsp = lead.count("\xa0")
        level = 0 if nbsp == 0 else (1 if nbsp < 10 else 2)
        html = raw.strip().replace("\xa0", " ").strip()
        if BeautifulSoup(html, "lxml").get_text(strip=True).replace("\xa0", ""):
            lines.append((level, html))

    def walk(node):
        for child in node.children:
            if isinstance(child, NavigableString):
                buf.append(str(child))
            elif child.name == "br":
                flush()
            elif child.name in BLOCK_TAGS:
                flush()
                walk(child)
                flush()
            else:
                buf.append(str(child))

    walk(cell)
    flush()
    return lines


def _lines_to_ul(lines: list[tuple[int, str]], soup: BeautifulSoup) -> Tag:
    root = soup.new_tag("ul")
    stack: list[tuple[int, Tag]] = [(0, root)]
    last_li: Tag | None = None
    for level, html in lines:
        while len(stack) > 1 and level < stack[-1][0]:
            stack.pop()
        if level > stack[-1][0] and last_li is not None:
            sub = soup.new_tag("ul")
            last_li.append(sub)
            stack.append((level, sub))
        li = soup.new_tag("li")
        li.append(BeautifulSoup(html, "html.parser"))
        stack[-1][1].append(li)
        last_li = li
    return root


def classify_table(table: Tag) -> str:
    rows = table.find_all("tr")
    cells = table.find_all(["td", "th"])
    imgs = table.find_all("img")
    if len(rows) == 1 and any(ICON_MARKER in (i.get("src") or "") for i in imgs):
        return "callout"
    if table.find("th") is None and not imgs:
        nonempty = [c for c in cells if _text(c)]
        if nonempty and all(len(c.find_all("br")) >= 5 for c in nonempty):
            return "list"
    return "data"


def table_to_markdown(table: Tag) -> str:
    rows = []
    for tr in table.find_all("tr"):
        cells = []
        for c in tr.find_all(["td", "th"], recursive=False):
            md = _md(c.decode_contents()).strip()
            md = re.sub(r"\\?\n+", "<br>", md).replace("|", "\\|")
            cells.append(md)
            span = int(c.get("colspan", 1) or 1)
            cells.extend([""] * (span - 1))
        if any(x.strip() for x in cells):
            rows.append(cells)
    if not rows:
        return ""
    width = max(len(r) for r in rows)
    rows = [r + [""] * (width - len(r)) for r in rows]
    first = table.find("tr")
    header_cells = first.find_all(["td", "th"], recursive=False) if first else []
    has_header = bool(header_cells) and all(
        c.name == "th" or (c.find(["strong", "b"]) and _text(c.find(["strong", "b"])) == _text(c)) for c in header_cells if _text(c)
    ) and len(rows) > 1
    if has_header:
        header, body = rows[0], rows[1:]
    else:
        header, body = [""] * width, rows
    out = ["| " + " | ".join(header) + " |", "|" + "|".join(["---"] * width) + "|"]
    out += ["| " + " | ".join(r) + " |" for r in body]
    return "\n".join(out)


# ---------------------------------------------------------------------------
# page conversion


def convert_page(body_html: str, slug: str, page_url: str, known: set[str]) -> tuple[str, str]:
    """Return (heading, markdown_body). heading is the page's own section heading."""
    soup = BeautifulSoup(body_html, "lxml")
    body = soup.body or soup

    # Boilerplate H1: "Editorial Manual" or "Editorial Manual | <section>".
    suffix = ""
    h1 = body.find("h1")
    if h1 is not None and _text(h1).lower().startswith("editorial manual"):
        suffix = _text(h1).partition("|")[2].strip()
        h1.decompose()

    # Page heading: the first H2, unless the H1 already names the section (then H2s
    # are real sub-sections) or the H2 is a link to another page (a table of contents).
    # Chapter pages (footnotes/chap-NN) are titled by their own H2.
    heading = suffix
    is_chapter = "/" in slug and not slug.endswith("/index")
    h2 = body.find("h2")
    if h2 is not None and not h2.find("a", href=True) and (not suffix or is_chapter):
        heading = _text(h2)
        h2.decompose()

    # In-page navigation chrome: A–Z letter bars, "TOP" links, jump-link TOCs.
    for p in body.find_all(["p", "div"]):
        if p.find_parent("table") is not None or p.find(["table", "ul", "ol"]):
            continue
        links = p.find_all("a", href=True)
        if links and all(a["href"].startswith("#") for a in links):
            residue = _text(p)
            for a in links:
                residue = residue.replace(_text(a), " ", 1)
            residue = re.sub(r"\b[A-Z]\b", "", residue)  # unlinked letters (e.g. "Q  X  Y  Z")
            if len(residue.strip(" *|-–")) <= 3:
                p.decompose()

    # Visual indentation with &nbsp; runs would become Markdown code blocks: trim it
    # (outside list-layout tables, where indentation is turned into list nesting).
    for p in body.find_all(["p", "li", "td", "h2", "h3", "h4"]):
        if p.name == "td" and classify_table(p.find_parent("table")) == "list":
            continue
        first = next((s for s in p.descendants if isinstance(s, NavigableString)), None)
        if first is not None and first.find_parent("table") is p.find_parent("table"):
            stripped = first.lstrip(" \t\n\xa0")
            if stripped != first:
                first.replace_with(NavigableString(stripped))

    # Classify tables while decorative icons are still present.
    for table in body.find_all("table"):
        table["data-kind"] = classify_table(table)

    # Strip presentational wrappers.
    for t in body.find_all(["span", "font", "o:p"]):
        t.unwrap()
    for t in body.find_all(True):
        for attr in ("style", "class", "align", "cellpadding", "cellspacing", "width", "height", "target", "border"):
            t.attrs.pop(attr, None)

    # Decorative icons.
    for img in body.find_all("img"):
        src = img.get("src", "")
        if ICON_MARKER in src:
            img.decompose()
        else:
            img["src"] = urljoin(page_url, src).replace("http://", "https://", 1)

    # Anchors -> tokens (resolved after markdownify).
    for a in body.find_all("a"):
        aid = a.get("id") or a.get("name")
        if aid and not a.get("href"):
            text = a.get_text()
            a.replace_with(NavigableString(ANCHOR_TOKEN.format(aid) + text))
        elif a.get("href", "").strip().lower().startswith("file:"):
            a.unwrap()  # broken links to an editor's local disk upstream: keep the text only
        elif a.get("href"):
            a["href"] = rewrite_href(a["href"], page_url, slug, known)
            a.attrs = {"href": a["href"]}
    for el in body.find_all(attrs={"id": True}):
        if el.name not in ("a",) and el.name in ("h2", "h3", "h4", "p"):
            el.insert(0, NavigableString(ANCHOR_TOKEN.format(el["id"])))

    # Tables.
    placeholders: dict[str, str] = {}
    for i, table in enumerate(body.find_all("table")):
        if table.find_parent("table") is not None:
            continue
        kind = table.get("data-kind") or classify_table(table)
        if kind == "list":
            lines = []
            for cell in table.find_all(["td", "th"]):
                lines.extend(_cell_lines(cell))
            table.replace_with(_lines_to_ul(lines, soup))
        elif kind == "callout":
            bq = soup.new_tag("blockquote")
            for cell in table.find_all(["td", "th"]):
                if _text(cell):
                    for child in list(cell.children):
                        bq.append(child.extract())
            table.replace_with(bq)
        else:
            key = f"TABLEPLACEHOLDER{i}X"
            placeholders[key] = table_to_markdown(table)
            p = soup.new_tag("p")
            p.string = key
            table.replace_with(p)

    md = _md(body.decode_contents())

    for key, val in placeholders.items():
        md = md.replace(key, "\n" + val + "\n")

    md = _finish(md)
    return heading, md


def _finish(md: str) -> str:
    md = md.replace("\xa0", " ")
    lines = []
    in_list = False
    for line in md.splitlines():
        line = line.rstrip()
        m = re.match(r"^(#{1,6} )(.*)$", line)
        if m:
            ids = ANCHOR_RE.findall(line)
            text = " ".join(ANCHOR_RE.sub("", m.group(2)).split())
            text = re.sub(r"^\*\*(.+?)\*\*$", r"\1", text).strip()  # headings are bold already
            line = m.group(1) + text + (f" {{#{ids[0]}}}" if ids else "")
            if not text:
                line = "".join(f'<a id="{i}"></a>' for i in ids)
        else:
            line = ANCHOR_RE.sub(lambda mm: f'<a id="{mm.group(1)}"></a>', line)
        # Indented prose (from &nbsp; after <br>) outside lists would render as code.
        # Only list items emitted by markdownify (unindented at top level) open a list
        # context; visually indented pseudo-items ("   1.  Organization") are flattened.
        if line.strip():
            if line[0] == " " and not in_list:
                line = line.lstrip()
            elif line[0] != " ":
                in_list = bool(re.match(r"^([-*+]|\d+\.)\s", line))
        # Drop lines that are only escaped/whitespace artefacts.
        if line.strip() in ("\\", "**", "* *"):
            line = ""
        lines.append(line)
    md = "\n".join(lines)
    md = re.sub(r"\n{3,}", "\n\n", md).strip() + "\n"
    return md


def first_sentence(md: str, limit: int = 180) -> str:
    """A short, verbatim description: the first prose sentence of the page."""
    for block in md.split("\n\n"):
        b = block.strip()
        if not b or b[0] in "#|-><!*[" or b.startswith("<a id"):
            continue
        plain = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", b)
        plain = re.sub(r"[*_`\\]", "", plain).replace("\n", " ")
        s = plain.strip()
        for m in re.finditer(r"[.:;](?=\s|$)", plain):
            head = plain[: m.end()]
            if re.search(r"\b(e\.g|i\.e|etc|No|Nos|para|paras|Mr|Ms|Dr|St|a\.i|vol|p|pp)\.$", head):
                continue
            s = head.strip()
            break
        if len(s) < 25:
            continue
        if len(s) > limit:
            s = s[: limit].rsplit(" ", 1)[0] + "…"
        return s
    return ""
