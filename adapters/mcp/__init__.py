"""MCP adapter — read-only discovery of MCP configuration files."""

from __future__ import annotations

from pathlib import Path

KNOWN_FILES = (".mcp.json", "mcp.json")


def discover_config_files(root: Path) -> list[Path]:
    """Return MCP configuration files under ``root`` (read-only)."""
    return [p for name in KNOWN_FILES for p in sorted(root.rglob(name)) if p.is_file()]
