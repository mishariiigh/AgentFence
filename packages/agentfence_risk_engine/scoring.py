"""AgentFence risk engine — deterministic risk scoring for findings."""

from __future__ import annotations

from agentfence_core.models import Finding, Severity

SEVERITY_WEIGHTS: dict[Severity, int] = {
    Severity.CRITICAL: 10,
    Severity.HIGH: 6,
    Severity.MEDIUM: 3,
    Severity.LOW: 1,
    Severity.INFO: 0,
}


def score_findings(findings: list[Finding]) -> int:
    """Compute a deterministic risk score (0-100) from findings.

    The score is the capped sum of severity weights, normalized so identical
    inputs always produce identical outputs.
    """
    raw = sum(SEVERITY_WEIGHTS[f.severity] for f in findings)
    return min(raw, 100)


def risk_label(score: int) -> str:
    """Map a 0-100 score to a human label (deterministic)."""
    if score >= 70:
        return "critical"
    if score >= 40:
        return "high"
    if score >= 15:
        return "moderate"
    if score > 0:
        return "low"
    return "clean"
