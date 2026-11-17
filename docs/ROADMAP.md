# AgentFence Roadmap

## Milestone 1 — Functional foundation ✅ (this release)

- [x] `agentfence` CLI: init, scan, arena, policy validate/evaluate, mcp scan, dashboard
- [x] Read-only security scanner with structured findings, severity, remediation
- [x] Safe secret detection with redaction
- [x] Deterministic policy engine (allow / deny / require-approval) + validation
- [x] Attack Lab: declarative scenarios, deterministic runner, summary reports
- [x] MCP configuration inspector (read-only)
- [x] Risk scoring (deterministic 0–100)
- [x] JSON & Markdown report generation
- [x] Local hash-chained audit log
- [x] FastAPI: health, scan, MCP inspect endpoints
- [x] Next.js dashboard foundation (8 pages, demo data clearly labeled)
- [x] CI (GitHub Actions), Docker files, docs, Apache-2.0 license

## Milestone 2 — Deeper platform coverage

- [ ] More scanner rules per platform (Claude Code, Codex, Cursor specifics)
- [ ] MCP inspector: tool schema analysis, prompt-injection heuristics in
      tool descriptions (static only)
- [ ] Policy engine: conditions, priorities, policy packs, import/include
- [ ] Attack Lab: user-authored scenario packs, CI gating (`arena --fail-on-failure`)
- [ ] Dashboard ↔ local API integration; real scan history via SQLite
- [ ] SARIF export for GitHub code scanning

## Milestone 3 — CI and team workflows

- [ ] GitHub Action: scan on PR, annotate findings, upload SARIF
- [ ] Baseline diffs (new findings only), severity thresholds
- [ ] Report signing for evidence integrity

## Milestone 4 — Runtime integrations (research track)

- [ ] Only after technical validation and explicit security review:
      opt-in hooks that observe agent tool calls and evaluate them against
      AgentFence policies. Any such feature must ship with enforcement tests
      and honest documentation of bypasses. **No runtime protection claims
      before this exists and is tested.**

## Non-goals (standing)

- Never execute scanned files or launch scanned agents/servers.
- Never make authorization decisions with an LLM.
- Never send user data off the machine by default.
