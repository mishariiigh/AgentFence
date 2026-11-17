"""OpenAI Codex adapter — read-only discovery of Codex CLI configuration."""

from __future__ import annotations

from pathlib import Path

KNOWN_FILES = ("config.toml", "instructions.md")


def discover_config_files(root: Path) -> list[Path]:
    """Return Codex configuration files under ``root`` (read-only)."""
    return [p for name in KNOWN_FILES for p in sorted(root.rglob(name)) if p.is_file()]
