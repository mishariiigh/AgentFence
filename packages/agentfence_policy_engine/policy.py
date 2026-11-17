"""Policy file loading and validation.

A policy file is a YAML document:

    name: my-policy
    default: deny
    rules:
      - id: allow-read
        action: read
        resource: "docs/*"
        decision: allow
      - id: require-approval-writes
        action: write
        resource: "docs/*"
        decision: require_approval
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
from agentfence_core.models import Decision
from pydantic import BaseModel, Field, ValidationError, field_validator


class PolicyRule(BaseModel):
    """A single explicit policy rule."""

    id: str
    action: str
    resource: str
    decision: Decision
    description: str | None = None

    @field_validator("action", "resource")
    @classmethod
    def _non_empty(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("must be a non-empty string")
        return value


class Policy(BaseModel):
    """A validated policy document."""

    name: str
    default: Decision = Decision.DENY
    rules: list[PolicyRule] = Field(default_factory=list)

    @field_validator("name")
    @classmethod
    def _name_non_empty(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("policy name must be non-empty")
        return value


class PolicyValidationError(Exception):
    """Raised when a policy file is invalid."""

    def __init__(self, path: str, errors: list[str]) -> None:
        self.path = path
        self.errors = errors
        super().__init__(f"Invalid policy file {path}: {'; '.join(errors)}")


def load_policy(path: Path) -> Policy:
    """Load and validate a policy YAML file."""
    if not path.is_file():
        raise PolicyValidationError(str(path), ["file does not exist"])
    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as exc:
        raise PolicyValidationError(str(path), [f"could not read/parse: {exc}"]) from exc
    if not isinstance(raw, dict):
        raise PolicyValidationError(str(path), ["top-level document must be a mapping"])
    return parse_policy(raw, str(path))


def parse_policy(raw: dict[str, Any], source: str) -> Policy:
    """Validate a raw mapping into a :class:`Policy`."""
    try:
        return Policy.model_validate(raw)
    except ValidationError as exc:
        errors = [f"{'.'.join(str(p) for p in e['loc'])}: {e['msg']}" for e in exc.errors()]
        raise PolicyValidationError(source, errors) from exc


def validate_policy_text(text: str) -> list[str]:
    """Return a list of validation problems (empty means valid)."""
    try:
        raw = yaml.safe_load(text)
    except yaml.YAMLError as exc:
        return [f"YAML parse error: {exc}"]
    if not isinstance(raw, dict):
        return ["top-level document must be a mapping"]
    try:
        Policy.model_validate(raw)
    except ValidationError as exc:
        return [f"{'.'.join(str(p) for p in e['loc'])}: {e['msg']}" for e in exc.errors()]
    return []
