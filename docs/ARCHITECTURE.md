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
│   ├── agentfence_core/             # Shared models (Finding, ScanResult, Decision)
│   │                                # + secret redaction helpers
│   ├── agentfence_scanner/          # Read-only config scanner
│   │   ├── signatures.py            #   which files are agent configs
│   │   ├── rules.py                 #   pure inspection rules over parsed data
│   │   └── engine.py                #   file discovery, parsing, findings assembly
│   ├── agentfence_policy_engine/    # Deterministic policy evaluation
│   │   ├── policy.py                #   schema + validation (Pydantic)
│   │   └── evaluator.py             #   first-match-wins evaluation, no LLM
│   ├── agentfence_attack_lab/       # Safe scenario testing
│   │   ├── scenarios.py             #   declarative YAML scenario schema
│   │   └── runner.py                #   deterministic fixture evaluation
│   ├── agentfence_mcp_inspector/    # Read-only MCP config inspection
│   ├── agentfence_risk_engine/      # Deterministic risk scoring
│   ├── agentfence_report_generator/ # JSON/Markdown reports (redacted)
│   ├── agentfence_flight_recorder/  # Hash-chained local audit log (JSONL)
│   ├── agentfence_cli/              # Typer CLI (`agentfence`)
│   └── agentfence_api/              # FastAPI application factory
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
target path
   │  (read-only file discovery; node_modules/.git/venv skipped)
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
   └── report_generator.save_report()
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

## Extension points

- **New scanner rule:** add a pure function in `scanner/rules.py` + tests.
- **New platform:** add an adapter under `adapters/<platform>` exposing
  `discover_config_files(root) -> list[Path]` (read-only).
- **New scenario:** drop a YAML file in `benchmarks/scenarios/`.
