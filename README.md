# un-editorial-manual-llm

The **United Nations Editorial Manual**, made usable by LLMs and AI agents. It provides:

- a verbatim Markdown mirror;
- [`llms.txt`](llms.txt) and [`llms-full.txt`](llms-full.txt);
- an Agent Skill (planned);
- a Microsoft Copilot kit (planned);
- a style linter (planned);
- an MCP server (planned).

> **Unofficial resource.** Not produced or endorsed by the United Nations. Content reproduced from the [United Nations Editorial Manual](https://www.un.org/dgacm/en/content/editorial-manual), © United Nations. Always check the source.

## What's here

| Path | What it is |
|---|---|
| [`content/en/`](content/en/) | One Markdown file per manual page, converted deterministically (no LLM) from un.org. The front matter holds `source_url`, `sha256` and `last_changed`. |
| [`manifest.json`](manifest.json) | Index of all pages (group, title, source URL, hash, last change). Every other output is generated from it. |
| [`llms.txt`](llms.txt), [`llms-full.txt`](llms-full.txt) | An [llmstxt.org](https://llmstxt.org/) index, and every page concatenated into one file. |
| [`snapshots/html/`](snapshots/html/) | The raw body HTML of each page as fetched, so every content diff can be traced to its source. |
| [`data/updates.json`](data/updates.json) | The manual's official updates log, parsed. |
| [`site/`](site/) | Quarto website, published to GitHub Pages. It serves the rendered pages plus the raw `.md` and llms files. |

## How it stays in sync

A weekly GitHub Action re-crawls un.org (respecting `Crawl-delay: 10`) and regenerates everything. It then runs the validation gate (page count, shrinkage, broken links) and opens a PR listing the changed pages and the matching entries from the manual's own updates log. Nothing is merged without review. Git history is the manual's version history.

## Usage

```sh
uv sync
uv run unem sync       # fetch → convert → manifest → llms.txt → validate
uv run unem build      # convert + llms.txt from existing snapshots (offline)
uv run unem validate
uv run pytest
quarto preview site    # after `uv run unem site`
```

If un.org blocks GitHub runners, run `uv run unem sync` locally and push the result.

## Resources

- https://www.un.org/dgacm/en/content/editorial-manual (canonical source)
- https://llmstxt.org/
- [`historical/United_Nations_Editorial_Manual.pdf`](historical/): the **1983** print edition (Sales No. E.83.I.16). It is superseded and kept for reference only; it is not part of the mirror.

## Ideas

- scrape? → done: deterministic crawl of the body HTML
- plain HTML → Markdown? → done: `content/en/`
- use GitBook? → Quarto site instead
- context7 → listing planned (P5)
- embeddings → `search_manual` in the MCP server (P4)
- could be used for more UN resources to be accessible [larger idea] → see [TODO.md](TODO.md)

See [TODO.md](TODO.md) for the roadmap, including multilingual support.

## License

The code is under the MIT License. Manual content is © United Nations and is reproduced here unofficially; no license is granted for it.
