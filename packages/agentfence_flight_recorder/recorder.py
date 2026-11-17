"""AgentFence flight recorder — local audit log of AgentFence activity.

Records a tamper-evident, append-only JSONL log of what AgentFence itself
did on this machine (scans run, scenarios evaluated). Local-only by design:
the log is never uploaded anywhere.
"""

from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path
from typing import Any

from agentfence_core.redaction import redact

DEFAULT_LOG_PATH = Path(".agentfence") / "audit.jsonl"


class FlightRecorder:
    """Append-only, hash-chained JSONL audit log (local only)."""

    def __init__(self, path: Path = DEFAULT_LOG_PATH) -> None:
        self.path = path

    def record(self, event: str, details: dict[str, Any] | None = None) -> None:
        entry = {
            "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "event": event,
            "details": _redact_deep(details or {}),
            "prev_hash": self._last_hash(),
        }
        entry["hash"] = hashlib.sha256(
            json.dumps(entry, sort_keys=True).encode("utf-8")
        ).hexdigest()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(entry, sort_keys=True) + "\n")

    def _last_hash(self) -> str:
        if not self.path.exists():
            return "0" * 64
        last_line = ""
        with self.path.open("r", encoding="utf-8") as fh:
            for line in fh:
                if line.strip():
                    last_line = line
        try:
            return json.loads(last_line)["hash"]
        except (json.JSONDecodeError, KeyError):
            return "0" * 64


def _redact_deep(value: Any) -> Any:  # noqa: ANN401 — recursive normalizer
    if isinstance(value, str):
        return redact(value)
    if isinstance(value, dict):
        return {k: _redact_deep(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_redact_deep(v) for v in value]
    return value
