# Contributing to AgentFence

Thanks for helping build AgentFence. Please read the invariants below first —
they are what make the tool safe to run against arbitrary repositories.

## Non-negotiable invariants

1. **Read-only scanning.** Never add code that executes scanned files, spawns
   processes from imports scanned modules.
2. **No launches.** Never start an agent or MCP server during inspection.
3. **No telemetry, no uploads.** No outbound network calls in the scanning path.
4. **Redact secrets.** Any new output path (CLI, report, log) must pass through
   `agentfence_core.redaction`.
5. **Deterministic policy only.** Security authorization decisions must never
   involve an LLM.
6. **No fabricated results.** UI metrics that aren't backed by real scans must
   be explicitly labeled demonstration data.
7. **No real credentials in the repo.** Tests use obviously fake values only.

PRs violating these will be declined regardless of other merits.

## Development setup (macOS)

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e '.[dev]'

cd apps/dashboard && npm install   # only if touching the dashboard
```

## Workflow

1. Fork and create a branch (`feat/my-change`).
2. Make the change with tests. New scanner rules, policy behaviors, and
   inspectors require tests.
3. Run checks:

   ```bash
   python -m pytest          # all tests must pass
   ruff check packages tests # lint must be clean
   ```

4. If touching the dashboard: `npm run build` in `apps/dashboard` must pass.
5. Open a PR describing the change and any security-relevant reasoning.

## Code style

- Python: type hints everywhere, ruff (`E,F,I,UP,B`), 100-char lines.
- Keep modules focused; avoid abstractions without a second user.
- Errors are raised, surfaced, or logged — never silently swallowed.

## Reporting security issues

See [SECURITY.md](SECURITY.md) — do not open public issues for vulnerabilities.
