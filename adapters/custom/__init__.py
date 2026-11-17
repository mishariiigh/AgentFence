"""Custom agent adapter — user-supplied configuration discovery."""

from __future__ import annotations

from pathlib import Path

SUFFIXES = (".yaml", ".yml", ".json", ".toml")


def discover_config_files(root: Path) -> list[Path]:
    """Return candidate configuration files under ``root`` (read-only)."""
    return sorted(p for p in root.rglob("*") if p.is_file() and p.suffix.lower() in SUFFIXES)
