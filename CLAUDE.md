# Project Memory

Read [AGENT.md](./AGENT.md) first — it tracks progress, gaps, the end-goal
architecture, the component-reuse map from `repos/weknora` (MIT) and
`repos/llm_wiki` (GPLv3 pattern-only), and the milestone plan. Always check
AGENT.md before starting work so you do not redo solved problems or copy
code under the wrong license.

## Hard rules

- **llm_wiki is GPLv3 — never copy its code.** Borrow prompts and patterns only.
- **WeKnora is MIT — reuse allowed with attribution.**
- **Reuse Graphiti shims in `python-core/wiki_agent/memory.py` verbatim.** They
  solve four known pitfalls (embedding-dim ordering, json_object mode,
  FalkorDB property flattening, `database=GROUP_ID`). Do not rewrite.
- **Never hard-code LLM endpoints or API keys.** All configuration lives in
  `python-core/wiki_agent/config.py` and persists via `keyring` + JSON.
- **Never commit secrets, `.venv/`, model caches, or the FalkorDB database.**
- **Never introduce Docker dependencies** — the local toolchain is broken.
