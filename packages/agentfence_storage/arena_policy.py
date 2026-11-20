"""Persistence for Arena runs and policy evaluations (schema v2 tables).

All free-text content (policy names, explanations, action/resource strings)
passes through the core redaction layer before an INSERT, so submitted YAML
or error text cannot leak credentials into SQLite.
"""

from __future__ import annotations

import json
import sqlite3
import time
import uuid
from pathlib import Path
from typing import Any

from agentfence_core.models import Decision
from agentfence_core.redaction import redact

from .database import DatabaseError, connect


class ArenaStore:
    """Persistence for Attack Lab scenario runs."""

    def __init__(self, db_path: Path | str) -> None:
        self._conn = connect(Path(db_path))

    def save_run(self, summary: Any) -> str:  # ArenaSummary from attack_lab
        """Persist an Arena run; explanations are redacted before storage."""
        run_id = uuid.uuid4().hex
        results = [
            {
                "scenario": redact(r.scenario)[:200],
                "expected": r.expected.value,
                "actual": r.actual.value,
                "passed": r.passed,
                "explanation": redact(r.explanation)[:2000],
                "matched_rule": redact(r.matched_rule)[:200] if r.matched_rule else None,
            }
            for r in summary.results
        ]
        try:
            with self._conn:
                self._conn.execute(
                    """
                    INSERT INTO arena_runs (
                        run_id, created_at, status, scenario_count,
                        passed, failed, score, results_json
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        run_id,
                        time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                        "completed",
                        summary.total,
                        summary.passed,
                        summary.failed,
                        summary.pass_rate,
                        json.dumps(results),
                    ),
                )
        except sqlite3.Error as exc:
            raise DatabaseError(f"could not persist arena run: {exc}") from exc
        return run_id

    def list_runs(self, limit: int = 20, offset: int = 0) -> tuple[list[dict[str, Any]], int]:
        """Return (runs, total) paginated newest-first."""
        limit = max(1, min(limit, 100))
        offset = max(0, offset)
        try:
            rows = self._conn.execute(
                "SELECT run_id, created_at, status, scenario_count, passed, failed, score"
                " FROM arena_runs ORDER BY created_at DESC, run_id LIMIT ? OFFSET ?",
                (limit, offset),
            ).fetchall()
            total = self._conn.execute("SELECT COUNT(*) AS c FROM arena_runs").fetchone()[0]
        except sqlite3.Error as exc:
            raise DatabaseError(f"could not list arena runs: {exc}") from exc
        return [dict(r) for r in rows], int(total)

    def get_run(self, run_id: str) -> dict[str, Any] | None:
        try:
            row = self._conn.execute(
                "SELECT * FROM arena_runs WHERE run_id = ?", (run_id,)
            ).fetchone()
            if row is None:
                return None
            run = dict(row)
            run["results"] = json.loads(run.pop("results_json"))
        except sqlite3.Error as exc:
            raise DatabaseError(f"could not read arena run: {exc}") from exc
        return run


class PolicyStore:
    """Persistence for policy evaluation history."""

    def __init__(self, db_path: Path | str) -> None:
        self._conn = connect(Path(db_path))

    def save_evaluation(
        self,
        policy_name: str,
        policy_valid: bool,
        action: str,
        resource: str,
        decision: Decision | None,
        matched_rule: str | None,
        explanation: str,
    ) -> str:
        """Persist an evaluation with all free text redacted first."""
        policy_name = redact(policy_name)[:120]
        action = redact(action)[:200]
        resource = redact(resource)[:500]
        matched_rule = redact(matched_rule)[:200] if matched_rule else None
        explanation = redact(explanation)[:2000]
        evaluation_id = uuid.uuid4().hex
        try:
            with self._conn:
                self._conn.execute(
                    """
                    INSERT INTO policy_evaluations (
                        evaluation_id, created_at, policy_name, policy_valid,
                        action, resource, decision, matched_rule, explanation
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        evaluation_id,
                        time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                        policy_name,
                        1 if policy_valid else 0,
                        action,
                        resource,
                        decision.value if decision else "invalid_policy",
                        matched_rule,
                        explanation,
                    ),
                )
        except sqlite3.Error as exc:
            raise DatabaseError(f"could not persist evaluation: {exc}") from exc
        return evaluation_id

    def list_evaluations(self, limit: int = 20, offset: int = 0) -> list[dict[str, Any]]:
        limit = max(1, min(limit, 100))
        offset = max(0, offset)
        try:
            rows = self._conn.execute(
                "SELECT * FROM policy_evaluations"
                " ORDER BY created_at DESC, evaluation_id LIMIT ? OFFSET ?",
                (limit, offset),
            ).fetchall()
        except sqlite3.Error as exc:
            raise DatabaseError(f"could not list policy evaluations: {exc}") from exc
        return [dict(r) for r in rows]
