# Security Policy

## Supported versions

| Version | Supported |
|---------|-----------|
| 0.1.x   | ✅        |

## Reporting a vulnerability

**Do not open a public issue for security vulnerabilities.**

Report privately to the maintainers via GitHub Security Advisories
("Report a vulnerability" on the repository's Security tab). Include:

- Affected component and version
- Steps to reproduce or a proof of concept
- Impact assessment

We aim to acknowledge reports within 5 business days.

## Scope

In scope:
- Anything that causes AgentFence to execute scanned files or launch
  agents/MCP servers.
- Leakage of scanned content or secrets outside the local machine.
- Bypass of secret redaction in logs, reports, or CLI output.
- Nondeterministic or LLM-influenced policy decisions.

Out of scope:
- Vulnerabilities in scanned target applications themselves.
- Local attacks where the attacker already has the user's privileges
  (AgentFence does not defend against a compromised local user).

## Design invariants (contributors: breaking these is a security bug)

1. Scanned files are never executed; no subprocess runs on scanned content.
2. No agent or MCP server is launched during inspection.
3. No outbound network calls in the scanning path; no telemetry.
4. Secret values are redacted in all output and persisted logs.
5. Policy decisions are deterministic rule evaluations — never LLM-based.
