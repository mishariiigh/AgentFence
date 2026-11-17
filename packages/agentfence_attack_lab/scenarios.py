"""Scenario schema and loading.

A scenario file is declarative YAML:

    name: tool-overreach-test
    description: Verifies that a write tool call is not silently allowed.
    tags: [permissions]
    fixture:
      action: write
      resource: "system/*"
      policy: default-deny
    expected:
      decision: deny
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
from agentfence_core.models import Decision
from pydantic import BaseModel, Field, ValidationError


class ScenarioFixture(BaseModel):
    """The input state a scenario is evaluated against."""

    action: str
    resource: str
    policy: str = Field(default="default-deny")


class ExpectedOutcome(BaseModel):
    decision: Decision


class Scenario(BaseModel):
    """A declarative attack-simulation scenario."""

    name: str
    description: str = ""
    tags: list[str] = Field(default_factory=list)
    fixture: ScenarioFixture
    expected: ExpectedOutcome


class ScenarioError(Exception):
    """Raised when a scenario file cannot be loaded."""


def load_scenario(path: Path) -> Scenario:
    """Load a single scenario YAML file."""
    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as exc:
        raise ScenarioError(f"{path}: {exc}") from exc
    if not isinstance(raw, dict):
        raise ScenarioError(f"{path}: scenario must be a YAML mapping")
    try:
        return Scenario.model_validate(raw)
    except ValidationError as exc:
        problems = [f"{'.'.join(str(p) for p in e['loc'])}: {e['msg']}" for e in exc.errors()]
        raise ScenarioError(f"{path}: {problems}") from exc


def load_scenarios(paths: list[Path]) -> list[Scenario]:
    """Load all scenario files from the given paths (files or directories)."""
    scenarios: list[Scenario] = []
    for path in paths:
        if path.is_file():
            scenarios.append(load_scenario(path))
        elif path.is_dir():
            for p in sorted(path.rglob("*")):
                if p.suffix.lower() in {".yaml", ".yml"}:
                    scenarios.append(load_scenario(p))
        else:
            raise ScenarioError(f"scenario path not found: {path}")
    return scenarios


# Built-in policies usable by fixtures (deterministic, no LLM).
_BUILTIN_POLICIES: dict[str, dict[str, Any]] = {
    "default-deny": {"default": Decision.DENY, "rules": []},
    "default-allow": {"default": Decision.ALLOW, "rules": []},
    "read-only": {
        "default": Decision.DENY,
        "rules": [{"id": "r1", "action": "read", "resource": "*", "decision": Decision.ALLOW}],
    },
    "write-needs-approval": {
        "default": Decision.DENY,
        "rules": [
            {"id": "r1", "action": "write", "resource": "*", "decision": Decision.REQUIRE_APPROVAL}
        ],
    },
}


def builtin_policy(name: str) -> dict[str, Any]:
    """Return a built-in policy definition by name."""
    try:
        return _BUILTIN_POLICIES[name]
    except KeyError:
        raise ScenarioError(
            f"unknown fixture policy '{name}'. Available: {', '.join(sorted(_BUILTIN_POLICIES))}"
        ) from None
