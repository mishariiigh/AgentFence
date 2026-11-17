"""FastAPI application factory with health and scanner endpoints."""

from __future__ import annotations

from pathlib import Path

from agentfence_core.models import ScanResult
from agentfence_mcp_inspector.inspector import McpInspectError, inspect_mcp_config
from agentfence_scanner.engine import ScanError, scan_path
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

API_VERSION = "0.1.0"


class HealthResponse(BaseModel):
    status: str
    version: str
    service: str


class ScanRequest(BaseModel):
    path: str


def create_app() -> FastAPI:
    app = FastAPI(
        title="AgentFence API",
        description=(
            "Local-first AI agent security platform API. "
            "Scanning is read-only: scanned files are never executed and "
            "agents or MCP servers are never launched."
        ),
        version=API_VERSION,
    )

    @app.get("/api/v1/health", response_model=HealthResponse)
    def health() -> HealthResponse:
        return HealthResponse(status="ok", version=API_VERSION, service="agentfence-api")

    @app.post("/api/v1/scan", response_model=ScanResult)
    def scan(request: ScanRequest) -> ScanResult:
        """Scan a local path (read-only). The path must exist on this machine."""
        target = Path(request.path)
        try:
            return scan_path(target)
        except ScanError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/api/v1/mcp/inspect", response_model=ScanResult)
    def mcp_inspect(request: ScanRequest) -> ScanResult:
        """Inspect a local MCP configuration file (read-only)."""
        target = Path(request.path)
        try:
            return inspect_mcp_config(target)
        except McpInspectError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    return app


app = create_app()
