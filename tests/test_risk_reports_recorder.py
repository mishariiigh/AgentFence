"""Tests for risk scoring, report generation, and the flight recorder."""

from __future__ import annotations

import json
from pathlib import Path

from agentfence_core.models import Finding, ScanResult, Severity
from agentfence_flight_recorder.recorder import FlightRecorder
from agentfence_report_generator.reports import report_json, report_markdown, save_report
from agentfence_risk_engine.scoring import risk_label, score_findings


def _finding(severity: Severity) -> Finding:
    return Finding(
        id="AF-X",
        title="t",
        severity=severity,
        category="c",
        description="d",
        remediation="r",
    )


def test_scoring_is_deterministic() -> None:
    findings = [_finding(Severity.HIGH), _finding(Severity.MEDIUM)]
    assert score_findings(findings) == score_findings(findings) == 9
    assert score_findings([]) == 0


def test_score_caps_at_100() -> None:
    assert score_findings([_finding(Severity.CRITICAL)] * 20) == 100


def test_risk_labels() -> None:
    assert risk_label(0) == "clean"
    assert risk_label(5) == "low"
    assert risk_label(20) == "moderate"
    assert risk_label(50) == "high"
    assert risk_label(90) == "critical"


def test_markdown_report_contains_redacted_evidence() -> None:
    result = ScanResult(
        target="x",
        scanner="s",
        findings=[_finding(Severity.HIGH)],
        files_inspected=1,
    )
    md = report_markdown(result)
    assert "AgentFence Report" in md
    assert "HIGH" in md


def test_save_report(tmp_path: Path) -> None:
    result = ScanResult(target="x", scanner="s")
    out = save_report(result, tmp_path / "reports" / "r.json")
    assert out.exists()
    assert json.loads(out.read_text(encoding="utf-8"))["target"] == "x"


def test_flight_recorder_hash_chain(tmp_path: Path) -> None:
    rec = FlightRecorder(tmp_path / "audit.jsonl")
    long_secret = "sk-proj-abcdefghij1234567890ABCD"
    rec.record("scan", {"target": "a", "secret": long_secret})
    rec.record("scan", {"target": "b"})
    content = (tmp_path / "audit.jsonl").read_text(encoding="utf-8")
    lines = [json.loads(line) for line in content.splitlines()]
    assert len(lines) == 2
    assert lines[1]["prev_hash"] == lines[0]["hash"]
    # secret is redacted in the log
    assert long_secret not in json.dumps(lines)
    assert "[REDACTED]" in json.dumps(lines)


def test_json_report_is_valid_json() -> None:
    result = ScanResult(target="x", scanner="s")
    assert json.loads(report_json(result))["target"] == "x"
