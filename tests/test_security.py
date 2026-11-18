"""Security tests: session token, Origin/Host validation, rate & size limits."""

from __future__ import annotations

from pathlib import Path

from agentfence_api.app import create_app
from agentfence_api.security import TOKEN_HEADER, SecurityConfig
from fastapi.testclient import TestClient


def _client(tmp_path: Path, **sec_kwargs: object) -> TestClient:
    sec = SecurityConfig(token="tok", rate_limit=1000, **sec_kwargs)  # type: ignore[arg-type]
    return TestClient(create_app(db_path=tmp_path / "db.sqlite", security=sec))


def test_mutation_without_token_rejected(tmp_path: Path) -> None:
    client = _client(tmp_path)
    r = client.post("/api/v1/scan", json={"path": "."})
    assert r.status_code == 403
    assert "session token" in r.json()["detail"]


def test_mutation_with_wrong_token_rejected(tmp_path: Path) -> None:
    client = TestClient(
        create_app(
            db_path=tmp_path / "db.sqlite",
            security=SecurityConfig(token="real", rate_limit=1000),
        )
    )
    r = client.post("/api/v1/scan", json={"path": "."}, headers={TOKEN_HEADER: "wrong"})
    assert r.status_code == 403


def test_health_get_does_not_need_token(tmp_path: Path) -> None:
    assert _client(tmp_path).get("/api/v1/health").status_code == 200


def test_foreign_origin_rejected_on_mutation(tmp_path: Path) -> None:
    client = _client(tmp_path)
    r = client.post(
        "/api/v1/scan",
        json={"path": "."},
        headers={TOKEN_HEADER: "tok", "Origin": "https://evil.example.com"},
    )
    assert r.status_code == 403
    assert "Origin" in r.json()["detail"]


def test_local_dashboard_origin_accepted(tmp_path: Path) -> None:
    client = _client(tmp_path)
    r = client.post(
        "/api/v1/scan",
        json={"path": "."},
        headers={TOKEN_HEADER: "tok", "Origin": "http://localhost:3000"},
    )
    assert r.status_code != 403  # may 400 (path), but not security-rejected


def test_dns_rebinding_host_rejected(tmp_path: Path) -> None:
    client = _client(tmp_path)
    r = client.get(
        "/api/v1/health",
        headers={"Host": "evil.example.com"},
    )
    assert r.status_code == 403
    assert "Host" in r.json()["detail"]


def test_local_host_accepted(tmp_path: Path) -> None:
    client = _client(tmp_path)
    r = client.get("/api/v1/health", headers={"Host": "127.0.0.1:8000"})
    assert r.status_code == 200


def test_rate_limit_blocks_flooding(tmp_path: Path) -> None:
    client = TestClient(
        create_app(
            db_path=tmp_path / "db.sqlite",
            security=SecurityConfig(token="tok", rate_limit=3, rate_window_seconds=60),
        )
    )
    for _ in range(3):
        assert (
            client.post(
                "/api/v1/scan",
                json={"path": "."},
                headers={TOKEN_HEADER: "tok"},
            ).status_code
            != 403
        )
    r = client.post("/api/v1/scan", json={"path": "."}, headers={TOKEN_HEADER: "tok"})
    assert r.status_code == 403
    assert "rate limit" in r.json()["detail"]


def test_oversized_body_rejected(tmp_path: Path) -> None:
    client = _client(tmp_path, max_body_bytes=10)
    r = client.post(
        "/api/v1/policies/validate",
        json={"content": "x" * 100},
        headers={TOKEN_HEADER: "tok"},
    )
    assert r.status_code == 413


def test_token_file_created_with_restrictive_permissions(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("AGENTFENCE_DB", str(tmp_path / "db.sqlite"))
    token = SecurityConfig.load_or_create_token()
    path = tmp_path / ".api-token"
    assert path.exists()
    assert len(token) >= 32
    assert (path.stat().st_mode & 0o777) == 0o600
    # Reload returns the same token (stability across restarts)
    assert SecurityConfig.load_or_create_token() == token
