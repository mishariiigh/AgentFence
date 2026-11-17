"""AgentFence report generator — renders scan results as reports."""

from __future__ import annotations

import json
from pathlib import Path

from agentfence_core.models import ScanResult
from agentfence_core.redaction import redact
from agentfence_risk_engine.scoring import risk_label, score_findings


def report_json(result: ScanResult) -> str:
    """Render a scan result as pretty JSON (secrets redacted)."""
    return json.dumps(result.model_dump(mode="json"), indent=2, default=redact_json_strings)


def redact_json_strings(obj: object) -> str:  # noqa: ANN401 — json default hook
    return redact(str(obj))


def report_markdown(result: ScanResult) -> str:
    """Render a scan result as a Markdown report."""
    score = score_findings(result.findings)
    counts = result.counts_by_severity
    lines = [
        f"# AgentFence Report — {result.target}",
        "",
        f"- Scanner: `{result.scanner}`",
        f"- Files inspected: {result.files_inspected}",
        f"- Risk score: {score}/100 ({risk_label(score)})",
        f"- Findings: {len(result.findings)} "
        f"(critical: {counts['critical']}, high: {counts['high']}, "
        f"medium: {counts['medium']}, low: {counts['low']}, info: {counts['info']})",
        "",
    ]
    if result.notes:
        lines += ["## Notes", *(f"- {n}" for n in result.notes), ""]
    if result.findings:
        lines.append("## Findings")
        for i, f in enumerate(result.findings, start=1):
            lines += [
                f"### {i}. [{f.severity.value.upper()}] {f.title}",
                "",
                f"- **ID:** `{f.id}`",
                f"- **Category:** {f.category}",
                f"- **File:** {f.file or 'n/a'}",
                f"- **Description:** {f.description}",
                f"- **Remediation:** {f.remediation}",
            ]
            if f.evidence:
                lines.append(f"- **Evidence:** `{f.evidence}`")
            lines.append("")
    else:
        lines += ["## Findings", "No findings.", ""]
    lines.append(
        "_Read-only static inspection. No files were executed, no agents or MCP "
        "servers were launched, and secret values are redacted._"
    )
    return "\n".join(lines)


def save_report(result: ScanResult, path: Path, fmt: str = "json") -> Path:
    """Write a report to ``path``. Format: 'json' or 'md'."""
    content = report_json(result) if fmt == "json" else report_markdown(result)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return path
