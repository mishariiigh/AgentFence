"""Security remediation tests: redaction, body limits, token file, Host parsing."""

from __future__ import annotations

import json
import stat
from pathlib import Path

import pytest
from agentfence_api.app import create_app
from agentfence_api.security import (
    TOKEN_HEADER,
    SecurityConfig,
    parse_host_authority,
)
from agentfence_storage.database import connect
from fastapi.testclient import TestClient


def _client(tmp_path: Path, **sec_kwargs: object) -> TestClient:
    sec = SecurityConfig(token="tok", rate_limit=1000, **sec_kwargs)  # type: ignore[arg-type]
    client = TestClient(create_app(db_path=tmp_path / "db.sqlite", security=sec))
    original_post = client.post

    def post(path: str, **kwargs: object) -> object:
        headers = dict(kwargs.pop("headers", {}) or {})
        headers[TOKEN_HEADER] = "tok"
        return original_post(path, headers=headers, **kwargs)  # type: ignore[arg-type]

    client.post = post  # type: ignore[method-assign]
    return client


SECRET = "sk-test-secret-value-1234567890"


# ---------------------------------------------------------------------------
# 1. Policy-history redaction (persisted records, not just API responses)
# ---------------------------------------------------------------------------


def test_policy_error_persistence_is_redacted_in_db(tmp_path: Path) -> None:
    """A secret embedded in invalid YAML must never reach SQLite."""
    client = _client(tmp_path)
    # Put the secret on the same line as the YAML error so the parser's
    # context snippet (included in the error message) would carry it.
    yaml_with_secret = f"name: [broken, {SECRET}"
    r = client.post(
        "/api/v1/policies/evaluate",
        json={"content": yaml_with_secret, "action": "read", "resource": "docs/*"},
    )
    assert r.status_code == 422

    # Raw database inspection
    conn = connect(tmp_path / "db.sqlite")
    rows = conn.execute(
        "SELECT explanation, policy_name, action, resource FROM policy_evaluations"
    ).fetchall()
    conn.close()
    blob = json.dumps([dict(r) for r in rows])
    assert SECRET not in blob
    assert "[REDACTED]" in blob


def test_policy_evaluation_details_redacted_in_db(tmp_path: Path) -> None:
    """Secrets in action/resource values must not persist either."""
    client = _client(tmp_path)
    policy = "name: p\n"
    client.post(
        "/api/v1/policies/evaluate",
        json={
            "content": policy,
            "action": f"read?token={SECRET}",
            "resource": f"docs/{SECRET}",
        },
    )
    conn = connect(tmp_path / "db.sqlite")
    rows = conn.execute("SELECT action, resource FROM policy_evaluations").fetchall()
    conn.close()
    blob = json.dumps([dict(r) for r in rows])
    assert SECRET not in blob
    assert "[REDACTED]" in blob


def test_policy_validation_api_response_redacted(tmp_path: Path) -> None:
    client = _client(tmp_path)
    r = client.post("/api/v1/policies/validate", json={"content": f"name: '{SECRET}' [x"})
    assert r.status_code == 200
    assert r.json()["valid"] is False
    assert SECRET not in json.dumps(r.json())


def test_arena_run_persistence_redacted_in_db(tmp_path: Path) -> None:
    """Arena explanations stored in the DB must not contain secret material."""
    client = _client(tmp_path)
    run_id = client.post("/api/v1/arena/run", json={}).json()["run_id"]
    conn = connect(tmp_path / "db.sqlite")
    row = conn.execute(
        "SELECT results_json FROM arena_runs WHERE run_id = ?", (run_id,)
    ).fetchone()
    conn.close()
    results = json.loads(row[0])
    # All scenario fields must be plain strings, and no raw secret patterns survive
    for result in results:
        assert isinstance(result["explanation"], str)
        assert SECRET not in result["explanation"]


# ---------------------------------------------------------------------------
# 2. Request-body limits
# ---------------------------------------------------------------------------


def test_oversized_body_rejected_with_413(tmp_path: Path) -> None:
    client = _client(tmp_path, max_body_bytes=100)
    r = client.post(
        "/api/v1/policies/validate",
        json={"content": "x" * 500},
        headers={TOKEN_HEADER: "tok"},
    )
    assert r.status_code == 413


def test_missing_content_length_chunked_body_still_limited(tmp_path: Path) -> None:
    """Chunked request without Content-Length must also be size-limited."""
    sec = SecurityConfig(token="tok", rate_limit=1000, max_body_bytes=100)
    app = create_app(db_path=tmp_path / "db.sqlite", security=sec)

    # Hand-craft an ASGI request without content-length, body larger than cap.
    payload = json.dumps({"content": "x" * 500}).encode()

    async def receive() -> dict:  # type: ignore[type-arg]
        return {"type": "http.request", "body": payload, "more_body": False}

    scope = {
        "type": "http",
        "method": "POST",
        "path": "/api/v1/policies/validate",
        "headers": [
            (b"host", b"testserver"),
            (b"content-type", b"application/json"),
            (b"x-agentfence-session", b"tok"),
        ],
        "query_string": b"",
        "client": ("127.0.0.1", 12345),
    }
    sent: list[dict] = []  # type: ignore[type-arg]

    async def send(message: dict) -> None:  # type: ignore[type-arg]
        sent.append(message)

    import asyncio

    async def call() -> None:
        await app(scope, receive, send)  # type: ignore[arg-type]

    asyncio.run(call())
    status = sent[0]["status"]
    assert status == 413


def test_normal_body_accepted_and_reaches_endpoint(tmp_path: Path) -> None:
    client = _client(tmp_path, max_body_bytes=64_000)
    r = client.post(
        "/api/v1/policies/validate",
        json={"content": "name: p\n"},
        headers={TOKEN_HEADER: "tok"},
    )
    assert r.status_code == 200
    assert r.json()["valid"] is True


def test_exact_limit_body_accepted(tmp_path: Path) -> None:
    client = _client(tmp_path, max_body_bytes=4096)
    content = "x" * 3900  # under limit once JSON-encoded
    r = client.post(
        "/api/v1/policies/validate",
        json={"content": content},
        headers={TOKEN_HEADER: "tok"},
    )
    assert r.status_code == 200


# ---------------------------------------------------------------------------
# 3. Token file security
# ---------------------------------------------------------------------------


def test_permissive_existing_token_file_is_tightened(tmp_path: Path, monkeypatch) -> None:
    db = tmp_path / "db.sqlite"
    monkeypatch.setenv("AGENTFENCE_DB", str(db))
    token_path = tmp_path / ".api-token"
    token_path.write_text("existing-token-value", encoding="utf-8")
    token_path.chmod(0o644)
    token = SecurityConfig.load_or_create_token()
    assert token == "existing-token-value"  # preserved across restart
    assert (token_path.stat().st_mode & 0o777) == 0o600


def test_symlinked_token_file_is_replaced(tmp_path: Path, monkeypatch) -> None:
    db = tmp_path / "db.sqlite"
    monkeypatch.setenv("AGENTFENCE_DB", str(db))
    target = tmp_path / "innocent.txt"
    target.write_text("not a token", encoding="utf-8")
    link = tmp_path / ".api-token"
    link.symlink_to(target)
    token = SecurityConfig.load_or_create_token()
    assert token and len(token) >= 32
    assert not link.is_symlink()
    assert link.is_file()
    assert (link.stat().st_mode & 0o777) == 0o600
    # the symlink target is untouched
    assert target.read_text(encoding="utf-8") == "not a token"


def test_directory_at_token_path_is_replaced(tmp_path: Path, monkeypatch) -> None:
    db = tmp_path / "db.sqlite"
    monkeypatch.setenv("AGENTFENCE_DB", str(db))
    (tmp_path / ".api-token").mkdir()
    token = SecurityConfig.load_or_create_token()
    assert len(token) >= 32
    assert (tmp_path / ".api-token").is_file()


def test_token_creation_mode_is_0600_from_start(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("AGENTFENCE_DB", str(tmp_path / "db.sqlite"))
    token = SecurityConfig.load_or_create_token()
    path = tmp_path / ".api-token"
    assert path.read_text(encoding="utf-8") == token
    assert stat.S_IMODE(path.stat().st_mode) == 0o600


# ---------------------------------------------------------------------------
# 4. Host / Origin validation
# ---------------------------------------------------------------------------


def test_parse_host_authority_variants() -> None:
    assert parse_host_authority("localhost") == "localhost"
    assert parse_host_authority("localhost:3000") == "localhost"
    assert parse_host_authority("127.0.0.1:8000") == "127.0.0.1"
    assert parse_host_authority("[::1]:8000") == "::1"
    assert parse_host_authority("::1") == "::1"


def test_parse_host_authority_rejects_malformed() -> None:
    for bad in ("", "   ", "user@host", "host with space", "host\ttab", "a\nb"):
        with pytest.raises(ValueError):
            parse_host_authority(bad)


def test_missing_host_rejected(tmp_path: Path) -> None:
    client = _client(tmp_path)
    r = client.get("/api/v1/health", headers={"Host": ""})
    assert r.status_code == 403


def test_wildcard_bind_host_rejected(tmp_path: Path) -> None:
    client = _client(tmp_path)
    r = client.get("/api/v1/health", headers={"Host": "0.0.0.0"})
    assert r.status_code == 403


def test_ipv6_loopback_host_accepted(tmp_path: Path) -> None:
    client = _client(tmp_path)
    r = client.get("/api/v1/health", headers={"Host": "[::1]:8000"})
    assert r.status_code == 200


def test_host_with_port_accepted(tmp_path: Path) -> None:
    client = _client(tmp_path)
    r = client.get("/api/v1/health", headers={"Host": "localhost:8000"})
    assert r.status_code == 200


def test_untrusted_portless_host_rejected(tmp_path: Path) -> None:
    client = _client(tmp_path)
    r = client.get("/api/v1/health", headers={"Host": "rebind.attacker.net"})
    assert r.status_code == 403


def test_mutation_with_invalid_origin_but_valid_token_rejected(tmp_path: Path) -> None:
    client = _client(tmp_path)
    r = client.post(
        "/api/v1/policies/validate",
        json={"content": "name: p"},
        headers={TOKEN_HEADER: "tok", "Origin": "https://evil.example.com"},
    )
    assert r.status_code == 403


def test_mutation_without_origin_and_valid_token_allowed(tmp_path: Path) -> None:
    """Non-browser clients (curl/CLI/tests) may omit Origin; token is required."""
    client = _client(tmp_path)
    r = client.post("/api/v1/policies/validate", json={"content": "name: p\n"})
    assert r.status_code == 200


def test_mutation_from_allowed_origin_accepted(tmp_path: Path) -> None:
    client = _client(tmp_path)
    r = client.post(
        "/api/v1/policies/validate",
        json={"content": "name: p\n"},
        headers={TOKEN_HEADER: "tok", "Origin": "http://localhost:3000"},
    )
    assert r.status_code == 200


def test_get_with_invalid_origin_allowed(tmp_path: Path) -> None:
    """Origin checks apply to mutations; GET responses carry no secrets here."""
    client = _client(tmp_path)
    r = client.get("/api/v1/health", headers={"Origin": "https://evil.example.com"})
    assert r.status_code == 200
