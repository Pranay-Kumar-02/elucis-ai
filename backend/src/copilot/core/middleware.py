"""Pure ASGI middleware: request IDs, access log, body-size limits, security headers.

Written as raw ASGI (not ``BaseHTTPMiddleware``) so streaming responses and SSE keep working
and context variables propagate correctly into route handlers.
"""

from __future__ import annotations

import json
import logging
import os
import re
import time
from collections.abc import Callable, Iterable
from typing import Any

from starlette.types import ASGIApp, Message, Receive, Scope, Send

from copilot.core.errors import error_body
from copilot.core.logging import request_id_var

logger = logging.getLogger("copilot.access")
error_logger = logging.getLogger("copilot.errors")

REQUEST_ID_HEADER = "x-request-id"
_VALID_INCOMING_ID = re.compile(r"^[A-Za-z0-9._-]{8,64}$")
_CROCKFORD = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"


def new_request_id() -> str:
    """Return a ULID (26 chars, time-ordered, 80 random bits), as shown in D09 section 2."""
    value = (int(time.time() * 1000) << 80) | int.from_bytes(os.urandom(10), "big")
    chars = []
    for _ in range(26):
        chars.append(_CROCKFORD[value & 0x1F])
        value >>= 5
    return "".join(reversed(chars))


class _BodyTooLargeError(Exception):
    pass


async def _send_json(
    send: Send, status: int, body: dict[str, Any], headers: list[tuple[bytes, bytes]]
) -> None:
    raw = json.dumps(body).encode()
    await send(
        {
            "type": "http.response.start",
            "status": status,
            "headers": [
                (b"content-type", b"application/json"),
                (b"content-length", str(len(raw)).encode()),
                *headers,
            ],
        }
    )
    await send({"type": "http.response.body", "body": raw})


class _Exchange:
    """State of one HTTP request/response passing through ``RequestContextMiddleware``."""

    def __init__(
        self, send: Send, receive: Receive, limit: int, upload: bool, request_id: str
    ) -> None:
        self._send = send
        self._receive = receive
        self.limit = limit
        self.upload = upload
        self.id_header = (REQUEST_ID_HEADER.encode(), request_id.encode())
        self.status = 500
        self.started = False
        self.received = 0
        self.exceeded = False

    async def receive(self) -> Message:
        message = await self._receive()
        if message["type"] == "http.request":
            self.received += len(message.get("body", b""))
            if self.received > self.limit:
                self.exceeded = True
                raise _BodyTooLargeError
        return message

    async def send(self, message: Message) -> None:
        # A framework layer may turn _BodyTooLargeError into its own 400 response (FastAPI
        # does this while parsing forms); replace that with a proper 413.
        if self.exceeded:
            if message["type"] == "http.response.start" and not self.started:
                await self.too_large()
            return
        if message["type"] == "http.response.start":
            self.status = message["status"]
            self.started = True
            message = {**message, "headers": [*message.get("headers", []), self.id_header]}
        await self._send(message)

    async def too_large(self) -> None:
        self.status, self.started = 413, True
        body = error_body(
            "file_too_large" if self.upload else "bad_request",
            "The upload is larger than 20 MB."
            if self.upload
            else "The request body is larger than 1 MB.",
        )
        await _send_json(self._send, 413, body, [self.id_header])

    async def internal_error(self) -> None:
        if not self.started:
            self.status, self.started = 500, True
            body = error_body("internal_error", "An unexpected error occurred.")
            await _send_json(self._send, 500, body, [self.id_header])


class RequestContextMiddleware:
    """Assigns a request ID, enforces body limits, writes one access-log line per request,
    and converts unexpected exceptions into the standard ``internal_error`` envelope."""

    def __init__(
        self,
        app: ASGIApp,
        *,
        max_body_bytes: int,
        upload_max_bytes: int,
        is_upload_path: Callable[[str], bool],
    ) -> None:
        self.app = app
        self.max_body_bytes = max_body_bytes
        self.upload_max_bytes = upload_max_bytes
        self.is_upload_path = is_upload_path

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        headers = dict(scope.get("headers") or [])
        incoming = headers.get(REQUEST_ID_HEADER.encode(), b"").decode("latin-1")
        request_id = incoming if _VALID_INCOMING_ID.match(incoming) else new_request_id()
        path: str = scope.get("path", "")
        upload = self.is_upload_path(path)
        limit = self.upload_max_bytes if upload else self.max_body_bytes
        exchange = _Exchange(send, receive, limit, upload, request_id)

        token = request_id_var.set(request_id)
        started = time.perf_counter()
        try:
            declared = headers.get(b"content-length", b"")
            if declared.isdigit() and int(declared) > limit:
                await exchange.too_large()
                return
            try:
                await self.app(scope, exchange.receive, exchange.send)
            except _BodyTooLargeError:
                if not exchange.started:
                    await exchange.too_large()
            except Exception:
                error_logger.exception("unhandled exception", extra={"path": path})
                await exchange.internal_error()
        finally:
            logger.info(
                "%s %s %s",
                scope.get("method", "-"),
                path,  # path only: query strings may carry user input
                exchange.status,
                extra={"duration_ms": round((time.perf_counter() - started) * 1000, 1)},
            )
            request_id_var.reset(token)


class SecurityHeadersMiddleware:
    """Adds conservative security headers to every HTTP response."""

    _API_CSP = b"default-src 'none'; frame-ancestors 'none'; base-uri 'none'"

    def __init__(self, app: ASGIApp, *, csp_exempt_prefixes: Iterable[str] = ()) -> None:
        self.app = app
        self.csp_exempt_prefixes = tuple(csp_exempt_prefixes)

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        path: str = scope.get("path", "")
        with_csp = not path.startswith(self.csp_exempt_prefixes)

        async def send_wrapper(message: Message) -> None:
            if message["type"] == "http.response.start":
                headers = list(message.get("headers", []))
                present = {k.lower() for k, _ in headers}
                extra = [
                    (b"x-content-type-options", b"nosniff"),
                    (b"x-frame-options", b"DENY"),
                    (b"referrer-policy", b"no-referrer"),
                    (b"cross-origin-opener-policy", b"same-origin"),
                    (b"cache-control", b"no-store"),
                ]
                if with_csp:
                    extra.append((b"content-security-policy", self._API_CSP))
                headers.extend((k, v) for k, v in extra if k not in present)
                message = {**message, "headers": headers}
            await send(message)

        await self.app(scope, receive, send_wrapper)
