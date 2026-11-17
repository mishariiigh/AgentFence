"""Read-only MCP configuration inspection."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from agentfence_core.models import Finding, ScanResult
from agentfence_core.redaction import redact

MAX_FILE_BYTES = 512 * 1024


class McpInspectError(Exception):
    """Raised when an MCP configuration cannot be inspected."""


def inspect_mcp_config(path: Path) -> ScanResult:
    """Inspect an MCP configuration file (e.g. .mcp.json, mcp.json) without launching anything.

    Recognized shapes:
      {"mcpServers": {"<name>": {"command": ..., "args": [...], "env": {...}, "url": ...}}}
    """
    if not path.is_file():
        raise McpInspectError(f"not a file: {path}")
    try:
        raw = path.read_text(encoding="utf-8", errors="replace")[:MAX_FILE_BYTES]
        data = json.loads(raw)
    except (OSError, json.JSONDecodeError) as exc:
        raise McpInspectError(f"could not read/parse {path}: {exc}") from exc
    if not isinstance(data, dict):
        raise McpInspectError(f"{path}: expected a JSON object at top level")

    result = ScanResult(target=str(path), scanner="agentfence-mcp-inspector")
    servers = data.get("mcpServers", {})
    if not isinstance(servers, dict):
        result.findings.append(
            Finding(
                id="AF-MCP-BAD-SHAPE",
                title="Malformed MCP configuration",
                severity="low",
                category="mcp",
                description="'mcpServers' must be an object mapping server names to configs.",
                remediation="Fix the 'mcpServers' structure.",
                file=str(path),
            )
        )
        return result

    for name, cfg in servers.items():
        if not isinstance(cfg, dict):
            continue
        result.findings.extend(_inspect_server(name, cfg, str(path)))
    result.notes.append(
        "Read-only inspection: no MCP servers were launched and no tools were executed."
    )
    return result


def _inspect_server(name: str, cfg: dict[str, Any], source: str) -> list[Finding]:
    findings: list[Finding] = []

    env = cfg.get("env")
    if isinstance(env, dict):
        for key, value in env.items():
            if isinstance(value, str) and value and not value.startswith("${"):
                findings.append(
                    Finding(
                        id="AF-MCP-ENV-SECRET",
                        title=(
                            f"Possible hardcoded secret in env var '{key}' "
                            f"of MCP server '{name}'"
                        ),
                        severity="high",
                        category="mcp",
                        description=(
                            f"MCP server '{name}' sets env '{key}' with a literal value. "
                            "Use environment expansion (e.g. ${VAR}) instead of hardcoding."
                        ),
                        remediation=(
                            "Reference the value from the environment; rotate it if committed."
                        ),
                        file=source,
                        evidence=redact(f"{key}={value}"),
                    )
                )

    if "command" in cfg:
        cmd = cfg["command"]
        if isinstance(cmd, str) and any(tok in cmd for tok in ("curl", "wget", "http", "eval")):
            findings.append(
                Finding(
                    id="AF-MCP-SUSPICIOUS-COMMAND",
                    title=f"Suspicious command for MCP server '{name}'",
                    severity="medium",
                    category="mcp",
                    description=(
                        f"MCP server '{name}' command contains a network/eval token: "
                        f"{redact(str(cmd))}"
                    ),
                    remediation="Review the command; pin a trusted server binary and version.",
                    file=source,
                )
            )

    if "url" in cfg:
        url = cfg["url"]
        if isinstance(url, str) and not url.startswith("https://"):
            findings.append(
                Finding(
                    id="AF-MCP-INSECURE-URL",
                    title=f"Insecure URL for MCP server '{name}'",
                    severity="medium",
                    category="mcp",
                    description=(
                        f"Remote MCP server '{name}' does not use HTTPS: {redact(str(url))}"
                    ),
                    remediation="Use https:// endpoints for remote MCP servers.",
                    file=source,
                )
            )

    args = cfg.get("args")
    if isinstance(args, list) and any(isinstance(a, str) and "--no-verify" in a for a in args):
        findings.append(
            Finding(
                id="AF-MCP-NO-VERIFY",
                title=f"TLS verification disabled for MCP server '{name}'",
                severity="high",
                category="mcp",
                description="Server arguments include '--no-verify', disabling certificate checks.",
                remediation="Remove '--no-verify'; investigate why verification was bypassed.",
                file=source,
            )
        )
    return findings
