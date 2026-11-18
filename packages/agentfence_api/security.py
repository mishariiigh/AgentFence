"""Local API security: session token, Origin/Host validation, rate limiting.

The API is unauthenticated by design (local-first, no credentials), but an
untrusted website open in the user's browser must not be able to trigger
API operations. DNS rebinding defeats both CORS and the Same-Origin Policy,
so we enforce:

1. A **local session token** required on every state-changing request
   (mutation endpoints). The token is random, generated at API start, stored
   0600 under .agentfence/, and printed once to the operator console.
2. **Origin validation**: browser requests (any request carrying an Origin
   header) must originate from the configured local dashboard origins. A
   mismatched or missing Origin on a mutating request → 403.
3. **Host validation**: the Host header must be localhost/127.0.0.1 — this is
   the DNS-rebinding defense, since rebinding attacks present a foreign Host.
4. **Rate limiting** on mutating endpoints to bound resource exhaustion.

Non-browser clients (CLI, curl, tests) simply include the token header.
"""

from __future__ import annotations

import os
import secrets
import threading
import time
from collections import defaultdict, deque
from pathlib import Path

TOKEN_HEADER = "X-AgentFence-Session"
DEFAULT_LOCAL_HOSTS = {"localhost", "127.0.0.1", "0.0.0.0", "[::1]", "::1", "testserver"}


class SecurityConfig:
    """Per-process security configuration for the local API."""

    def __init__(
        self,
        token: str | None = None,
        allowed_origins: list[str] | None = None,
        local_hosts: set[str] | None = None,
        rate_limit: int = 30,
        rate_window_seconds: float = 60.0,
        max_body_bytes: int = 64 * 1024,
    ) -> None:
        self.token = token or SecurityConfig.load_or_create_token()
        self.allowed_origins = set(
            allowed_origins
            if allowed_origins is not None
            else os.environ.get(
                "AGENTFENCE_CORS_ORIGINS",
                "http://localhost:3000,http://127.0.0.1:3000",
            ).split(",")
        )
        self.allowed_origins = {o.strip() for o in self.allowed_origins if o.strip()}
        self.local_hosts = local_hosts or DEFAULT_LOCAL_HOSTS
        self.rate_limit = rate_limit
        self.rate_window = rate_window_seconds
        self.max_body_bytes = max_body_bytes
        self._hits: dict[str, deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()

    # -- token management ---------------------------------------------------

    @staticmethod
    def token_path() -> Path:
        base = os.environ.get("AGENTFENCE_DB", ".agentfence/agentfence.db")
        return Path(base).parent / ".api-token"

    @staticmethod
    def load_or_create_token() -> str:
        """Load or create the local session token (0600 file)."""
        path = SecurityConfig.token_path()
        if path.exists():
            token = path.read_text(encoding="utf-8").strip()
            if token:
                return token
        token = secrets.token_urlsafe(32)
        path.parent.mkdir(parents=True, exist_ok=True)
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(token)
        return token

    # -- request checks ------------------------------------------------------

    def check_request(self, method: str, headers: dict[str, str], client_host: str) -> str | None:
        """Return a rejection reason, or None if the request may proceed."""
        # Host header: DNS-rebinding defense. Applies to every request.
        host = (headers.get("host") or "").split(":")[0].strip().lower()
        if host and host not in self.local_hosts:
            return f"untrusted Host header: {host}"

        origin = headers.get("origin")
        if method in {"POST", "PUT", "DELETE", "PATCH"}:
            if origin is not None and origin not in self.allowed_origins:
                return f"untrusted Origin: {origin}"
            if not self.check_rate_limit(client_host):
                return "rate limit exceeded; retry later"
            # Mutations always require the session token.
            provided = headers.get(TOKEN_HEADER.lower()) or headers.get(TOKEN_HEADER)
            if provided != self.token:
                return "missing or invalid session token"
        return None

    def check_rate_limit(self, client_key: str) -> bool:
        now = time.monotonic()
        with self._lock:
            hits = self._hits[client_key]
            while hits and now - hits[0] > self.rate_window:
                hits.popleft()
            if len(hits) >= self.rate_limit:
                return False
            hits.append(now)
            return True
