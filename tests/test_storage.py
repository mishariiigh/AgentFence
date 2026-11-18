"""Tests for SQLite storage: initialization, persistence, pagination, redaction."""

from __future__ import annotations

import sqlite3
import time
import uuid
from pathlib import Path

import pytest
from agentfence_core.models import Finding, ScanResult, Severity
from agentfence_storage.database import SCHEMA_VERSION, DatabaseError, connect
from agentfence_storage.scans import ScanStore


def _finding(severity: Severity = Severity.MEDIUM) -> Finding:
    return Finding(
        id="AF-TEST",
        title="Test finding",
        severity=severity,
        category="test",
        description="desc",
        remediation="fix it",
        file="settings.json",
        evidence="api_key = sk-abcdefghij1234567890ABCD",
    )


def _result(
    target: str = "./proj/settings.json", findings: list[Finding] | None = None
) -> ScanResult:
    return ScanResult(
        target=target,
        scanner="agentfence-scanner",
        findings=list(findings) if findings else [],
        files_inspected=1,
    )


def test_database_initialization_creates_schema(tmp_path: Path) -> None:
    db = tmp_path / "sub" / "agentfence.db"
    conn = connect(db)
    version = conn.execute("SELECT MAX(version) FROM schema_version").fetchone()[0]
    assert version == SCHEMA_VERSION
    tables = {
        r[0]
        for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()
    }
    assert {"scans", "findings", "schema_version"} <= tables
    conn.close()


def test_repeated_connect_is_idempotent(tmp_path: Path) -> None:
    db = tmp_path / "agentfence.db"
    connect(db).close()
    conn = connect(db)
    assert conn.execute("SELECT COUNT(*) FROM scans").fetchone()[0] == 0
    conn.close()


def test_future_schema_version_rejected(tmp_path: Path) -> None:
    db = tmp_path / "agentfence.db"
    conn = connect(db)
    conn.close()
    c2 = sqlite3.connect(str(db))
    c2.execute("UPDATE schema_version SET version = ?", (SCHEMA_VERSION + 5,))
    c2.commit()
    c2.close()
    with pytest.raises(DatabaseError, match="newer than supported"):
        connect(db)


def test_scan_and_findings_persisted(tmp_path: Path) -> None:
    store = ScanStore(tmp_path / "agentfence.db")
    scan_id = store.save_scan(_result("./proj/settings.json", [_finding()]), "0.2.0")
    detail = store.get_scan(scan_id)
    assert detail is not None
    scan = detail["scan"]
    assert scan["target_display"] == "proj/settings.json"
    assert scan["kind"] == "scan"
    assert scan["total_findings"] == 1
    assert scan["medium_findings"] == 1
    f = detail["findings"][0]
    assert f["rule_id"] == "AF-TEST"
    assert f["severity"] == "medium"


def test_evidence_is_redacted_before_persistence(tmp_path: Path) -> None:
    store = ScanStore(tmp_path / "agentfence.db")
    scan_id = store.save_scan(_result("./a/settings.json", [_finding()]), "0.2.0")
    detail = store.get_scan(scan_id)
    evidence = detail["findings"][0]["evidence"]
    assert "sk-abcdefghij1234567890ABCD" not in evidence
    assert "[REDACTED]" in evidence
    # raw db check too
    conn = connect(tmp_path / "agentfence.db")
    raw = conn.execute("SELECT evidence FROM findings").fetchone()[0]
    conn.close()
    assert "sk-abcdefghij1234567890ABCD" not in raw


def test_persistence_across_restarts(tmp_path: Path) -> None:
    db = tmp_path / "agentfence.db"
    store = ScanStore(db)
    scan_id = store.save_scan(_result("./x/settings.json", [_finding()]), "0.2.0")
    store.close()
    # "restart": fresh store instance over the same file
    store2 = ScanStore(db)
    assert store2.get_scan(scan_id) is not None
    assert store2.summary()["total_scans"] == 1
    store2.close()


def test_pagination_and_ordering(tmp_path: Path) -> None:
    store = ScanStore(tmp_path / "agentfence.db")
    # Distinct timestamps: created_at has 1-second resolution.
    base = int(time.time())
    for i in range(5):
        ts = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(base + i * 5))
        conn = store._connection()
        scan_id = uuid.uuid4().hex
        with conn:
            conn.execute(
                "INSERT INTO scans (scan_id, created_at, target_display, target_basename,"
                " status, scanner, scanner_version, kind) VALUES (?, ?, ?, ?, 'completed',"
                " 's', '0.2.0', 'scan')",
                (scan_id, ts, f"p{i}/settings.json", f"p{i}"),
            )
    page1 = store.list_scans(limit=2, offset=0)
    page2 = store.list_scans(limit=2, offset=2)
    assert len(page1) == len(page2) == 2
    assert page1[0]["scan_id"] != page2[0]["scan_id"]
    asc = store.list_scans(limit=5, order="asc")
    desc = store.list_scans(limit=5, order="desc")
    assert asc[0]["scan_id"] == desc[-1]["scan_id"]
    assert [r["created_at"] for r in desc] == sorted(
        (r["created_at"] for r in desc), reverse=True
    )


def test_severity_filter(tmp_path: Path) -> None:
    store = ScanStore(tmp_path / "agentfence.db")
    clean_id = store.save_scan(_result("./clean/settings.json"), "0.2.0")
    dirty_id = store.save_scan(
        _result("./dirty/settings.json", [_finding(Severity.CRITICAL)]), "0.2.0"
    )
    filtered = store.list_scans(severity="critical")
    ids = {s["scan_id"] for s in filtered}
    assert dirty_id in ids
    assert clean_id not in ids
    with pytest.raises(ValueError):
        store.list_scans(severity="banana")


def test_get_unknown_scan_returns_none(tmp_path: Path) -> None:
    store = ScanStore(tmp_path / "agentfence.db")
    assert store.get_scan("nope") is None


def test_foreign_keys_enforced(tmp_path: Path) -> None:
    db = tmp_path / "agentfence.db"
    conn = connect(db)  # connect() enables foreign_keys and creates the schema
    conn.execute("PRAGMA foreign_keys = ON")
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            "INSERT INTO findings (scan_id, rule_id, title, description, severity, remediation)"
            " VALUES ('ghost', 'r', 't', 'd', 'low', 'x')"
        )
    conn.close()


def test_display_target_avoids_absolute_paths(tmp_path: Path) -> None:
    store = ScanStore(tmp_path / "agentfence.db")
    scan_id = store.save_scan(_result("/Users/someone/secretproj/settings.json"), "0.2.0")
    scan = store.get_scan(scan_id)["scan"]
    assert "/Users/someone" not in scan["target_display"]
    assert scan["target_display"] == "secretproj/settings.json"


def test_database_error_on_unopenable_path(tmp_path: Path) -> None:
    # A directory that exists as a *file* makes the db path unopenable.
    blocker = tmp_path / "blocker"
    blocker.write_text("not a directory", encoding="utf-8")
    with pytest.raises(DatabaseError):
        ScanStore(blocker / "agentfence.db").summary()
