"""Arena and Policies API routes.

Arena: executes the existing declarative scenario engine (agentfence_attack_lab)
against built-in deterministic policies. Policy: validates and evaluates via the
existing deterministic policy engine (agentfence_policy_engine). No LLM, no
payload execution, no external systems.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
from agentfence_attack_lab.runner import run_scenarios
from agentfence_attack_lab.scenarios import ScenarioError, load_scenarios
from agentfence_policy_engine.evaluator import evaluate
from agentfence_policy_engine.policy import (
    PolicyValidationError,
    parse_policy,
    validate_policy_text,
)
from agentfence_storage.arena_policy import ArenaStore, PolicyStore
from agentfence_storage.database import DatabaseError
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

router = APIRouter()

# Directory containing bundled declarative scenarios (read-only data).
SCENARIO_DIRS = [Path("benchmarks/scenarios"), Path(".agentfence/scenarios")]


class ArenaRunRequest(BaseModel):
    scenario_ids: list[str] | None = Field(
        default=None, description="Subset of scenario names to run; empty/None = all."
    )


class ScenarioInfo(BaseModel):
    name: str
    description: str
    tags: list[str]
    expected_decision: str


class ArenaRunResult(BaseModel):
    scenario: str
    expected: str
    actual: str
    passed: bool
    explanation: str
    matched_rule: str | None


class ArenaRunResponse(BaseModel):
    run_id: str
    total: int
    passed: int
    failed: int
    score: float
    results: list[ArenaRunResult]


class ArenaRunSummary(BaseModel):
    run_id: str
    created_at: str
    status: str
    scenario_count: int
    passed: int
    failed: int
    score: float


class ArenaRunListResponse(BaseModel):
    runs: list[ArenaRunSummary]
    total: int
    limit: int
    offset: int


class PolicyValidateRequest(BaseModel):
    content: str = Field(min_length=1, max_length=64_000)


class PolicyEvaluateRequest(BaseModel):
    name: str | None = Field(default=None, description="Name of a listed policy.")
    content: str | None = Field(default=None, description="Inline policy YAML.")
    action: str = Field(min_length=1, max_length=200)
    resource: str = Field(min_length=1, max_length=500)


def _scenario_dirs() -> list[Path]:
    return [p for p in SCENARIO_DIRS if p.is_dir()]


def _load_all_scenarios() -> list[Any]:
    dirs = _scenario_dirs()
    if not dirs:
        return []
    return load_scenarios(dirs)


@router.get("/api/v1/arena/scenarios", response_model=list[ScenarioInfo])
def list_arena_scenarios() -> list[ScenarioInfo]:
    try:
        scenarios = _load_all_scenarios()
    except ScenarioError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return [
        ScenarioInfo(
            name=s.name,
            description=s.description,
            tags=s.tags,
            expected_decision=s.expected.decision.value,
        )
        for s in scenarios
    ]


def _resolve_scenarios(request: ArenaRunRequest) -> list[Any]:
    scenarios = _load_all_scenarios()
    if not scenarios:
        raise HTTPException(status_code=404, detail="no scenarios available")
    if request.scenario_ids:
        by_name = {s.name: s for s in scenarios}
        unknown = [sid for sid in request.scenario_ids if sid not in by_name]
        if unknown:
            raise HTTPException(
                status_code=422, detail=f"unknown scenario id(s): {', '.join(unknown)}"
            )
        if len(request.scenario_ids) > 50:
            raise HTTPException(status_code=422, detail="too many scenarios requested")
        return [by_name[sid] for sid in request.scenario_ids]
    return scenarios


@router.post("/api/v1/arena/run", response_model=ArenaRunResponse)
def run_arena(request: ArenaRunRequest, http_request: Request) -> ArenaRunResponse:
    store: ArenaStore = http_request.app.state.arena_store
    scenarios = _resolve_scenarios(request)
    summary = run_scenarios(scenarios)  # existing deterministic runner; nothing executed
    try:
        run_id = store.save_run(summary)
    except DatabaseError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return ArenaRunResponse(
        run_id=run_id,
        total=summary.total,
        passed=summary.passed,
        failed=summary.failed,
        score=summary.pass_rate,
        results=[
            ArenaRunResult(
                scenario=r.scenario,
                expected=r.expected.value,
                actual=r.actual.value,
                passed=r.passed,
                explanation=r.explanation,
                matched_rule=r.matched_rule,
            )
            for r in summary.results
        ],
    )


@router.get("/api/v1/arena/runs", response_model=ArenaRunListResponse)
def list_arena_runs(
    request: Request, limit: int = 20, offset: int = 0
) -> ArenaRunListResponse:
    store: ArenaStore = request.app.state.arena_store
    try:
        runs = store.list_runs(limit=limit, offset=offset)
    except DatabaseError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    total_row = store._conn.execute("SELECT COUNT(*) AS c FROM arena_runs").fetchone()
    return ArenaRunListResponse(
        runs=[ArenaRunSummary.model_validate(r) for r in runs],
        total=int(total_row["c"]),
        limit=max(1, min(limit, 100)),
        offset=max(0, offset),
    )


@router.get("/api/v1/arena/runs/{run_id}")
def get_arena_run(run_id: str, request: Request) -> dict[str, Any]:
    store: ArenaStore = request.app.state.arena_store
    run = store.get_run(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail=f"arena run not found: {run_id}")
    return run


# ---------------------------------------------------------------------------
# Policies
# ---------------------------------------------------------------------------


@router.get("/api/v1/policies")
def list_policies() -> dict[str, Any]:
    """List bundled example policies (YAML files in policies/ and .agentfence/policies/)."""
    dirs = [Path("policies"), Path(".agentfence/policies")]
    items: list[dict[str, Any]] = []
    for d in dirs:
        if not d.is_dir():
            continue
        for p in sorted(d.glob("*.y*ml")):
            try:
                text = p.read_text(encoding="utf-8")
                policy = parse_policy(yaml.safe_load(text) or {}, str(p))
                problems: list[str] = []
            except (PolicyValidationError, yaml.YAMLError) as exc:
                policy = None
                problems = [str(exc)]
            items.append(
                {
                    "name": policy.name if policy else p.stem,
                    "file": p.name,
                    "directory": str(d),
                    "valid": policy is not None,
                    "problems": problems,
                    "default": policy.default.value if policy else None,
                    "rule_count": len(policy.rules) if policy else 0,
                    "rules": (
                        [
                            {
                                "id": r.id,
                                "action": r.action,
                                "resource": r.resource,
                                "decision": r.decision.value,
                                "description": r.description,
                            }
                            for r in policy.rules
                        ]
                        if policy
                        else []
                    ),
                }
            )
    return {"policies": items}


@router.post("/api/v1/policies/validate")
def validate_policy(request: PolicyValidateRequest) -> dict[str, Any]:
    """Validate an inline policy YAML document. Nothing is written to disk."""
    problems = validate_policy_text(request.content)
    return {"valid": not problems, "problems": problems}


@router.post("/api/v1/policies/evaluate")
def evaluate_policy(request: PolicyEvaluateRequest, http_request: Request) -> dict[str, Any]:
    """Evaluate action/resource against a named or inline policy (deterministic)."""
    store: PolicyStore = http_request.app.state.policy_store
    if request.name is None and request.content is None:
        raise HTTPException(
            status_code=422, detail="provide either 'name' of a listed policy or inline 'content'"
        )
    if request.name is not None and request.content is not None:
        raise HTTPException(status_code=422, detail="provide only one of 'name' or 'content'")

    raw: dict[str, Any] | None = None
    if request.content is not None:
        try:
            raw = yaml.safe_load(request.content)
        except yaml.YAMLError as exc:
            evaluation_id = store.save_evaluation(
                policy_name="(inline)",
                policy_valid=False,
                action=request.action,
                resource=request.resource,
                decision=None,
                matched_rule=None,
                explanation=f"policy YAML is invalid: {exc}",
            )
            raise HTTPException(
                status_code=422,
                detail={
                    "message": "policy YAML is invalid",
                    "problems": [str(exc)],
                    "evaluation_id": evaluation_id,
                },
            ) from exc
        source = "(inline)"
    else:
        dirs = [Path("policies"), Path(".agentfence/policies")]
        found: Path | None = None
        for d in dirs:
            if not d.is_dir():
                continue
            for p in sorted(d.glob("*.y*ml")):
                try:
                    candidate = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
                except yaml.YAMLError:
                    continue
                if isinstance(candidate, dict) and candidate.get("name") == request.name:
                    found = p
                    raw = candidate
                    break
            if found:
                break
        if raw is None:
            raise HTTPException(status_code=404, detail=f"policy not found: {request.name}")
        source = str(found)

    try:
        policy = parse_policy(raw or {}, source)
    except PolicyValidationError as exc:
        evaluation_id = store.save_evaluation(
            policy_name=str(raw.get("name", "?")) if isinstance(raw, dict) else "?",
            policy_valid=False,
            action=request.action,
            resource=request.resource,
            decision=None,
            matched_rule=None,
            explanation=f"policy is invalid: {exc}",
        )
        raise HTTPException(
            status_code=422,
            detail={
                "message": f"policy '{source}' is invalid — refusing to evaluate",
                "problems": exc.errors,
                "evaluation_id": evaluation_id,
            },
        ) from exc

    decision = evaluate(policy, request.action, request.resource)
    store.save_evaluation(
        policy_name=policy.name,
        policy_valid=True,
        action=request.action,
        resource=request.resource,
        decision=decision.decision,
        matched_rule=decision.matched_rule,
        explanation=decision.explanation,
    )
    return {
        "policy": policy.name,
        "action": request.action,
        "resource": request.resource,
        "decision": decision.decision.value,
        "matched_rule": decision.matched_rule,
        "explanation": decision.explanation,
    }


@router.get("/api/v1/policies/history")
def policy_history(request: Request, limit: int = 20, offset: int = 0) -> dict[str, Any]:
    store: PolicyStore = request.app.state.policy_store
    try:
        items = store.list_evaluations(limit=limit, offset=offset)
    except DatabaseError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return {"evaluations": items, "limit": limit, "offset": offset}
