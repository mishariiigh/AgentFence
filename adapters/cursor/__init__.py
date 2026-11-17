"""Cursor adapter — read-only discovery of Cursor configuration."""

from __future__ import annotations

from pathlib import Path

KNOWN_FILES = ("mcp.json", ".cursorrules")
KNOWN_DIRS = (".cursor/rules",)


def discover_config_files(root: Path) -> list[Path]:
    """Return Cursor configuration files under ``root`` (read-only)."""
    found = [p for name in KNOWN_FILES for p in sorted(root.rglob(name)) if p.is_file()]
    for dirname in KNOWN_DIRS:
        found.extend(p for p in sorted(root.rglob("*")) if dirname in p.parts and p.is_file())
    return found
