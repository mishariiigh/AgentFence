"""SQLite database management: connection, initialization, migrations."""

from __future__ import annotations

import sqlite3
from pathlib import Path

SCHEMA_VERSION = 1

_MIGRATIONS: dict[int, tuple[str, ...]] = {
    1: (
        """
        CREATE TABLE IF NOT EXISTS schema_version (
            version INTEGER NOT NULL
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS scans (
            scan_id TEXT PRIMARY KEY,
            created_at TEXT NOT NULL,
            target_display TEXT NOT NULL,
            target_basename TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'completed',
            scanner TEXT NOT NULL,
            scanner_version TEXT NOT NULL,
            risk_score INTEGER NOT NULL DEFAULT 0,
            files_inspected INTEGER NOT NULL DEFAULT 0,
            total_findings INTEGER NOT NULL DEFAULT 0,
            critical_findings INTEGER NOT NULL DEFAULT 0,
            high_findings INTEGER NOT NULL DEFAULT 0,
            medium_findings INTEGER NOT NULL DEFAULT 0,
            low_findings INTEGER NOT NULL DEFAULT 0,
            info_findings INTEGER NOT NULL DEFAULT 0,
            kind TEXT NOT NULL DEFAULT 'scan'
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS findings (
            finding_pk INTEGER PRIMARY KEY AUTOINCREMENT,
            scan_id TEXT NOT NULL REFERENCES scans(scan_id) ON DELETE CASCADE,
            rule_id TEXT NOT NULL,
            title TEXT NOT NULL,
            description TEXT NOT NULL,
            severity TEXT NOT NULL,
            file_ref TEXT,
            remediation TEXT NOT NULL,
            evidence TEXT
        )
        """,
        "CREATE INDEX IF NOT EXISTS idx_scans_created ON scans(created_at DESC)",
        "CREATE INDEX IF NOT EXISTS idx_findings_scan ON findings(scan_id)",
    ),
}


class DatabaseError(Exception):
    """Raised when the local database cannot be opened or migrated."""


def connect(db_path: Path) -> sqlite3.Connection:
    """Open (creating if needed) the SQLite database and apply migrations."""
    try:
        db_path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(str(db_path))
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        _migrate(conn)
        return conn
    except (sqlite3.Error, OSError) as exc:
        raise DatabaseError(f"could not open database {db_path}: {exc}") from exc


def _migrate(conn: sqlite3.Connection) -> None:
    current = _get_version(conn)
    if current > SCHEMA_VERSION:
        raise DatabaseError(
            f"database schema version {current} is newer than supported "
            f"version {SCHEMA_VERSION}; upgrade AgentFence"
        )
    for version in range(current + 1, SCHEMA_VERSION + 1):
        statements = _MIGRATIONS[version]
        with conn:
            for statement in statements:
                conn.execute(statement)
            conn.execute("DELETE FROM schema_version")
            conn.execute("INSERT INTO schema_version (version) VALUES (?)", (version,))


def _get_version(conn: sqlite3.Connection) -> int:
    try:
        row = conn.execute("SELECT MAX(version) AS v FROM schema_version").fetchone()
        return int(row["v"] or 0)
    except sqlite3.OperationalError:
        return 0
