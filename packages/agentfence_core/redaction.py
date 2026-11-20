"""Secret redaction helpers.

Any text that may contain secret material (findings evidence, logs, reports)
must pass through :func:`redact` before it is displayed or persisted.
"""

from __future__ import annotations

import re

_REPLACEMENT = "[REDACTED]"

# Patterns matching likely secret *values*. Each has a capture group around the
# secret value (group 2 for key=value patterns, group 1 otherwise) so the
# surrounding context (e.g. the key name) can be preserved.
_VALUE_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"sk-ant-[A-Za-z0-9_\-]{20,}"),          # Anthropic keys
    re.compile(r"sk-[A-Za-z0-9_\-]{20,}"),              # OpenAI-style keys
    re.compile(r"gh[pousr]_[A-Za-z0-9]{30,}"),          # GitHub tokens
    re.compile(r"github_pat_[A-Za-z0-9_]{20,}"),        # GitHub fine-grained PATs
    re.compile(r"AKIA[0-9A-Z]{16}"),                    # AWS access keys
    re.compile(r"xox[abp]-[A-Za-z0-9\-]{10,}"),         # Slack tokens
    re.compile(r"(?i)Bearer\s+[A-Za-z0-9._\-]{16,}"),   # Authorization headers
    re.compile(
        r"(?i)(api[_-]?key|secret|token|password|passwd|credential)\s*[:=]\s*[\"']?"
        r"([^\s\"']{8,})"
    ),
    # Bare secret-shaped tokens appearing anywhere (catches values inside
    # error messages, YAML snippets, URLs): a key-like word somewhere on the
    # line, followed by a long secret-like run of characters.
    re.compile(r"(?im)\b(?:api[_-]?key|secret|token|password|credential|key)\b[^\n]{0,80}?"
               r"([A-Za-z0-9_\-]{16,})"),
    # Secret-prefix tokens with no key context (OpenAI/Anthropic-style values
    # embedded in free text such as YAML error snippets).
    re.compile(r"\b(sk-[A-Za-z0-9_\-]{12,}|sk-ant-[A-Za-z0-9_\-]{12,})"),
)


def redact(text: str) -> str:
    """Redact likely secret values from ``text``, preserving surrounding context.

    Keeps the first 4 characters of a matched value so reports remain useful
    (e.g. ``sk-1[REDACTED]``) while never exposing the full secret.
    """
    out = text
    for pattern in _VALUE_PATTERNS:
        out = pattern.sub(_replace, out)
    return out


def _replace(match: re.Match[str]) -> str:
    value = match.group(0)
    if match.lastindex and match.lastindex >= 2:
        # Named group: value is group 2, group 1 is the key name prefix.
        value = match.group(2)
        prefix = match.group(0)[: match.start(2) - match.start(0)]
    else:
        prefix = ""
    return f"{prefix}{value[:4]}{_REPLACEMENT}"
