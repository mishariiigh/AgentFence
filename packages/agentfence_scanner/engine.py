"""The read-only scanner engine."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import yaml
from agentfence_core.models import Finding, ScanResult
from agentfence_core.redaction import redact

from . import rules
from .signatures import classify

MAX_FILE_BYTES = 512 * 1024  # refuse to slurp huge files


class ScanError(Exception):
    """Raised when a target cannot be scanned."""


def scan_path(target: Path) -> ScanResult:
    """Statically inspect configuration files under ``target``. Read-only."""
    if not target.exists():
        raise ScanError(f"target does not exist: {target}")

    result = ScanResult(target=str(target), scanner="agentfence-scanner")
    files = [target] if target.is_file() else sorted(
        p for p in target.rglob("*") if p.is_file() and not _is_ignored(p)
    )
    for path in files:
        kind = classify(path.name)
        if kind is None:
            continue
        result.files_inspected += 1
        result.findings.extend(_inspect_file(path))
    result.notes.append(
        "Read-only static inspection: no files were executed and no agents were launched."
    )
    return result


def _is_ignored(path: Path) -> bool:
    parts = {p.lower() for p in path.parts}
    return bool(
        parts & {".git", "node_modules", ".venv", "venv", "__pycache__", "dist", ".next"}
    )


def _inspect_file(path: Path) -> list[Finding]:
    findings: list[Finding] = []
    try:
        raw = path.read_text(encoding="utf-8", errors="replace")[:MAX_FILE_BYTES]
    except OSError as exc:
        f = Finding(
            id="AF-UNREADABLE",
            title="File could not be read",
            severity="low",
            category="scanner",
            description=f"Skipping unreadable file: {exc}",
            remediation="Check file permissions.",
            file=str(path),
        )
        findings.append(f)
        return findings

    # Secrets: report pattern type only, with redacted evidence.
    for key in rules.detect_hardcoded_secrets(raw):
        match = next(
            p for k, p in rules._SECRET_LINE_PATTERNS if k == key  # noqa: SLF001 — internal reuse
        ).search(raw)
        f = Finding(
            id=f"AF-SECRET-{key.upper()}",
            title=f"Potential hardcoded secret ({key})",
            severity="high",
            category="secrets",
            description=(
                f"File contains text matching a {key} pattern. "
                "Move the value to an environment variable or secret manager."
            ),
            remediation=(
                "Remove the secret from the file; rotate the credential if it was committed."
            ),
            file=str(path),
            evidence=redact(match.group(0)) if match else None,
        )
        findings.append(f)

    # Structured checks on parseable configs.
    data: Any = None
    suffix = path.suffix.lower()
    name = path.name.lower()
    try:
        if suffix == ".json" or name.endswith(".json"):
            data = json.loads(raw)
        elif suffix in {".yaml", ".yml"}:
            data = yaml.safe_load(raw)
    except (json.JSONDecodeError, yaml.YAMLError) as exc:
        f = Finding(
            id="AF-PARSE-ERROR",
            title="Configuration file failed to parse",
            severity="low",
            category="scanner",
            description=f"Could not parse as JSON/YAML: {exc.__class__.__name__}",
            remediation="Fix the syntax so automated inspection can evaluate the file.",
            file=str(path),
        )
        findings.append(f)
    else:
        if isinstance(data, dict):
            for f in rules.inspect_mapping(data, str(path)):
                findings.append(f)
    return findings
