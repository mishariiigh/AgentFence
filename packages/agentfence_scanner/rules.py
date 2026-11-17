"""Read-only inspection rules for agent configuration contents.

Rules are pure functions over parsed configuration data. Nothing in this
module reads commands, spawns processes, or executes code from scanned files.
"""

from __future__ import annotations

import re
from typing import Any

from agentfence_core.models import Finding, Severity

# ---------------------------------------------------------------------------
# Secrets detection (safe patterns; values are redacted before display)
# ---------------------------------------------------------------------------

_SECRET_LINE_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("openai_key", re.compile(r"sk-[A-Za-z0-9_\-]{20,}")),
    ("anthropic_key", re.compile(r"sk-ant-[A-Za-z0-9_\-]{20,}")),
    ("github_token", re.compile(r"gh[pousr]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{20,}")),
    ("aws_key", re.compile(r"AKIA[0-9A-Z]{16}")),
    ("slack_token", re.compile(r"xox[abp]-[A-Za-z0-9\-]{10,}")),
    (
        "assigned_secret",
        re.compile(
            r"(?i)(api[_-]?key|secret|token|password|passwd|credential)\s*[:=]\s*[\"']?"
            r"([^\s\"']{8,})"
        ),
    ),
)


def detect_hardcoded_secrets(text: str) -> list[str]:
    """Return the rule keys of secret patterns present in ``text`` (values never returned raw)."""
    return [key for key, pattern in _SECRET_LINE_PATTERNS if pattern.search(text)]


def _finding(
    fid: str,
    title: str,
    severity: Severity,
    description: str,
    remediation: str,
    category: str = "configuration",
) -> Finding:
    return Finding(
        id=fid,
        title=title,
        severity=severity,
        category=category,
        description=description,
        remediation=remediation,
    )


# ---------------------------------------------------------------------------
# Structured rule evaluation
# ---------------------------------------------------------------------------

# (key in settings) -> whether that key enabling/being non-empty is risky
_PERMISSION_KEYS: dict[str, tuple[Severity, str, str]] = {
    "allow_unsafe_permissions": (
        Severity.HIGH,
        "Unsafe permissions explicitly allowed",
        "Remove 'allow_unsafe_permissions' and enumerate required permissions explicitly.",
    ),
    "auto_approve_all": (
        Severity.CRITICAL,
        "All tool calls auto-approved",
        "Disable 'auto_approve_all'; use explicit allow-lists with approval gates.",
    ),
    "disable_sandbox": (
        Severity.HIGH,
        "Sandbox disabled",
        "Keep the sandbox enabled; scope exceptions narrowly.",
    ),
}


def inspect_mapping(data: dict[str, Any], source: str) -> list[Finding]:
    """Inspect a parsed settings mapping for risky permissions and patterns."""
    findings: list[Finding] = []
    flat = _flatten(data)

    for key, (severity, title, remediation) in _PERMISSION_KEYS.items():
        # Flat keys are dotted paths; match on the leaf key name.
        if any(k.split(".")[-1] == key for k in flat) and any(
            _truthy(v) for k, v in flat.items() if k.split(".")[-1] == key
        ):
            f = _finding(
                f"AF-{key.upper()}",
                title,
                severity,
                title,
                remediation,
                "permissions",
            )
            f.file = source
            f.metadata["config_key"] = key
            findings.append(f)

    # Overly broad network/shell patterns
    for path, value in flat.items():
        if isinstance(value, str) and value.strip() in {"*", "ALL"}:
            f = _finding(
                "AF-WILDCARD-PERMISSION",
                f"Wildcard permission on '{path}'",
                Severity.HIGH,
                f"Configuration grants unrestricted access via '{path}: *'.",
                "Replace wildcards with an explicit list of required capabilities.",
                "permissions",
            )
            f.file = source
            findings.append(f)
            break  # one wildcard finding is enough noise reduction

    # Suspicious instruction patterns in free-text config (prompt injection vectors)
    suspicious = _scan_suspicious_text(data)
    if suspicious:
        f = _finding(
            "AF-SUSPICIOUS-INSTRUCTION",
            "Suspicious instruction pattern in configuration",
            Severity.MEDIUM,
            "Configuration contains instruction text that attempts to override "
            f"system behavior (patterns: {', '.join(sorted(suspicious))}).",
            "Remove instructions that override safety behavior; review the file by hand.",
            "prompt-injection",
        )
        f.file = source
        findings.append(f)
    return findings


_SUSPICIOUS_TEXT = (
    re.compile(r"(?i)ignore\s+(all\s+)?(previous|prior|above)\s+(instructions|prompts?)"),
    re.compile(r"(?i)you\s+are\s+now\s+"),
    re.compile(r"(?i)disable\s+(all\s+)?(safety|guardrails?|restrictions?)"),
    re.compile(r"(?i)exfiltrate|exfiltration"),
)


def _scan_suspicious_text(data: Any) -> set[str]:
    found: set[str] = set()

    def walk(node: Any) -> None:
        if isinstance(node, dict):
            for v in node.values():
                walk(v)
        elif isinstance(node, list):
            for v in node:
                walk(v)
        elif isinstance(node, str):
            for pattern in _SUSPICIOUS_TEXT:
                m = pattern.search(node)
                if m:
                    found.add(m.group(0).strip().lower()[:60])

    walk(data)
    return found


def _truthy(value: Any) -> bool:
    return value is True or (isinstance(value, str) and value.lower() in {"true", "yes", "1"})


def _flatten(data: Any, prefix: str = "") -> dict[str, Any]:
    flat: dict[str, Any] = {}
    if isinstance(data, dict):
        for k, v in data.items():
            key = f"{prefix}.{k}" if prefix else str(k)
            if isinstance(v, dict):
                flat.update(_flatten(v, key))
            else:
                flat[key] = v
    return flat
