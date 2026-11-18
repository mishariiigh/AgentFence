"""Persistence for Arena runs and policy evaluations (schema v2 tables)."""

from __future__ import annotations

import json
import sqlite3
import time
import uuid
from pathlib import Path
from typing import Any

from agentfence_core.models import Decision

from .database import DatabaseError, connect


class ArenaStore:
    """Persistence for Attack Lab scenario runs."""

    def __init__(self, db_path: Path | str) -> None:
        self._conn = connect(Path(db_path))

    def save_run(self, summary: Any) -> str:  # ArenaSummary from attack_lab
        run_id = uuid.uuid4().hex
        results = [
            {
                "scenario": r.scenario,
                "expected": r.expected.value,
                "actual": r.actual.value,
                "passed": r.passed,
                "explanation": r.explanation,
                "matched_rule": r.matched_rule,
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

    def list_runs(self, limit: int = 20, offset: int = 0) -> list[dict[str, Any]]:
        limit = max(1, min(limit, 100))
        offset = max(0, offset)
        rows = self._conn.execute(
            "SELECT run_id, created_at, status, scenario_count, passed, failed, score"
            " FROM arena_runs ORDER BY created_at DESC, run_id LIMIT ? OFFSET ?",
            (limit, offset),
        ).fetchall()
        return [dict(r) for r in rows]

    def get_run(self, run_id: str) -> dict[str, Any] | None:
        row = self._conn.execute(
            "SELECT * FROM arena_runs WHERE run_id = ?", (run_id,)
        ).fetchone()
        if row is None:
            return None
        run = dict(row)
        run["results"] = json.loads(run.pop("results_json"))
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
        rows = self._conn.execute(
            "SELECT * FROM policy_evaluations"
            " ORDER BY created_at DESC, evaluation_id LIMIT ? OFFSET ?",
            (limit, offset),
        ).fetchall()
        return [dict(r) for r in rows]
