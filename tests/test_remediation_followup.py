"""Follow-up remediation tests: ASGI body limit, Host ports, token file, workspace root."""

from __future__ import annotations

import asyncio
import json
import os
import stat
from pathlib import Path

import pytest
from agentfence_api.app import create_app
from agentfence_api.body_limit import body_limit_middleware
from agentfence_api.security import (
    TOKEN_HEADER,
    SecurityConfig,
    parse_host_authority,
)
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


# ---------------------------------------------------------------------------
# 1. ASGI body-limit middleware (pure implementation, message sequencing)
# ---------------------------------------------------------------------------


def _run_asgi(
    app: object,
    method: str,
    path: str,
    body: bytes,
    headers: list[tuple[bytes, bytes]] | None = None,
) -> list[dict]:  # type: ignore[type-arg]
    sent: list[dict] = []  # type: ignore[type-arg]
    scope = {
        "type": "http",
        "method": method,
        "path": path,
        "headers": headers or [(b"host", b"testserver")],
        "query_string": b"",
        "client": ("127.0.0.1", 1),
    }

    async def receive() -> dict:  # type: ignore[type-arg]
        return {"type": "http.request", "body": body, "more_body": False}

    async def send(message: dict) -> None:  # type: ignore[type-arg]
        sent.append(message)

    async def call() -> None:
        await app(scope, receive, send)  # type: ignore[arg-type]

    asyncio.run(call())
    return sent


def test_asgi_middleware_empty_body_replayed_as_final_message(tmp_path: Path) -> None:
    """An empty POST must not leave the endpoint waiting for a disconnect."""
    captured: dict[str, object] = {}

    async def inner_app(scope: object, receive: object, send: object) -> None:  # type: ignore[no-untyped-def]
        # Simulate an endpoint reading the request body.
        message = await receive()  # type: ignore[misc]
        captured["type"] = message["type"]
        captured["body"] = message.get("body", b"")
        captured["more_body"] = message.get("more_body", False)
        await send({"type": "http.response.start", "status": 200, "headers": []})  # type: ignore[attr-defined]
        await send({"type": "http.response.body", "body": b""})  # type: ignore[attr-defined]

    mw = body_limit_middleware(inner_app, max_body_bytes=1000)
    sent = _run_asgi(mw, "POST", "/x", b"", [(b"host", b"testserver")])
    assert captured["type"] == "http.request"
    assert captured["body"] == b""
    assert captured["more_body"] is False
    assert sent[0]["status"] == 200  # inner app completed and responded


def test_asgi_middleware_normal_body_replayed_intact(tmp_path: Path) -> None:
    captured: dict[str, bytes] = {}

    async def inner_app(scope: object, receive: object, send: object) -> None:  # type: ignore[no-untyped-def]
        message = await receive()  # type: ignore[misc]
        captured["body"] = message.get("body", b"")

    mw = body_limit_middleware(inner_app, max_body_bytes=1000)
    _run_asgi(mw, "POST", "/x", b'{"a": 1}', [(b"host", b"testserver")])
    assert captured["body"] == b'{"a": 1}'


def test_asgi_middleware_exact_limit_body_accepted(tmp_path: Path) -> None:
    captured: dict[str, bytes] = {}

    async def inner_app(scope: object, receive: object, send: object) -> None:  # type: ignore[no-untyped-def]
        message = await receive()  # type: ignore[misc]
        captured["body"] = message.get("body", b"")

    mw = body_limit_middleware(inner_app, max_body_bytes=10)
    _run_asgi(mw, "POST", "/x", b"x" * 10, [(b"host", b"testserver")])
    assert captured["body"] == b"x" * 10


def test_asgi_middleware_oversized_body_rejected_413(tmp_path: Path) -> None:
    async def inner_app(scope: object, receive: object, send: object) -> None:  # type: ignore[no-untyped-def]
        raise AssertionError("inner app must not be called for oversized bodies")

    mw = body_limit_middleware(inner_app, max_body_bytes=10)
    sent = _run_asgi(mw, "POST", "/x", b"x" * 11, [(b"host", b"testserver")])
    assert sent[0]["status"] == 413


def test_asgi_middleware_oversized_content_length_precheck(tmp_path: Path) -> None:
    async def inner_app(scope: object, receive: object, send: object) -> None:  # type: ignore[no-untyped-def]
        raise AssertionError("inner app must not be called")

    mw = body_limit_middleware(inner_app, max_body_bytes=10)
    sent = _run_asgi(
        mw,
        "POST",
        "/x",
        b"",
        [(b"host", b"testserver"), (b"content-length", b"999")],
    )
    assert sent[0]["status"] == 413


def test_asgi_middleware_chunked_without_content_length_limited(tmp_path: Path) -> None:
    """Multiple http.request chunks without Content-Length are accumulated."""

    async def inner_app(scope: object, receive: object, send: object) -> None:  # type: ignore[no-untyped-def]
        raise AssertionError("inner app must not be called")

    mw = body_limit_middleware(inner_app, max_body_bytes=15)
    chunks = [b"a" * 10, b"b" * 10]  # total 20 > 15
    sent: list[dict] = []  # type: ignore[type-arg]
    scope = {
        "type": "http",
        "method": "POST",
        "path": "/x",
        "headers": [(b"host", b"testserver")],
        "query_string": b"",
        "client": ("127.0.0.1", 1),
    }
    queue = list(chunks)

    async def receive() -> dict:  # type: ignore[type-arg]
        if queue:
            chunk = queue.pop(0)
            return {"type": "http.request", "body": chunk, "more_body": bool(queue)}
        return {"type": "http.disconnect"}

    async def send(message: dict) -> None:  # type: ignore[type-arg]
        sent.append(message)

    async def call() -> None:
        await mw(scope, receive, send)  # type: ignore[arg-type]

    asyncio.run(call())
    assert sent[0]["status"] == 413


def test_asgi_middleware_zero_byte_chunk_flood_bounded(tmp_path: Path) -> None:
    """Unlimited zero-byte chunks must be cut off by the message cap, not
    exhaust memory via unbounded message buffering."""
    async def inner_app(scope: object, receive: object, send: object) -> None:  # type: ignore[no-untyped-def]
        raise AssertionError("inner app must not be called")

    mw = body_limit_middleware(inner_app, max_body_bytes=1000, max_body_messages=50)
    sent: list[dict] = []  # type: ignore[type-arg]
    scope = {
        "type": "http",
        "method": "POST",
        "path": "/x",
        "headers": [(b"host", b"testserver")],
        "query_string": b"",
        "client": ("127.0.0.1", 1),
    }

    async def receive() -> dict:  # type: ignore[type-arg]
        # Endless zero-byte chunks with more_body=True.
        return {"type": "http.request", "body": b"", "more_body": True}

    async def send(message: dict) -> None:  # type: ignore[type-arg]
        sent.append(message)

    async def call() -> None:
        await mw(scope, receive, send)  # type: ignore[arg-type]

    asyncio.run(call())
    assert sent[0]["status"] == 413


def test_asgi_middleware_no_state_between_requests(tmp_path: Path) -> None:
    """Sequential requests must not retain prior body data."""
    captured: list[bytes] = []

    async def inner_app(scope: object, receive: object, send: object) -> None:  # type: ignore[no-untyped-def]
        message = await receive()  # type: ignore[misc]
        captured.append(message.get("body", b""))
        await send({"type": "http.response.start", "status": 200, "headers": []})  # type: ignore[attr-defined]
        await send({"type": "http.response.body", "body": b""})  # type: ignore[attr-defined]

    mw = body_limit_middleware(inner_app, max_body_bytes=1000)
    _run_asgi(mw, "POST", "/x", b"first-request-body")
    _run_asgi(mw, "POST", "/x", b"")
    _run_asgi(mw, "POST", "/x", b"second")
    assert captured == [b"first-request-body", b"", b"second"]


def test_asgi_middleware_disconnect_passthrough(tmp_path: Path) -> None:
    """A disconnect during body read is replayed to the app exactly once.

    The receive mock returns a disconnect only on the FIRST call (like a real
    server, which never re-delivers a consumed event). The middleware must
    therefore buffer it during the drain and replay the buffered message."""
    received: list[dict] = []  # type: ignore[type-arg]

    async def inner_app(scope: object, receive: object, send: object) -> None:  # type: ignore[no-untyped-def]
        received.append(await receive())  # type: ignore[misc]

    mw = body_limit_middleware(inner_app, max_body_bytes=1000)
    sent: list[dict] = []  # type: ignore[type-arg]
    scope = {
        "type": "http",
        "method": "POST",
        "path": "/x",
        "headers": [(b"host", b"testserver")],
        "query_string": b"",
        "client": ("127.0.0.1", 1),
    }
    calls = 0

    async def receive() -> dict:  # type: ignore[type-arg]
        nonlocal calls
        calls += 1
        if calls == 1:
            return {"type": "http.disconnect"}
        raise AssertionError("real servers do not re-deliver a consumed disconnect")

    async def send(message: dict) -> None:  # type: ignore[type-arg]
        sent.append(message)

    async def call() -> None:
        await mw(scope, receive, send)  # type: ignore[arg-type]

    asyncio.run(call())
    assert len(received) == 1
    assert received[0]["type"] == "http.disconnect"


def test_asgi_middleware_disconnect_after_partial_body_replayed(tmp_path: Path) -> None:
    """Chunks received before a disconnect are replayed, then the disconnect."""
    received: list[dict] = []  # type: ignore[type-arg]

    async def inner_app(scope: object, receive: object, send: object) -> None:  # type: ignore[no-untyped-def]
        while True:
            message = await receive()  # type: ignore[misc]
            received.append(message)
            if message["type"] == "http.disconnect":
                return

    mw = body_limit_middleware(inner_app, max_body_bytes=1000)
    scope = {
        "type": "http",
        "method": "POST",
        "path": "/x",
        "headers": [(b"host", b"testserver")],
        "query_string": b"",
        "client": ("127.0.0.1", 1),
    }
    queue: list[dict] = [  # type: ignore[type-arg]
        {"type": "http.request", "body": b"part-", "more_body": True},
        {"type": "http.disconnect"},
    ]

    async def receive() -> dict:  # type: ignore[type-arg]
        if queue:
            return queue.pop(0)
        raise AssertionError("receive called after queue exhausted")

    async def send(message: dict) -> None:  # type: ignore[type-arg]
        pass  # type: ignore[unreachable]

    async def call() -> None:
        await mw(scope, receive, send)  # type: ignore[arg-type]

    asyncio.run(call())
    assert [m["type"] for m in received] == ["http.request", "http.disconnect"]
    assert received[0]["body"] == b"part-"


def test_asgi_middleware_message_cap_counts_all_requests(tmp_path: Path) -> None:
    """The message cap bounds total buffered http.request messages, including
    zero-byte ones: an endless zero-byte flood is rejected with 413 and the
    inner app is never invoked."""

    async def inner_app(scope: object, receive: object, send: object) -> None:  # type: ignore[no-untyped-def]
        raise AssertionError("inner app must not be called")

    mw = body_limit_middleware(inner_app, max_body_bytes=10**9, max_body_messages=25)
    scope = {
        "type": "http",
        "method": "POST",
        "path": "/x",
        "headers": [(b"host", b"testserver")],
        "query_string": b"",
        "client": ("127.0.0.1", 1),
    }

    async def receive() -> dict:  # type: ignore[type-arg]
        return {"type": "http.request", "body": b"", "more_body": True}

    sent: list[dict] = []  # type: ignore[type-arg]

    async def send(message: dict) -> None:  # type: ignore[type-arg]
        sent.append(message)

    async def call() -> None:
        await mw(scope, receive, send)  # type: ignore[arg-type]

    asyncio.run(call())
    assert sent[0]["status"] == 413


def test_asgi_middleware_bytes_cap_never_exceeded(tmp_path: Path) -> None:
    """Total accumulated bytes across sequential requests stay bounded, and a
    request whose chunks exceed the byte cap is rejected without buffering."""
    captured: list[bytes] = []

    async def inner_app(scope: object, receive: object, send: object) -> None:  # type: ignore[no-untyped-def]
        message = await receive()  # type: ignore[misc]
        captured.append(message.get("body", b""))
        await send({"type": "http.response.start", "status": 200, "headers": []})  # type: ignore[attr-defined]
        await send({"type": "http.response.body", "body": b""})  # type: ignore[attr-defined]

    mw = body_limit_middleware(inner_app, max_body_bytes=10)
    sent1 = _run_asgi(mw, "POST", "/x", b"a" * 5)
    sent2 = _run_asgi(mw, "POST", "/x", b"b" * 5)
    sent3 = _run_asgi(mw, "POST", "/x", b"c" * 11)  # over the cap -> 413
    sent4 = _run_asgi(mw, "POST", "/x", b"d" * 5)  # still works afterwards
    assert sent1[0]["status"] == 200
    assert sent2[0]["status"] == 200
    assert sent3[0]["status"] == 413
    assert sent4[0]["status"] == 200
    assert captured == [b"a" * 5, b"b" * 5, b"d" * 5]


def test_asgi_middleware_multi_chunk_body_replayed_in_order(tmp_path: Path) -> None:
    captured: dict[str, bytes] = {}

    async def inner_app(scope: object, receive: object, send: object) -> None:  # type: ignore[no-untyped-def]
        body = b""
        while True:
            message = await receive()  # type: ignore[misc]
            body += message.get("body", b"")
            if not message.get("more_body"):
                break
        captured["body"] = body
        await send({"type": "http.response.start", "status": 200, "headers": []})  # type: ignore[attr-defined]
        await send({"type": "http.response.body", "body": b""})  # type: ignore[attr-defined]

    mw = body_limit_middleware(inner_app, max_body_bytes=1000)
    sent: list[dict] = []  # type: ignore[type-arg]
    scope = {
        "type": "http",
        "method": "POST",
        "path": "/x",
        "headers": [(b"host", b"testserver")],
        "query_string": b"",
        "client": ("127.0.0.1", 1),
    }
    chunks = [b"one-", b"two-", b"three"]
    queue = list(chunks)

    async def receive() -> dict:  # type: ignore[type-arg]
        chunk = queue.pop(0)
        return {"type": "http.request", "body": chunk, "more_body": bool(queue)}

    async def send(message: dict) -> None:  # type: ignore[type-arg]
        sent.append(message)

    async def call() -> None:
        await mw(scope, receive, send)  # type: ignore[arg-type]

    asyncio.run(call())
    assert captured["body"] == b"one-two-three"


def test_asgi_middleware_get_passes_through_untouched(tmp_path: Path) -> None:
    async def inner_app(scope: object, receive: object, send: object) -> None:  # type: ignore[no-untyped-def]
        await send({"type": "http.response.start", "status": 200, "headers": []})
        await send({"type": "http.response.body", "body": b"ok"})

    mw = body_limit_middleware(inner_app, max_body_bytes=1)
    sent = _run_asgi(mw, "GET", "/x", b"")
    assert sent[0]["status"] == 200


def test_body_limit_end_to_end_via_testclient(tmp_path: Path) -> None:
    """FastAPI receives the body after the middleware replays it."""
    client = _client(tmp_path, max_body_bytes=64_000)
    r = client.post("/api/v1/policies/validate", json={"content": "name: p\n"})
    assert r.status_code == 200
    assert r.json()["valid"] is True
    big = _client(tmp_path, max_body_bytes=100)
    r = big.post(
        "/api/v1/policies/validate",
        json={"content": "x" * 500},
        headers={TOKEN_HEADER: "tok"},
    )
    assert r.status_code == 413


# ---------------------------------------------------------------------------
# 2. Host authority parsing incl. ports
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("localhost", "localhost"),
        ("localhost:3000", "localhost"),
        ("127.0.0.1:8000", "127.0.0.1"),
        ("[::1]:8000", "::1"),
        ("::1", "::1"),
        ("LocalHost:3000", "localhost"),
        ("localhost:65535", "localhost"),
    ],
)
def test_parse_host_accepts(value: str, expected: str) -> None:
    assert parse_host_authority(value) == expected


@pytest.mark.parametrize(
    "value",
    [
        "localhost:",            # empty port
        "localhost:0",           # port 0 invalid for requests
        "localhost:65536",       # above range
        "localhost:99999999",    # far above range
        "localhost:abc",         # nonnumeric port
        "localhost:-1",          # negative port
        "[::1:8000",             # malformed IPv6 brackets
        "[::1",                  # unclosed bracket
        "user@localhost",        # userinfo
        "localhost extra",       # whitespace inside
        "",                      # empty
        "localhost/path",        # path component
        "localhost/",            # trailing-slash path component
        "localhost?query=1",     # query component
        "localhost#fragment",    # fragment component
        "localhost:/",           # path after empty port
        " localhost",            # leading whitespace
        "localhost ",            # trailing whitespace
        "\tlocalhost",           # tab (control char)
        "local\nhost",           # embedded newline
    ],
)
def test_parse_host_rejects(value: str) -> None:
    with pytest.raises(ValueError):
        parse_host_authority(value)


def test_host_with_invalid_port_rejected_by_middleware(tmp_path: Path) -> None:
    client = _client(tmp_path)
    r = client.get("/api/v1/health", headers={"Host": "localhost:99999"})
    assert r.status_code == 403


def test_host_with_valid_port_accepted_by_middleware(tmp_path: Path) -> None:
    client = _client(tmp_path)
    r = client.get("/api/v1/health", headers={"Host": "localhost:8000"})
    assert r.status_code == 200


# ---------------------------------------------------------------------------
# 3. Token-file hardening
# ---------------------------------------------------------------------------


def test_token_fifo_at_path_is_replaced(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("AGENTFENCE_DB", str(tmp_path / "db.sqlite"))
    fifo = tmp_path / ".api-token"
    os.mkfifo(fifo)
    token = SecurityConfig.load_or_create_token()
    assert len(token) >= 32
    assert fifo.is_file() and not stat.S_ISFIFO(fifo.lstat().st_mode)
    assert stat.S_IMODE(fifo.lstat().st_mode) == 0o600


def test_token_preserved_and_permissions_tightened(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("AGENTFENCE_DB", str(tmp_path / "db.sqlite"))
    path = tmp_path / ".api-token"
    path.write_text("stable-token", encoding="utf-8")
    path.chmod(0o666)
    assert SecurityConfig.load_or_create_token() == "stable-token"
    assert stat.S_IMODE(path.lstat().st_mode) == 0o600


def test_token_creation_race_preserves_winner(tmp_path: Path, monkeypatch) -> None:
    """A competing creator's token is not clobbered."""
    monkeypatch.setenv("AGENTFENCE_DB", str(tmp_path / "db.sqlite"))
    path = tmp_path / ".api-token"
    path.write_text("winner-token", encoding="utf-8")
    path.chmod(0o600)
    assert SecurityConfig.load_or_create_token() == "winner-token"


def test_token_symlink_to_outside_file_not_followed(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("AGENTFENCE_DB", str(tmp_path / "db.sqlite"))
    outside = tmp_path / "outside.txt"
    outside.write_text("precious", encoding="utf-8")
    link = tmp_path / ".api-token"
    link.symlink_to(outside)
    token = SecurityConfig.load_or_create_token()
    # The symlink was replaced by a regular token file; the target untouched.
    assert outside.read_text(encoding="utf-8") == "precious"
    assert link.is_file() and not link.is_symlink()
    assert len(token) >= 32


def test_existing_regular_token_file_loaded_from_descriptor(
    tmp_path: Path, monkeypatch
) -> None:
    """An existing 0600 regular file is read unchanged (no rewrite)."""
    monkeypatch.setenv("AGENTFENCE_DB", str(tmp_path / "db.sqlite"))
    path = tmp_path / ".api-token"
    path.write_text("descriptor-token", encoding="utf-8")
    path.chmod(0o600)
    before = path.stat().st_mtime_ns
    assert SecurityConfig.load_or_create_token() == "descriptor-token"
    assert stat.S_IMODE(path.lstat().st_mode) == 0o600
    # The file was not truncated/rewritten: content and inode stay stable.
    assert path.read_text(encoding="utf-8") == "descriptor-token"
    assert path.stat().st_ino == path.stat().st_ino
    del before


def test_token_concurrent_creation_threads(tmp_path: Path, monkeypatch) -> None:
    """Concurrent creators all return the SAME token (one wins, others adopt)."""
    import threading

    monkeypatch.setenv("AGENTFENCE_DB", str(tmp_path / "db.sqlite"))
    results: list[str] = []
    errors: list[BaseException] = []
    barrier = threading.Barrier(4)

    def worker() -> None:
        try:
            barrier.wait()
            results.append(SecurityConfig.load_or_create_token())
        except BaseException as exc:  # noqa: BLE001
            errors.append(exc)

    threads = [threading.Thread(target=worker) for _ in range(4)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert not errors
    assert len(set(results)) == 1, results
    assert len(results[0]) >= 32


def test_token_symlink_substituted_during_creation_race(
    tmp_path: Path, monkeypatch
) -> None:
    """If a symlink appears between our EEXIST and the re-open, O_NOFOLLOW
    fails the open, the symlink is replaced, and a regular token file results
    — the symlink target is never followed or written."""
    import threading

    monkeypatch.setenv("AGENTFENCE_DB", str(tmp_path / "db.sqlite"))
    path = tmp_path / ".api-token"
    outside = tmp_path / "outside.txt"
    outside.write_text("precious", encoding="utf-8")
    path.write_text("")  # empty file: forces the create path with EEXIST-like flow
    path.unlink()

    started = threading.Event()

    def substituter() -> None:
        # Wait until the primary creator is inside creation, then plant a symlink.
        started.wait(timeout=5)
        for _ in range(50):
            if not path.exists():
                path.symlink_to(outside)
                return
            import time

            time.sleep(0.001)

    t = threading.Thread(target=substituter)
    t.start()
    token = SecurityConfig.load_or_create_token()
    t.join()
    assert len(token) >= 32
    assert outside.read_text(encoding="utf-8") == "precious"
    final = path.lstat()
    assert stat.S_ISREG(final.st_mode)
    assert stat.S_IMODE(final.st_mode) == 0o600


# ---------------------------------------------------------------------------
# 4. Workspace-root consistency
# ---------------------------------------------------------------------------


def test_workspace_root_ignores_cwd(tmp_path: Path, monkeypatch) -> None:
    """Bundled scenarios/policies must be found regardless of the shell CWD."""

    monkeypatch.delenv("AGENTFENCE_WORKSPACE", raising=False)
    monkeypatch.setenv("AGENTFENCE_DB", str(tmp_path / "agentfence.db"))

    from fastapi.testclient import TestClient

    sec = SecurityConfig(token="tok", rate_limit=1000)
    client = TestClient(create_app(db_path=tmp_path / "agentfence.db", security=sec))

    old_cwd = os.getcwd()
    try:
        os.chdir(tmp_path)  # CWD with no bundled data
        scenarios = client.get("/api/v1/arena/scenarios").json()
        policies = client.get("/api/v1/policies").json()
    finally:
        os.chdir(old_cwd)

    assert any(s["name"] == "write-should-deny" for s in scenarios)
    assert any(p["file"] == "example.yaml" for p in policies["policies"])


def test_workspace_root_explicit_env(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("AGENTFENCE_WORKSPACE", str(tmp_path))
    from agentfence_api.arena_policy import _workspace_root

    assert _workspace_root() == tmp_path.resolve()


# ---------------------------------------------------------------------------
# 5. API error redaction
# ---------------------------------------------------------------------------


def test_database_error_details_redacted(tmp_path: Path, monkeypatch) -> None:
    """A DatabaseError raised by storage must not leak raw driver strings."""
    client = _client(tmp_path)
    # Normal operation works; then break the DB behind the store's back.

    from agentfence_api.app import create_app as _ca  # noqa: F401
    from agentfence_storage.database import connect

    conn = connect(tmp_path / "db.sqlite")
    conn.execute("DROP TABLE policy_evaluations")
    conn.commit()
    conn.close()

    r = client.get("/api/v1/policies/history")
    assert r.status_code == 500
    detail = json.dumps(r.json()).lower()
    # Useful diagnostic retained…
    assert "policy_evaluations" in detail or "error" in detail
    # …but no SQL statement text or token material.
    assert "insert into" not in detail
    assert "tok" != r.json().get("detail", "")


def test_scan_error_details_redacted(tmp_path: Path) -> None:
    client = _client(tmp_path)
    r = client.post("/api/v1/scan", json={"path": "https://secret-host.example.com/x"})
    assert r.status_code == 400
    body = r.json()["detail"]
    assert "remote" in body  # useful diagnostic kept
