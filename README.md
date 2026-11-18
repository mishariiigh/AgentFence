# AgentFence — AI Agent Security Engineering Platform

**Scan. Test. Protect. Monitor.**

AgentFence is an open-source, local-first platform for assessing, testing, and improving the security of AI agents — including Claude Code, OpenAI Codex, Cursor, MCP servers, and custom agents.

> **Status: early foundation (v0.1).** The first milestone delivers a working CLI, a read-only security scanner, a safe Attack Lab, a deterministic policy engine, an MCP inspector, a local API, and a dashboard foundation. See [docs/ROADMAP.md](docs/ROADMAP.md) for what's next.

---

## Why AgentFence

AI agents hold powerful capabilities: file access, shell execution, network calls, and tool orchestration. Their configuration — permissions, MCP servers, instruction files — is often committed to repositories with risky defaults or hardcoded secrets. AgentFence gives you a reproducible, offline way to inspect and test those configurations **without ever executing them**.

## What works today

| Capability | Status | How |
|---|---|---|
| Read-only security scanner | ✅ Working | `agentfence scan <path>` |
| MCP configuration inspector | ✅ Working | `agentfence mcp scan <path>` |
| Deterministic policy engine | ✅ Working | `agentfence policy validate / evaluate` |
| Safe scenario-based Attack Lab | ✅ Working | `agentfence arena` |
| Risk scoring & report generation | ✅ Working | `agentfence scan --report report.json` |
| Local audit log (hash-chained) | ✅ Working | written to `.agentfence/audit.jsonl` |
| SQLite scan history | ✅ Working | `.agentfence/agentfence.db`, API: `GET /api/v1/scans` |
| Local API (health, scan, history, MCP inspect) | ✅ Working | `agentfence dashboard` |
| Dashboard UI (live data for Overview/Scans/Findings/MCP) | ✅ Working | `npm run dev` in `apps/dashboard` |
| Attack Lab & Policies UI | 🟡 Demo/planned views | see docs/ROADMAP.md |
| Runtime protection / agent enforcement | ❌ Not implemented | see docs/SECURITY_MODEL.md |

## Security guarantees (enforced in code)

- **Read-only inspection.** Scanned files are parsed, never executed. No subprocess is spawned on scanned content.
- **No launches.** No agent, MCP server, or external service is started during scanning.
- **Secret redaction.** Likely secret values are redacted in findings evidence, reports, and the audit log.
- **Deterministic policy.** Authorization decisions come exclusively from validated rules — never from an LLM.
- **Local-first, no telemetry.** Nothing leaves your machine.

See [docs/SECURITY_MODEL.md](docs/SECURITY_MODEL.md) for assumptions and limitations.

## Installation (macOS)

Requires Python 3.11+ and Node.js 20+.

```bash
git clone <your-fork-url> agentfence
cd agentfence

# Python CLI + API
python3 -m venv .venv
source .venv/bin/activate
pip install -e '.[dev]'

# Dashboard
cd apps/dashboard
npm install
```

## Usage

```bash
# Initialize an AgentFence workspace (.agentfence/ with policies & scenarios)
agentfence init

# Statically scan AI agent configurations (never executes them)
agentfence scan .
agentfence scan ~/my-project --json
agentfence scan ~/my-project --report report.json

# Inspect MCP configuration files (read-only)
agentfence mcp scan .mcp.json

# Validate & evaluate deterministic policies
agentfence policy validate policies/example.yaml
agentfence policy evaluate policies/example.yaml read docs/report.md

# Run the safe scenario suite (declarative data; no payloads executed)
agentfence arena benchmarks/scenarios

# Start the local API on http://127.0.0.1:8000
agentfence dashboard
```

### Dashboard (live API integration)

```bash
# Terminal 1: start the local API (binds to 127.0.0.1 by default)
agentfence dashboard

# Terminal 2: start the dashboard
cd apps/dashboard
npm install
npm run dev        # http://localhost:3000
```

The dashboard talks to the API at `NEXT_PUBLIC_AGENTFENCE_API`
(default: `http://127.0.0.1:8000`). Override it, e.g. for a custom port:

```bash
echo 'NEXT_PUBLIC_AGENTFENCE_API=http://127.0.0.1:8001' > apps/dashboard/.env.local
```

From the dashboard you can:

- See live totals (scans, findings, critical/high counts) on **Overview**.
- Run a new scan by path on **Scans** (history refreshes automatically).
- Open any scan to see its actual stored findings on **Scan Details**.
- Filter all findings by severity on **Findings**.
- Run live MCP config inspections on **MCP Inspection**.

Scan history persists across API restarts in SQLite at
`.agentfence/agentfence.db` (override with `AGENTFENCE_DB`). CORS is limited
to localhost dashboard origins.

Attack Lab, Policies, Reports, and Settings pages remain clearly-labelled
demonstration/planned views.

## Architecture

Modular monorepo:

```
packages/            Python modules (core, scanner, policy_engine, attack_lab,
                     mcp_inspector, risk_engine, report_generator, flight_recorder,
                     cli, api)
adapters/            Read-only config discovery per platform (claude_code, codex,
                     cursor, mcp, custom)
apps/api + dashboard FastAPI + Next.js dashboard
benchmarks/          Declarative scenario files (YAML data only)
policies/            Example policy files
tests/               Pytest suite
```

Details in [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).

## Development

```bash
# Tests
python -m pytest

# Lint
ruff check packages tests

# Dashboard production build
cd apps/dashboard && npm run build
```

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md). Security-relevant changes must preserve the read-only scanning guarantee — see [SECURITY.md](SECURITY.md).

## License

[Apache-2.0](LICENSE)
