# AgentFence Architecture

## Principles

1. **Local-first.** All processing happens on the user's machine. No telemetry, no uploads.
2. **Read-only by construction.** Scanning code contains no execution paths for scanned content.
3. **Deterministic security decisions.** Authorization is rule-based, never model-based.
4. **Modular monorepo.** Focused Python packages, one Next.js app, clear boundaries.

## Layout

```
agentfence/
├── packages/
│   ├── agentfence_storage/          # SQLite persistence (schema migrations, scan store)
│   ├── agentfence_api/              # FastAPI app (scan + history + MCP endpoints, CORS)
│   ├── agentfence_cli/              # Typer CLI (`agentfence`)
│   └── ... (core, scanner, policy_engine, attack_lab, mcp_inspector,
│            risk_engine, report_generator, flight_recorder)
├── adapters/                        # Per-platform read-only config discovery
│   ├── claude_code/ codex/ cursor/ mcp/ custom/
├── apps/
│   ├── dashboard/                   # Next.js + Tailwind dashboard
├── benchmarks/scenarios/            # Declarative YAML scenarios (data only)
├── policies/                        # Example policy files
├── tests/                           # Pytest suite
└── docs/
```

## Data flow (scan)

```
target path ──► validated by API (local path, no URLs, must exist)
   │  (read-only file discovery; node_modules/.git/.next skipped)
   ▼
signatures.classify() ──► supported config kinds
   │
   ▼
engine._inspect_file()
   ├── secrets detection (pattern match; evidence redacted via core.redaction)
   ├── JSON/YAML parse (parse errors become low-severity findings)
   └── rules.inspect_mapping()  (risky permissions, wildcards, suspicious text)
   ▼
ScanResult (list[Finding], counts, notes)
   ├── CLI rendering (Rich)  ── or ── JSON (--json)
   ├── risk_engine.score_findings() ─► score/label
   ├── report_generator.save_report()
   └── ★ ScanStore.save_scan() ─► .agentfence/agentfence.db (SQLite)
            │  findings rows store redacted evidence only
            ▼
       API endpoints: GET /api/v1/scans (history)
                      GET /api/v1/scans/{id} (detail + findings)
                      GET /api/v1/summary (dashboard overview)
   │
   ▼
flight_recorder.record() ─► .agentfence/audit.jsonl (hash-chained, redacted)
```

## Policy evaluation

`Policy` files are validated YAML (Pydantic schemas). Evaluation is
first-matching-rule-wins over glob-style action/resource patterns, falling back
to the policy `default`. Every decision carries a human-readable explanation
naming the matched rule. There is deliberately **no** LLM, heuristic scoring, or
network access in this path.

## Attack Lab

Scenarios are YAML *data* (`fixture` + `expected`). The runner evaluates the
fixture against a named built-in deterministic policy and compares actual vs.
expected decisions. Nothing is executed; "attack" refers to the adversarial
*expectation being tested*, not to running an attack.

## Dashboard

Next.js App Router with a persistent sidebar and eight routes. All displayed
metrics are explicitly labeled demonstration data until the API integration
milestone lands. Dark cybersecurity-SaaS aesthetic via Tailwind CSS variables.

## Persistence layer (Milestone 2)

`agentfence_storage` owns all SQLite access:

- **Location:** `.agentfence/agentfence.db` (override with `AGENTFENCE_DB`).
  The directory and database are created on first use.
- **Schema versioning:** a `schema_version` table drives ordered migrations;
  a database written by a *newer* AgentFence is rejected with a clear error
  rather than silently migrated backwards.
- **Safety:** parameterized SQL everywhere, `PRAGMA foreign_keys = ON`,
  transactions around scan+findings inserts, and `DatabaseError` wrapping so
  callers never see raw driver exceptions.
- **Redaction before persistence:** finding evidence passes through
  `agentfence_core.redaction` before an INSERT; raw secret values are never
  written. Targets are stored as short display paths (parent/name), not full
  absolute paths.

## Dashboard ↔ API integration

- Typed client in `apps/dashboard/lib/api.ts`; base URL from
  `NEXT_PUBLIC_AGENTFENCE_API` (default `http://127.0.0.1:8000`).
- CORS on the API is an explicit allow-list (localhost:3000 variants),
  configurable via `AGENTFENCE_CORS_ORIGINS`. The API binds to `127.0.0.1`.
- Pages fetch live data with loading/empty/error states; failures never
  silently fall back to demo data. A status indicator shows API health.

## Extension points

- **New scanner rule:** add a pure function in `scanner/rules.py` + tests.
- **New platform:** add an adapter under `adapters/<platform>` exposing
  `discover_config_files(root) -> list[Path]` (read-only).
- **New scenario:** drop a YAML file in `benchmarks/scenarios/`.
