"""Local API security: session token, Origin/Host validation, rate limiting.

The API is unauthenticated by design (local-first, no credentials), but an
untrusted website open in the user's browser must not be able to trigger
API operations. DNS rebinding defeats both CORS and the Same-Origin Policy,
so we enforce:

1. A **local session token** required on every state-changing request.
   The token is random, generated at API start, and stored in a 0600 file
   under .agentfence/ (symlinks rejected, permissions enforced on load).
2. **Origin validation**: any request carrying an Origin header must come
   from the configured local dashboard origins. A mutating request with a
   mismatched Origin is rejected; a *missing* Origin on a mutation is
   allowed only for non-browser clients, which must present the session
   token (curl, tests, scripts). Browsers always send Origin on
   cross-origin requests, so a missing Origin + valid token is not a
   browser CSRF vector.
3. **Host validation** on every request: the Host header is parsed as an
   authority (hostname or IP, with optional port / IPv6 brackets) and must
   resolve to a normalized hostname in an explicit localhost allowlist.
   Malformed, missing, wildcard (0.0.0.0), and untrusted values are
   rejected. This is the DNS-rebinding defense.
4. **Rate limiting** on mutating endpoints to bound resource exhaustion.
5. **Request-body size limits** enforced while receiving the body (see
   agentfence_api.body_limit), not just via Content-Length.

Non-browser clients (CLI, curl, tests) simply include the token header.
"""

from __future__ import annotations

import os
import secrets
import threading
import time
from collections import defaultdict, deque
from pathlib import Path
from urllib.parse import urlsplit

TOKEN_HEADER = "X-AgentFence-Session"

# Normalized hostnames accepted in the Host header. Wildcard bind addresses
# (0.0.0.0) are deliberately NOT accepted: they are bind addresses, not
# request authorities.
DEFAULT_LOCAL_HOSTS = {"localhost", "127.0.0.1", "::1", "[::1]", "testserver"}


def parse_host_authority(value: str) -> str:
    """Parse a Host header authority and return the normalized hostname.

    Handles ``hostname``, ``hostname:port``, IPv6 literals (``[::1]:8000``),
    and bare ``::1``. Raises ValueError for malformed or empty values.

    The *entire* authority is validated: leading/trailing whitespace is
    rejected (not silently stripped), as are embedded whitespace, control
    characters, userinfo, path/query/fragment components, and malformed,
    empty, zero, or out-of-range ports.
    """
    # No stripping: leading/trailing whitespace is malformed, not incidental.
    if not value:
        raise ValueError("empty Host header")
    # Reject userinfo and ALL whitespace/control characters, anywhere.
    if any(c.isspace() or ord(c) < 32 for c in value):
        raise ValueError("malformed Host header: whitespace or control characters")
    if "@" in value:
        raise ValueError("malformed Host header: userinfo is not allowed")
    # Wrap bare IPv6 in brackets so urlsplit can parse the authority.
    if ":" in value and not value.startswith("["):  # noqa: PTH121
        if value.count(":") > 1:
            value = f"[{value}]"
    try:
        split = urlsplit(f"//{value}")
    except ValueError as exc:
        raise ValueError("malformed Host header") from exc
    hostname = (split.hostname or "").lower()
    if not hostname:
        raise ValueError("malformed Host header")
    # The Host header is an authority only: reject any path/query/fragment.
    if split.path or split.query or split.fragment:
        raise ValueError("malformed Host header: path/query/fragment not allowed")
    # Validate the port explicitly: must be numeric, non-empty, and within
    # 1-65535. urlsplit returns port=None both for "no port" and for empty or
    # malformed ports, so validate the raw port segment directly. Only
    # non-bracketed netlocs carry a plain ``host:port`` tail; bracketed IPv6
    # literals are validated by ``split.port`` below.
    if not split.netloc.startswith("["):
        port_segment = split.netloc.rsplit(":", 1)[1] if ":" in split.netloc else None
        if port_segment is not None:
            if not port_segment.isdigit() or not (1 <= int(port_segment) <= 65535):
                raise ValueError("invalid port in Host header")
    port = split.port  # raises ValueError for malformed ports on some platforms
    if port is not None and not (0 < port <= 65535):
        raise ValueError("invalid port in Host header")
    # After parsing, only hostname-safe characters may remain (colons survive
    # only for bracketed IPv6 literals; the port was consumed by urlsplit).
    charset = set(hostname)
    allowed = set("abcdefghijklmnopqrstuvwxyz0123456789.-:")
    if charset - allowed:
        raise ValueError("malformed Host header")
    return hostname


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
        """Load or create the local session token safely.

        All read/tighten operations are **descriptor-based**: the file is
        opened with ``O_NOFOLLOW`` (symlinks are never followed at open
        time), verified as a regular file via ``os.fstat`` on that
        descriptor, tightened with ``os.fchmod`` on the same descriptor, and
        read from it — eliminating the open/read time-of-check/time-of-use
        window on the path.

        Unsafe filesystem types (symlink, directory, FIFO, device) found at
        the exact token path are replaced with a fresh regular file. Only
        the token path is ever touched; a symlink's *target* is never
        modified.

        Creation uses ``O_CREAT|O_EXCL`` with mode 0600, so there is no
        window where the file is world-readable. The creation-race fallback
        re-opens with ``O_NOFOLLOW`` so a concurrently substituted symlink
        cannot be followed.

        Platform notes (stated honestly):
        - ``O_NOFOLLOW`` is available on Linux, macOS, and other POSIX
          systems; this implementation is not designed for Windows.
        - The parent directory is opened once and all name-based operations
          (open / unlink / lstat) are performed relative to that descriptor
          (``openat`` semantics). On platforms or Python builds where a
          specific call does not support ``dir_fd``, that single call falls
          back to the equivalent path-based operation.
        - Replacing an unsafe entry that is a *directory* uses
          ``shutil.rmtree`` on the exact token path only.
        - The token value is preserved across normal restarts.
        """
        path = SecurityConfig.token_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        import stat as stat_module

        open_flags = os.O_NOFOLLOW if hasattr(os, "O_NOFOLLOW") else 0

        # Directory-descriptor-relative (openat-style) operations: open the
        # parent directory once and perform every name-based operation
        # (open / unlink) relative to that descriptor, so a concurrent swap of
        # a *parent* path component cannot redirect us to another directory.
        # Not every platform/name supports dir_fd for these calls; where it is
        # unsupported we fall back to plain path operations (documented
        # limitation, not claimed otherwise).
        dir_fd: int | None
        try:
            dir_fd = os.open(path.parent, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
        except (OSError, TypeError):
            dir_fd = None

        def _open(nm: str, flags: int, mode: int = 0) -> int:
            if dir_fd is not None:
                try:
                    return os.open(nm, flags, mode, dir_fd=dir_fd)
                except (TypeError, OSError):
                    pass  # dir_fd unsupported here; fall through to path open
            return os.open(os.fspath(path.parent / nm), flags, mode)

        def _unlink(nm: str) -> None:
            if dir_fd is not None:
                try:
                    os.unlink(nm, dir_fd=dir_fd)
                    return
                except (TypeError, OSError):
                    pass
            Path(path).with_name(nm).unlink(missing_ok=True)

        name = path.name

        # --- descriptor-based open of an existing entry -----------------
        unsafe_link = False
        fd = None
        try:
            # O_NOFOLLOW: opening a symlink raises ELOOP instead of following it.
            fd = _open(name, os.O_RDWR | open_flags)
        except FileNotFoundError:
            pass
        except IsADirectoryError:
            # Directory at the token path: unsafe type, replace it.
            unsafe_link = True
        except OSError as exc:
            if exc.errno == 40:  # ELOOP — path is a symlink: unsafe type
                unsafe_link = True
            elif exc.errno == 21:  # EISDIR (some platforms)
                unsafe_link = True
            # Other open errors (permissions, etc.) fall through to creation
            # attempt, which will raise a clear error if truly blocked.

        if fd is not None:
            st = os.fstat(fd)
            if not stat_module.S_ISREG(st.st_mode):
                # FIFO/device/other non-regular type: close and replace.
                os.close(fd)
                fd = None
                unsafe_link = True
            else:
                # Legit regular file: tighten permissions on the descriptor
                # and read from it (no path re-open → no TOCTOU here).
                if stat_module.S_IMODE(st.st_mode) != 0o600:
                    os.fchmod(fd, 0o600)
                with os.fdopen(fd, "r", encoding="utf-8") as fh:
                    token = fh.read().strip()
                if token:
                    return token
                # Empty file: fall through to creation below.

        # --- replace unsafe entries at the exact token path ---------------
        if unsafe_link:
            try:
                st = os.lstat(name, dir_fd=dir_fd) if dir_fd is not None else path.lstat()
            except (FileNotFoundError, TypeError, OSError):
                st = None
            if st is not None:
                if stat_module.S_ISDIR(st.st_mode):
                    import shutil

                    shutil.rmtree(path)
                else:
                    _unlink(name)

        # --- create the token file (race-safe, 0600 from first byte) ------
        token = secrets.token_urlsafe(32)
        while True:
            try:
                fd = _open(name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | open_flags, 0o600)
                break
            except FileExistsError:
                # Lost a creation race: re-open with O_NOFOLLOW (never follow
                # a concurrently substituted symlink), verify regular + 0600.
                try:
                    fd = _open(name, os.O_RDWR | open_flags)
                except OSError:
                    # ELOOP etc.: the entry was substituted with a symlink
                    # between our check and open — replace it and retry.
                    _unlink(name)
                    continue
                st = os.fstat(fd)
                if not stat_module.S_ISREG(st.st_mode):
                    os.close(fd)
                    _unlink(name)
                    continue
                os.fchmod(fd, 0o600)
                with os.fdopen(fd, "r", encoding="utf-8") as fh:
                    existing = fh.read().strip()
                if existing:
                    return existing
                fd = _open(name, os.O_WRONLY | os.O_TRUNC | open_flags, 0o600)
                break
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(token)
        if dir_fd is not None:
            os.close(dir_fd)
        return token

    # -- request checks ------------------------------------------------------

    def check_request(self, method: str, headers: dict[str, str], client_host: str) -> str | None:
        """Return a rejection reason, or None if the request may proceed."""
        # Host header: DNS-rebinding defense. Applies to every request.
        # Malformed or missing Host values are rejected outright.
        try:
            host = parse_host_authority(headers.get("host") or "")
        except ValueError as exc:
            return str(exc)
        if host not in self.local_hosts:
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
