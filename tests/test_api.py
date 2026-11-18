"""Tests for the FastAPI application (health, scan, history, MCP, errors)."""

from __future__ import annotations

import json
from pathlib import Path

from agentfence_api.app import create_app
from fastapi.testclient import TestClient


def _client(tmp_path: Path) -> TestClient:
    return TestClient(create_app(db_path=tmp_path / "agentfence.db"))


def test_health(tmp_path: Path) -> None:
    r = _client(tmp_path).get("/api/v1/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_scan_persists_and_returns_scan_id(tmp_path: Path, clean_json: Path) -> None:
    client = _client(tmp_path)
    r = client.post("/api/v1/scan", json={"path": str(clean_json)})
    assert r.status_code == 200
    body = r.json()
    assert body["scan_id"]
    assert body["result"]["findings"] == []
    assert body["risk_score"] == 0
    # history now contains the scan
    hist = client.get("/api/v1/scans").json()
    assert hist["total"] == 1
    assert hist["scans"][0]["scan_id"] == body["scan_id"]


def test_scan_endpoint_missing_path(tmp_path: Path) -> None:
    client = _client(tmp_path)
    r = client.post("/api/v1/scan", json={"path": "/does/not/exist"})
    assert r.status_code == 400


def test_scan_rejects_remote_url(tmp_path: Path) -> None:
    client = _client(tmp_path)
    r = client.post("/api/v1/scan", json={"path": "https://evil.example.com/config"})
    assert r.status_code == 400
    assert "remote" in r.json()["detail"]


def test_scan_rejects_empty_path(tmp_path: Path) -> None:
    client = _client(tmp_path)
    r = client.post("/api/v1/scan", json={"path": ""})
    assert r.status_code == 422


def test_get_scan_detail_with_findings(tmp_path: Path, settings_json: Path) -> None:
    client = _client(tmp_path)
    scan_id = client.post("/api/v1/scan", json={"path": str(settings_json)}).json()["scan_id"]
    detail = client.get(f"/api/v1/scans/{scan_id}")
    assert detail.status_code == 200
    body = detail.json()
    assert body["scan"]["scan_id"] == scan_id
    rule_ids = {f["rule_id"] for f in body["findings"]}
    assert any(rid.endswith("AUTO_APPROVE_ALL") for rid in rule_ids)
    # no unredacted secrets in the response
    assert "sk-" not in json.dumps(body).replace("agentfence", "")


def test_get_unknown_scan_404(tmp_path: Path) -> None:
    client = _client(tmp_path)
    r = client.get("/api/v1/scans/deadbeef")
    assert r.status_code == 404


def test_scan_list_pagination(tmp_path: Path, clean_json: Path) -> None:
    client = _client(tmp_path)
    for _ in range(3):
        client.post("/api/v1/scan", json={"path": str(clean_json)})
    r = client.get("/api/v1/scans", params={"limit": 2, "offset": 0})
    body = r.json()
    assert len(body["scans"]) == 2
    assert body["total"] == 3
    r2 = client.get("/api/v1/scans", params={"limit": 2, "offset": 2})
    assert len(r2.json()["scans"]) == 1


def test_scan_list_severity_filter(tmp_path: Path, clean_json: Path, settings_json: Path) -> None:
    client = _client(tmp_path)
    client.post("/api/v1/scan", json={"path": str(clean_json)})
    client.post("/api/v1/scan", json={"path": str(settings_json)})
    r = client.get("/api/v1/scans", params={"severity": "critical"})
    assert r.status_code == 200
    assert all(s["critical_findings"] > 0 for s in r.json()["scans"])


def test_summary_endpoint(tmp_path: Path, settings_json: Path) -> None:
    client = _client(tmp_path)
    client.post("/api/v1/scan", json={"path": str(settings_json)})
    s = client.get("/api/v1/summary").json()
    assert s["total_scans"] == 1
    assert s["total_findings"] >= 1


def test_mcp_endpoint_persists(tmp_path: Path) -> None:
    p = tmp_path / "mcp.json"
    p.write_text(json.dumps({"mcpServers": {}}), encoding="utf-8")
    client = _client(tmp_path)
    r = client.post("/api/v1/mcp/inspect", json={"path": str(p)})
    assert r.status_code == 200
    scan_id = r.json()["scan_id"]
    detail = client.get(f"/api/v1/scans/{scan_id}").json()
    assert detail["scan"]["kind"] == "mcp_inspection"


def test_cors_allows_local_dashboard_origin(tmp_path: Path) -> None:
    client = _client(tmp_path)
    r = client.options(
        "/api/v1/health",
        headers={"Origin": "http://localhost:3000", "Access-Control-Request-Method": "GET"},
    )
    assert r.status_code == 200
    assert r.headers["access-control-allow-origin"] == "http://localhost:3000"


def test_cors_rejects_unknown_origin(tmp_path: Path) -> None:
    client = _client(tmp_path)
    r = client.options(
        "/api/v1/health",
        headers={"Origin": "https://evil.example.com", "Access-Control-Request-Method": "GET"},
    )
    assert "access-control-allow-origin" not in r.headers
