import hmac
import json
import logging
from typing import Any

from starlette.exceptions import HTTPException
from starlette.types import ASGIApp, Receive, Scope, Send

from config.settings import settings

logger = logging.getLogger(__name__)

_SECURITY_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "no-referrer",
    "Cross-Origin-Opener-Policy": "same-origin",
    "Permissions-Policy": "camera=(self), microphone=(self), geolocation=()",
    "Content-Security-Policy": (
        "default-src 'self'; "
        "script-src 'self' 'unsafe-inline' 'wasm-unsafe-eval' https://cdn.jsdelivr.net; "
        "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
        "font-src 'self' https://fonts.gstatic.com data:; "
        "img-src 'self' data: blob:; "
        "media-src 'self' blob:; "
        "connect-src 'self' https://cdn.jsdelivr.net; "
        "object-src 'none'; "
        "frame-ancestors 'none'; "
        "base-uri 'self'"
    ),
}

_MUTATING_METHODS = {"POST", "PUT", "PATCH", "DELETE"}
_BODY_METHODS = {"POST", "PUT", "PATCH"}


def _headers_dict(scope: Scope) -> dict[str, str]:
    return {
        k.decode("latin-1").lower(): v.decode("latin-1")
        for k, v in scope.get("headers", [])
    }


class SecurityMiddleware:
    """Single choke point for API auth, origin validation, request limits,
    and security response headers. Never blocks the event loop.

    Request size is enforced at two layers:
      1. Declared Content-Length is rejected up front (no body touched).
      2. The actual body stream is counted as it flows to the application,
         so chunked transfer encoding and streaming uploads cannot bypass
         the limit. The body is never buffered here — chunks are counted in
         flight — and the request is rejected with 413 at the moment the
         limit is exceeded, before the remaining bytes are consumed.
    """

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        headers = _headers_dict(scope)
        rejection = self._reject(scope, headers)
        if rejection is not None:
            await self._send_json(send, rejection, headers.get("origin"))
            return

        if self._has_body(scope):
            await self._dispatch_with_body_limit(scope, receive, send)
        else:
            await self.app(scope, receive, self._send_with_headers(send))

    def _has_body(self, scope: Scope) -> bool:
        path: str = scope.get("path", "")
        method: str = scope.get("method", "GET")
        return method in _BODY_METHODS and path.startswith("/api/")

    async def _dispatch_with_body_limit(
        self,
        scope: Scope,
        receive: Receive,
        send: Send,
    ) -> None:
        limit = settings.max_request_bytes
        received = 0

        async def receive_limited() -> dict[str, Any]:
            nonlocal received
            message = await receive()
            if message["type"] == "http.request":
                chunk = message.get("body", b"")
                if chunk:
                    received += len(chunk)
                    if received > limit:
                        logger.warning(
                            "Rejected %s %s: streamed body exceeded %s bytes "
                            "(received %s, Content-Length not trusted)",
                            scope.get("method"), scope.get("path"), limit, received,
                        )
                        raise HTTPException(
                            status_code=413,
                            detail="Request body too large",
                        )
            return message

        await self.app(scope, receive_limited, self._send_with_headers(send))

    def _reject(self, scope: Scope, headers: dict[str, str]) -> tuple[int, str] | None:
        path: str = scope.get("path", "")
        method: str = scope.get("method", "GET")

        if not path.startswith("/api/"):
            return None

        if method in _BODY_METHODS:
            content_length = headers.get("content-length")
            if (
                content_length
                and content_length.isdigit()
                and int(content_length) > settings.max_request_bytes
            ):
                logger.warning(
                    "Rejected %s %s: body %s bytes exceeds limit %s",
                    method, path, content_length, settings.max_request_bytes,
                )
                return 413, "Request body too large"

        if method != "OPTIONS" and settings.api_token:
            auth = headers.get("authorization", "")
            token = (
                auth[7:].strip()
                if auth.lower().startswith("bearer ")
                else headers.get("x-falso-token", "")
            )
            if not hmac.compare_digest(token, settings.api_token):
                logger.warning("Rejected %s %s: missing or invalid API token", method, path)
                return 401, "Unauthorized"

        if method in _MUTATING_METHODS:
            origin = headers.get("origin")
            if origin:
                host = headers.get("host", "")
                same_origin = origin in (f"http://{host}", f"https://{host}")
                if not same_origin and origin not in settings.allowed_origins:
                    logger.warning(
                        "Rejected %s %s: origin %s not allowed", method, path, origin
                    )
                    return 403, "Origin not allowed"

        return None

    async def _send_json(
        self, send: Send, rejection: tuple[int, str], origin: str | None
    ) -> None:
        status, detail = rejection
        body = json.dumps({"detail": detail}).encode("utf-8")
        headers: list[tuple[str, str]] = list(_SECURITY_HEADERS.items()) + [
            ("content-type", "application/json"),
            ("content-length", str(len(body))),
        ]
        if origin:
            headers.append(("access-control-allow-origin", origin))
        encoded = [
            (k.encode("latin-1"), v.encode("latin-1")) for k, v in headers
        ]
        await send({"type": "http.response.start", "status": status, "headers": encoded})
        await send({"type": "http.response.body", "body": body})

    def _send_with_headers(self, send: Send) -> Any:
        async def wrapper(message: dict[str, Any]) -> None:
            if message["type"] == "http.response.start":
                headers = list(message.get("headers", []))
                existing = {k.lower() for k, _ in headers}
                for name, value in _SECURITY_HEADERS.items():
                    if name.lower() not in existing:
                        headers.append(
                            (name.encode("latin-1"), value.encode("latin-1"))
                        )
                message = {**message, "headers": headers}
            await send(message)

        return wrapper
