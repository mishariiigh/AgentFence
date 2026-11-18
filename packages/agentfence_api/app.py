"""FastAPI application: health, scanning, scan history, MCP inspection.

Local-first. The API binds to localhost by default and persists scan history
in a local SQLite database under .agentfence/. Scanning stays read-only.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from agentfence_core.models import ScanResult
from agentfence_core.redaction import redact
from agentfence_mcp_inspector.inspector import McpInspectError, inspect_mcp_config
from agentfence_risk_engine.scoring import score_findings
from agentfence_scanner.engine import ScanError, scan_path
from agentfence_storage.arena_policy import ArenaStore, PolicyStore
from agentfence_storage.database import DatabaseError
from agentfence_storage.scans import ScanStore
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from agentfence_api.arena_policy import router as arena_policy_router
from agentfence_api.body_limit import body_limit_middleware
from agentfence_api.security import TOKEN_HEADER, SecurityConfig

API_VERSION = "0.2.0"

# Explicit CORS: only local dashboard dev origins are allowed by default.
DEFAULT_ALLOWED_ORIGINS = [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
]


class HealthResponse(BaseModel):
    status: str
    version: str
    service: str


class ScanRequest(BaseModel):
    path: str = Field(min_length=1)


class ScanStartedResponse(BaseModel):
    scan_id: str
    result: ScanResult
    risk_score: int


class ScanSummary(BaseModel):
    scan_id: str
    created_at: str
    target_display: str
    status: str
    scanner_version: str
    risk_score: int
    files_inspected: int
    total_findings: int
    critical_findings: int
    high_findings: int
    medium_findings: int
    low_findings: int
    info_findings: int
    kind: str


class ScanListResponse(BaseModel):
    scans: list[ScanSummary]
    total: int
    limit: int
    offset: int


class ScanDetailResponse(BaseModel):
    scan: ScanSummary
    findings: list[dict[str, Any]]


def default_db_path() -> Path:
    """Database location, overridable via AGENTFENCE_DB for tests."""
    return Path(os.environ.get("AGENTFENCE_DB", ".agentfence/agentfence.db"))


def _resolve_target(raw: str) -> Path:
    """Validate a scan target path. Rejects remote URLs and non-existent paths."""
    if "://" in raw:
        raise HTTPException(
            status_code=400,
            detail="remote URLs are not supported; provide a local filesystem path",
        )
    target = Path(raw).expanduser().resolve()
    if not target.exists():
        raise HTTPException(status_code=400, detail=f"target does not exist: {raw}")
    if not target.is_file() and not target.is_dir():
        raise HTTPException(status_code=400, detail=f"target is not a file or directory: {raw}")
    return target


def create_app(db_path: Path | None = None, security: SecurityConfig | None = None) -> FastAPI:
    store = ScanStore(db_path or default_db_path())
    sec = security or SecurityConfig()
    allowed_origins = sorted(sec.allowed_origins)

    app = FastAPI(
        title="AgentFence API",
        description=(
            "Local-first AI agent security platform API. "
            "Scanning is read-only: scanned files are never executed and "
            "agents or MCP servers are never launched. Scan history is stored "
            "in a local SQLite database; secrets are redacted before persistence."
        ),
        version=API_VERSION,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=allowed_origins,
        allow_credentials=False,
        allow_methods=["GET", "POST"],
        allow_headers=["Content-Type", TOKEN_HEADER],
    )
    # Body-size enforcement while receiving (chunked-safe, pure ASGI).
    app.add_middleware(
        lambda app: body_limit_middleware(app, max_body_bytes=sec.max_body_bytes)
    )

    # Arena + policy stores and routes (schema v2 tables).
    app.state.arena_store = ArenaStore(store.db_path)
    app.state.policy_store = PolicyStore(store.db_path)
    app.include_router(arena_policy_router)

    @app.middleware("http")
    async def local_security_middleware(request: Request, call_next: Any):  # noqa: ANN201
        reason = sec.check_request(
            request.method,
            {k.lower(): v for k, v in request.headers.items()},
            request.client.host if request.client else "unknown",
        )
        if reason:
            return JSONResponse(status_code=403, content={"detail": reason})
        return await call_next(request)

    @app.get("/api/v1/health", response_model=HealthResponse)
    def health() -> HealthResponse:
        return HealthResponse(status="ok", version=API_VERSION, service="agentfence-api")

    @app.post("/api/v1/scan", response_model=ScanStartedResponse)
    def scan(request: ScanRequest) -> ScanStartedResponse:
        """Scan a local path (read-only), persist the result, and return it."""
        target = _resolve_target(request.path)
        try:
            result = scan_path(target)
        except ScanError as exc:
            raise HTTPException(status_code=400, detail=redact(str(exc))[:300]) from exc
        try:
            scan_id = store.save_scan(result, scanner_version=API_VERSION)
        except DatabaseError as exc:
            raise HTTPException(status_code=500, detail=redact(str(exc))[:300]) from exc
        return ScanStartedResponse(
            scan_id=scan_id, result=result, risk_score=score_findings(result.findings)
        )

    @app.get("/api/v1/scans", response_model=ScanListResponse)
    def list_scans(
        limit: int = 20,
        offset: int = 0,
        order: str = "desc",
        severity: str | None = None,
    ) -> ScanListResponse:
        """Paginated scan history, newest first by default."""
        try:
            scans = store.list_scans(limit=limit, offset=offset, order=order, severity=severity)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        except DatabaseError as exc:
            raise HTTPException(status_code=500, detail=redact(str(exc))[:300]) from exc
        try:
            total = store.summary()["total_scans"]
        except DatabaseError as exc:
            raise HTTPException(status_code=500, detail=redact(str(exc))[:300]) from exc
        return ScanListResponse(
            scans=[ScanSummary.model_validate(s) for s in scans],
            total=total,
            limit=limit,
            offset=offset,
        )

    @app.get("/api/v1/scans/{scan_id}", response_model=ScanDetailResponse)
    def get_scan(scan_id: str) -> ScanDetailResponse:
        try:
            detail = store.get_scan(scan_id)
        except DatabaseError as exc:
            raise HTTPException(status_code=500, detail=redact(str(exc))[:300]) from exc
        if detail is None:
            raise HTTPException(status_code=404, detail=f"scan not found: {scan_id}")
        return ScanDetailResponse(
            scan=ScanSummary.model_validate(detail["scan"]),
            findings=detail["findings"],
        )

    @app.get("/api/v1/summary")
    def summary() -> dict[str, int]:
        """Aggregate counts for the dashboard overview."""
        try:
            return store.summary()
        except DatabaseError as exc:
            raise HTTPException(status_code=500, detail=redact(str(exc))[:300]) from exc

    @app.post("/api/v1/mcp/inspect", response_model=ScanStartedResponse)
    def mcp_inspect(request: ScanRequest) -> ScanStartedResponse:
        """Inspect a local MCP configuration file (read-only) and persist the result."""
        target = _resolve_target(request.path)
        try:
            result = inspect_mcp_config(target)
        except McpInspectError as exc:
            raise HTTPException(status_code=400, detail=redact(str(exc))[:300]) from exc
        try:
            scan_id = store.save_scan(
                result, scanner_version=API_VERSION, kind="mcp_inspection"
            )
        except DatabaseError as exc:
            raise HTTPException(status_code=500, detail=redact(str(exc))[:300]) from exc
        return ScanStartedResponse(
            scan_id=scan_id, result=result, risk_score=score_findings(result.findings)
        )

    return app


app = create_app()
