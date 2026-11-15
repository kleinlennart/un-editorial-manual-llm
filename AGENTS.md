# AGENTS.md

Python 3.12+, run with `uv`. The package lives in `src/unem/`, and its CLI is `uv run unem <cmd>`.

## Pipeline

`fetch` (un.org → `snapshots/html/`) → `convert` (→ `content/en/*.md`) → `manifest.json` → `llms.txt` / `llms-full.txt` → `validate`.

- `uv run unem sync`: the full pipeline, including the network crawl (about 7 minutes, because of the 10 s crawl delay).
- `uv run unem build`: offline; regenerates everything from the committed snapshots.
- `uv run unem validate`: the gate. A non-zero exit means don't publish.
- `uv run unem site`: stages the Quarto site inputs; then run `quarto render site`.
- `uv run pytest`: golden tests in `tests/fixtures/`.

## Rules

- **Never** edit `content/`, `manifest.json` or `llms*.txt` by hand. They are generated; change the converter instead and regenerate.
- The mirror is verbatim: no LLM rewriting of manual text, ever.
- If you change the converter, run `uv run unem build`, check the content diff, and update the goldens (`uv run pytest --update-goldens`) only when the change is intended.
- Use relative paths only, in code, docs and commits.
- Keep the disclaimer (in `src/unem/llmstxt.py`) on every generated surface.
