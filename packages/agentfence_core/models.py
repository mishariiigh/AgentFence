"""Shared domain models for AgentFence."""

from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field


class Severity(StrEnum):
    """Severity of a security finding."""

    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"


class Finding(BaseModel):
    """A structured security finding produced by a read-only inspection."""

    id: str
    title: str
    severity: Severity
    category: str
    description: str
    remediation: str
    file: str | None = None
    line: int | None = None
    evidence: str | None = Field(
        default=None, description="Redacted evidence snippet; secrets must never appear here."
    )
    metadata: dict[str, Any] = Field(default_factory=dict)


class ScanResult(BaseModel):
    """Result of scanning one or more targets."""

    target: str
    scanner: str
    findings: list[Finding] = Field(default_factory=list)
    files_inspected: int = 0
    notes: list[str] = Field(default_factory=list)

    @property
    def counts_by_severity(self) -> dict[str, int]:
        counts = {s.value: 0 for s in Severity}
        for f in self.findings:
            counts[f.severity.value] += 1
        return counts


class Decision(StrEnum):
    """Deterministic policy decision outcomes."""

    ALLOW = "allow"
    DENY = "deny"
    REQUIRE_APPROVAL = "require_approval"


class PolicyDecision(BaseModel):
    """The result of a deterministic policy evaluation. No LLM involved."""

    decision: Decision
    matched_rule: str | None = None
    explanation: str
