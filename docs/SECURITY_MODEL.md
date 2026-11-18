# AgentFence Security Model

This document states what AgentFence does, what it deliberately does not do,
and the trust assumptions involved. It is normative for contributors.

## What AgentFence does

1. **Static, read-only inspection** of AI agent configuration files
   (`settings.json`, `.mcp.json`, `mcp.json`, `config.toml`, YAML rules files)
   using filename classification and content pattern/structure rules.
2. **Secret detection** using safe regex patterns. Matched *values* are
   redacted before display or persistence; only the pattern category and a
   truncated prefix (first 4 characters) are retained.
3. **Deterministic policy evaluation** of `allow` / `deny` /
   `require_approval` decisions from validated YAML rules.
4. **Scenario evaluation** in the Attack Lab: declarative fixtures compared
   against deterministic policy outcomes.
5. **Local audit logging**: append-only, hash-chained JSONL in
   `.agentfence/audit.jsonl`, with all strings redacted before writing.

## Hard guarantees (enforced in code, tested)

- Scanned files are **never executed**. There is no code path in the scanner
  that spawns a process, evaluates scanned text, or imports scanned modules.
- No agent, MCP server, or network service is **launched** by scanning.
- No scanned content, secrets, or reports are **uploaded** anywhere. There are
  no outbound network calls in the scanning path.
- Policy decisions involve **no LLM**. The evaluator is pure, synchronous, and
  deterministic; the same input always yields the same decision.
- Reports, logs, API responses, and persisted database rows pass through the
  redaction layer before storage or display.

## What AgentFence does NOT do (do not assume otherwise)

- **No runtime protection.** AgentFence does not intercept, sandbox, or
  enforce anything while your agent runs. It does not block tool calls,
  commands, or network access. Any claim of runtime enforcement would be
  false until an enforcement component exists and is tested.
- **No execution-based verification.** A configuration that *looks* safe may
  still behave dangerously. Static inspection is a best-effort signal, not a
  proof of safety.
- **No complete secret detection.** Pattern-based detection has both false
  negatives (unusual secret formats) and false positives. Treat any finding
  as "investigate manually," never as ground truth.
- **No tamper-proof audit log.** The hash chain detects accidental mutation
  but an attacker with filesystem write access can rewrite the whole log.
- **The scan path validator is not a sandbox.** It rejects remote URLs and
  requires existing local paths, but the local user is already trusted by
  assumption; the API is not hardened against a malicious local process.

## Trust assumptions

- The user running AgentFence is trusted with full local access.
- Configuration files under scan are treated as **untrusted input**: parsing
  uses safe loaders only (`json.loads`, `yaml.safe_load`) with size limits
  (512 KiB), and parse failures become findings rather than crashes.
- The Attack Lab's built-in policies are examples, not security defaults you
  should rely on for production decisions.
- **The local API is not a hardened network service.** It binds to 127.0.0.1
  and its CORS allow-list covers only local dashboard origins, but anyone or
  anything already running on your machine can call it. Do not expose the API
  port beyond localhost (e.g. do not run it with `--host 0.0.0.0` on a shared
  network).

## Reporting a vulnerability

See [SECURITY.md](../SECURITY.md).
