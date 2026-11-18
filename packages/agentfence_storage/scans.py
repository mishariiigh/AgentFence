"""Scan history persistence (scans + findings)."""

from __future__ import annotations

import sqlite3
import time
import uuid
from pathlib import Path
from typing import Any

from agentfence_core.models import ScanResult, Severity
from agentfence_core.redaction import redact
from agentfence_risk_engine.scoring import score_findings

from .database import DatabaseError, connect

_SEVERITY_COLUMNS = {
    Severity.CRITICAL: "critical_findings",
    Severity.HIGH: "high_findings",
    Severity.MEDIUM: "medium_findings",
    Severity.LOW: "low_findings",
    Severity.INFO: "info_findings",
}


def _display_target(target: str) -> str:
    """Avoid storing sensitive absolute paths; keep a relative-looking display."""
    p = Path(target)
    name = p.name or target
    parent = p.parent.name if p.parent.name and p.parent.name not in ("/", ".") else "."
    return f"{parent}/{name}" if parent != "." else name


class ScanStore:
    """Persistence for scans and their findings (parameterized SQL throughout)."""

    def __init__(self, db_path: Path | str) -> None:
        self.db_path = Path(db_path)
        self._conn: sqlite3.Connection | None = None

    def _connection(self) -> sqlite3.Connection:
        if self._conn is None:
            self._conn = connect(self.db_path)
        return self._conn

    def close(self) -> None:
        if self._conn is not None:
            self._conn.close()
            self._conn = None

    def save_scan(self, result: ScanResult, scanner_version: str, kind: str = "scan") -> str:
        """Persist a ScanResult and its (redacted) findings atomically."""
        conn = self._connection()
        scan_id = uuid.uuid4().hex
        counts = {s: 0 for s in Severity}
        for f in result.findings:
            counts[f.severity] += 1
        try:
            with conn:
                conn.execute(
                    """
                    INSERT INTO scans (
                        scan_id, created_at, target_display, target_basename, status,
                        scanner, scanner_version, risk_score, files_inspected,
                        total_findings, critical_findings, high_findings,
                        medium_findings, low_findings, info_findings, kind
                    ) VALUES (?, ?, ?, ?, 'completed', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        scan_id,
                        time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                        _display_target(result.target),
                        Path(result.target).name or result.target,
                        result.scanner,
                        scanner_version,
                        score_findings(result.findings),
                        result.files_inspected,
                        len(result.findings),
                        counts[Severity.CRITICAL],
                        counts[Severity.HIGH],
                        counts[Severity.MEDIUM],
                        counts[Severity.LOW],
                        counts[Severity.INFO],
                        kind,
                    ),
                )
                for f in result.findings:
                    conn.execute(
                        """
                        INSERT INTO findings (
                            scan_id, rule_id, title, description, severity,
                            file_ref, remediation, evidence
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            scan_id,
                            f.id,
                            f.title,
                            f.description,
                            f.severity.value,
                            f.file,
                            f.remediation,
                            redact(f.evidence) if f.evidence else None,
                        ),
                    )
        except sqlite3.Error as exc:
            raise DatabaseError(f"could not persist scan: {exc}") from exc
        return scan_id

    def list_scans(
        self,
        limit: int = 20,
        offset: int = 0,
        order: str = "desc",
        severity: str | None = None,
    ) -> list[dict[str, Any]]:
        """Return paginated scans sorted by creation date (newest first by default)."""
        if order not in {"asc", "desc"}:
            raise ValueError("order must be 'asc' or 'desc'")
        limit = max(1, min(limit, 100))
        offset = max(0, offset)
        conn = self._connection()
        where = ""
        if severity is not None:
            # severity is validated against the fixed severity name set below.
            if severity not in {s.value for s in Severity}:
                raise ValueError(f"unknown severity filter: {severity}")
            where = f"WHERE {severity}_findings > 0"
        try:
            rows = conn.execute(
                f"SELECT * FROM scans {where} ORDER BY created_at {order}, scan_id "
                "LIMIT ? OFFSET ?",
                (limit, offset),
            ).fetchall()
        except sqlite3.Error as exc:
            raise DatabaseError(f"could not list scans: {exc}") from exc
        return [dict(r) for r in rows]

    def get_scan(self, scan_id: str) -> dict[str, Any] | None:
        conn = self._connection()
        try:
            scan = conn.execute(
                "SELECT * FROM scans WHERE scan_id = ?", (scan_id,)
            ).fetchone()
            if scan is None:
                return None
            findings = conn.execute(
                "SELECT * FROM findings WHERE scan_id = ? ORDER BY finding_pk", (scan_id,)
            ).fetchall()
        except sqlite3.Error as exc:
            raise DatabaseError(f"could not read scan: {exc}") from exc
        return {"scan": dict(scan), "findings": [dict(f) for f in findings]}

    def summary(self) -> dict[str, int]:
        """Aggregate counts for the dashboard overview."""
        conn = self._connection()
        try:
            row = conn.execute(
                """
                SELECT COUNT(*) AS total_scans,
                       COALESCE(SUM(total_findings), 0) AS total_findings,
                       COALESCE(SUM(critical_findings), 0) AS critical,
                       COALESCE(SUM(high_findings), 0) AS high,
                       COALESCE(SUM(medium_findings), 0) AS medium,
                       COALESCE(SUM(low_findings), 0) AS low,
                       COALESCE(SUM(info_findings), 0) AS info
                FROM scans
                """
            ).fetchone()
        except sqlite3.Error as exc:
            raise DatabaseError(f"could not summarize: {exc}") from exc
        return dict(row)
