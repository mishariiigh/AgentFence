"""Tests for the FastAPI application."""

from __future__ import annotations

import json
from pathlib import Path

from agentfence_api.app import create_app
from fastapi.testclient import TestClient


def test_health() -> None:
    client = TestClient(create_app())
    r = client.get("/api/v1/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_scan_endpoint(clean_json: Path) -> None:
    client = TestClient(create_app())
    r = client.post("/api/v1/scan", json={"path": str(clean_json)})
    assert r.status_code == 200
    assert r.json()["findings"] == []


def test_scan_endpoint_missing_path() -> None:
    client = TestClient(create_app())
    r = client.post("/api/v1/scan", json={"path": "/does/not/exist"})
    assert r.status_code == 400


def test_mcp_endpoint(tmp_path: Path) -> None:
    p = tmp_path / "mcp.json"
    p.write_text(json.dumps({"mcpServers": {}}), encoding="utf-8")
    client = TestClient(create_app())
    r = client.post("/api/v1/mcp/inspect", json={"path": str(p)})
    assert r.status_code == 200
