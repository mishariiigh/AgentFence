"""Known AI agent configuration file signatures.

Each entry maps a config kind to the file names / extensions that identify it.
Detection is filename-based and read-only: file contents are never executed.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class ConfigKind:
    """A recognized agent configuration file type."""

    key: str
    description: str
    filenames: tuple[str, ...] = field(default_factory=tuple)
    suffixes: tuple[str, ...] = field(default_factory=tuple)

    def matches(self, name: str) -> bool:
        lowered = name.lower()
        return lowered in self.filenames or lowered.endswith(self.suffixes)


CONFIG_KINDS: tuple[ConfigKind, ...] = (
    ConfigKind(
        key="claude_settings",
        description="Claude Code settings",
        filenames=("settings.json", "settings.local.json"),
    ),
    ConfigKind(
        key="claude_mcp",
        description="Claude Code MCP configuration",
        filenames=(".mcp.json",),
    ),
    ConfigKind(
        key="codex_config",
        description="OpenAI Codex CLI configuration",
        filenames=("config.toml",),
    ),
    ConfigKind(
        key="cursor_mcp",
        description="Cursor MCP configuration",
        filenames=("mcp.json",),
    ),
    ConfigKind(
        key="cursor_rules",
        description="Cursor rules",
        suffixes=(".cursorrules", ".mdc"),
    ),
    ConfigKind(
        key="generic_yaml",
        description="YAML configuration",
        suffixes=(".yaml", ".yml"),
    ),
    ConfigKind(
        key="generic_json",
        description="JSON configuration",
        suffixes=(".json",),
    ),
)


def classify(name: str) -> ConfigKind | None:
    """Return the config kind matching ``name``, or None if unsupported."""
    for kind in CONFIG_KINDS:
        if kind.matches(name):
            return kind
    return None
