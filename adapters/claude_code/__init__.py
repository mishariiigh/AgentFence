"""Claude Code adapter — read-only discovery of Claude Code configuration."""

from __future__ import annotations

from pathlib import Path

KNOWN_FILES = ("settings.json", "settings.local.json", ".mcp.json", "CLAUDE.md")


def discover_config_files(root: Path) -> list[Path]:
    """Return Claude Code configuration files under ``root`` (read-only)."""
    return [p for name in KNOWN_FILES for p in sorted(root.rglob(name)) if p.is_file()]
