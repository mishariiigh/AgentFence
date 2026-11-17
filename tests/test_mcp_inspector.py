"""Tests for the MCP inspector."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from agentfence_mcp_inspector.inspector import McpInspectError, inspect_mcp_config


def _write(tmp_path: Path, data: dict) -> Path:
    p = tmp_path / ".mcp.json"
    p.write_text(json.dumps(data), encoding="utf-8")
    return p


def test_detects_env_secret(tmp_path: Path) -> None:
    p = _write(
        tmp_path,
        {
            "mcpServers": {
                "web": {"command": "npx", "env": {"API_TOKEN": "sk-abcdefghij1234567890"}}
            }
        },
    )
    result = inspect_mcp_config(p)
    assert any(f.id == "AF-MCP-ENV-SECRET" for f in result.findings)
    # full secret must never appear in any finding text
    for f in result.findings:
        assert "sk-abcdefghij1234567890" not in (f.evidence or "")


def test_detects_no_verify_flag(tmp_path: Path) -> None:
    p = _write(tmp_path, {"mcpServers": {"fs": {"command": "node", "args": ["--no-verify"]}}})
    result = inspect_mcp_config(p)
    assert any(f.id == "AF-MCP-NO-VERIFY" for f in result.findings)


def test_detects_insecure_url(tmp_path: Path) -> None:
    p = _write(tmp_path, {"mcpServers": {"web": {"url": "http://example.com/sse"}}})
    result = inspect_mcp_config(p)
    assert any(f.id == "AF-MCP-INSECURE-URL" for f in result.findings)


def test_clean_config_has_no_findings(tmp_path: Path) -> None:
    p = _write(
        tmp_path,
        {
            "mcpServers": {
                "fs": {"command": "npx", "args": ["-y", "server"], "env": {"KEY": "${MY_KEY}"}}
            }
        },
    )
    assert inspect_mcp_config(p).findings == []


def test_invalid_json_raises(tmp_path: Path) -> None:
    p = tmp_path / "mcp.json"
    p.write_text("{not json", encoding="utf-8")
    with pytest.raises(McpInspectError):
        inspect_mcp_config(p)
