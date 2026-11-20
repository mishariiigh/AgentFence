"""Request-body size enforcement while receiving the request.

Content-Length alone is insufficient: chunked/streamed requests may omit it.
This is a *pure ASGI* middleware: it intercepts the ``receive`` channel,
accumulates the body in bounded chunks, rejects any request whose accumulated
size exceeds the configured maximum (HTTP 413), and then replays the exact
original ASGI messages to the application. Private Starlette request
attributes and ``BaseHTTPMiddleware`` are avoided.

Memory bounds (per request — all state is created inside ``middleware``):
- Total buffered **bytes** never exceed ``max_body_bytes``.
- Total buffered **messages** never exceed ``max_body_messages``; this also
  bounds unlimited zero-byte chunks, which do not count toward the byte cap.
- All buffering state is per-request; nothing is retained between requests.

Replay guarantees:
- Buffered ``http.request`` messages are re-emitted in order with their
  original ``more_body`` flags.
- An empty body is replayed as a single final ``http.request`` message
  (``body=b""``, ``more_body=False``) so the endpoint never blocks waiting
  for a disconnect.
- Disconnect messages (``http.disconnect``) received during the drain are
  buffered and replayed to the application exactly once, in sequence, so a
  disconnect is never swallowed even though a real ASGI server would not
  re-deliver a consumed event.
"""

from __future__ import annotations

from collections.abc import Callable, MutableMapping
from typing import Any

Receive = Callable[[], Any]
Send = Callable[[MutableMapping[str, Any]], Any]

# Upper bound on buffered ASGI messages per request. A well-formed server
# sends one final http.request; pathological peers splitting a tiny body into
# thousands of zero-byte chunks are cut off here instead of exhausting memory.
MAX_BODY_MESSAGES = 10_000


class _BodyTooLarge(Exception):
    """Internal: raised by the limited receive when the body exceeds the cap."""


def body_limit_middleware(
    app: Any, max_body_bytes: int, max_body_messages: int = MAX_BODY_MESSAGES
) -> Callable[[MutableMapping[str, Any], Receive, Send], Any]:
    """Pure ASGI middleware enforcing the request-body size cap."""

    async def middleware(
        scope: MutableMapping[str, Any], receive: Receive, send: Send
    ) -> None:
        # Per-request state only: nothing survives between requests.
        buffered_messages: list[dict[str, Any]] = []
        buffered_bytes = 0
        message_count = 0
        done = False

        if scope["type"] != "http" or scope["method"] in {"GET", "HEAD", "OPTIONS"}:
            await app(scope, receive, send)
            return

        # Cheap pre-check when Content-Length is present.
        for name, value in scope.get("headers", []):
            if name == b"content-length":
                if value.isdigit() and int(value) > max_body_bytes:
                    await _send_413(send)
                    return
                break

        async def limited_receive() -> dict[str, Any]:
            nonlocal buffered_bytes, message_count, done
            message = await receive()
            if message["type"] != "http.request":
                done = True
                # Buffer non-request lifecycle messages (e.g. http.disconnect)
                # so replay can hand the *same* event to the application; a
                # real ASGI server would not re-deliver a consumed disconnect.
                buffered_messages.append(message)
                return message
            chunk = message.get("body", b"")
            buffered_bytes += len(chunk)
            message_count += 1
            if buffered_bytes > max_body_bytes or message_count > max_body_messages:
                done = True
                raise _BodyTooLarge()
            buffered_messages.append(message)
            if not message.get("more_body"):
                done = True
            return message

        async def drain() -> None:
            nonlocal done
            while not done:
                await limited_receive()

        # Pre-drain the body under the caps. Oversized requests are rejected
        # here and never reach the inner application.
        try:
            await drain()
        except _BodyTooLarge:
            await _send_413(send)
            return

        index = 0

        async def replay() -> dict[str, Any]:
            """Replay buffered messages in order, then defer to the real receive."""
            nonlocal index
            if index < len(buffered_messages):
                message = buffered_messages[index]
                index += 1
                return message
            return await receive()

        await app(scope, replay, send)

    return middleware


async def _send_413(send: Send) -> None:
    await send(
        {
            "type": "http.response.start",
            "status": 413,
            "headers": [(b"content-type", b"application/json")],
        }
    )
    await send(
        {
            "type": "http.response.body",
            "body": b'{"detail":"request body too large"}',
        }
    )
