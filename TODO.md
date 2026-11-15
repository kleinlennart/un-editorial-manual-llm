# TODO

Roadmap beyond the current phase. See the README for what exists today.

## Phases

- [ ] **P1:** Markdown mirror, `llms.txt` / `llms-full.txt`, Quarto site, weekly sync PR
- [ ] **P2a:** Microsoft Copilot kit: instructions, knowledge files (.docx + .md), starter prompts, declarative agent package, "Use with Copilot" page
- [ ] **P2b:** Agent Skill (agentskills.io spec), installable with `npx skills add`; zip for claude.ai; per-repo example
- [ ] **P3:** `rules.json` (extracted + curated tiers), which generates the Vale package (`UNStyle`) and `rules.js`
- [ ] **P4:** MCP server (`check_text`, `lookup_term`, `search_manual`, `get_section`), run with `uvx`
- [ ] **P5:** Evals for linter precision/recall, the drafting eval (with/without skill or MCP, plus a manual Copilot condition), a client-side demo page, and Context7 and llms-txt-hub listings

## Multilingual (important for the UN)

The UN works in six official languages. Each language service maintains its **own** editorial guidance, so the work is to discover and mirror each one, not to translate the English manual.

- [ ] Discover the Arabic, Chinese, French, Russian and Spanish editorial resources. The un.org language menu is rendered by JS, so find the real URLs behind it, and look for other language-service style guides.
- [ ] Generalize `fetch`/`convert` per language, writing to `content/<lang>/` and `snapshots/<lang>/`.
- [ ] Per-language `llms.txt` at `/<lang>/llms.txt`, with a root `llms.txt` linking them.
- [ ] Per-language `rules.json` and Vale styles. Each language has its own spelling and typography, e.g. the French space before `; : ! ?`, Spanish `¿¡`, Chinese full-width punctuation.
- [ ] Quarto language switcher; RTL layout for Arabic; CJK-friendly search.
- [ ] Make the skill, Copilot kit and MCP server language-aware (a `lang` parameter on `check_text` and `lookup_term`).

## Later

- [ ] **Word add-in:** an Office.js task pane that runs `rules.js` locally on the open document, with no AI and no data leaving the machine. Sideloadable, or deployed centrally by IT. Decide after the P2/P5 usage signal.
- [ ] Hosted remote MCP endpoint (HTTP), for non-developers and for Copilot Studio, which supports MCP.
- [ ] Copilot skill in Word, once Microsoft ships the SKILL.md picker there.
- [ ] GPT/Copilot drafters in the automated eval.
- [ ] UNTERM integration for terminology lookups. -- Interesting MCP opportunity as well
- [ ] Other UN reference resources through the same pipeline (Delegates Handbook, country names list, document submission guidelines).
