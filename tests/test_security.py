import hmac
import json
import uuid

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from starlette.exceptions import HTTPException as StarletteHTTPException

import app.main as main_module
import app.middleware.security as security_module
import app.routes.conversations as conv_module
from app.routes.conversations import _validate_conv_id
from config.settings import settings

CHAT_TOOL_PROMPT = "what is the time now"


class TestStaticFileServing:
    """The catch-all static route must never escape the frontend directory."""

    def test_traversal_attempts_serve_index(self) -> None:
        with TestClient(main_module.app) as client:
            for path in (
                "/..%2F..%2F.env",
                "/%2e%2e/%2e%2e/.env",
                "/..%2f..%2f.env.example",
                "/..%5C..%5Cconfig%5Csettings.py",
            ):
                r = client.get(path)
                assert r.status_code == 200
                assert "text/html" in r.headers["content-type"]
                assert "FALSO" in r.text

    def test_security_headers_present(self) -> None:
        with TestClient(main_module.app) as client:
            r = client.get("/")
            assert r.headers.get("x-content-type-options") == "nosniff"
            assert r.headers.get("x-frame-options") == "DENY"
            assert "content-security-policy" in r.headers
            assert "default-src 'self'" in r.headers["content-security-policy"]


class TestConversationIdValidation:
    """conv_id must be a safe charset — never a filesystem path fragment.

    Note: httpx decodes %2F into "/" before dispatch, so slash-based traversal
    gets absorbed by the route regex (single-segment param) and falls through to
    the static catch-all. The dangerous vector is the single-segment backslash
    form ("..\\..\\etc"), which must be rejected by charset validation.
    """

    def test_validator_rejects_traversal_ids(self) -> None:
        for bad in (
            "../../etc",
            "..\\..\\etc",
            "../evil",
            "a/b",
            "..",
            ".",
            "a b",
            "",
            "id.with.dot",
            "a" * 65,
        ):
            with pytest.raises(HTTPException):
                _validate_conv_id(bad)

    def test_validator_accepts_safe_ids(self) -> None:
        conv_id = str(uuid.uuid4())
        assert _validate_conv_id(conv_id) == conv_id
        assert _validate_conv_id("test123") == "test123"
        assert _validate_conv_id("chat-2026_07") == "chat-2026_07"

    def test_api_rejects_backslash_traversal(self, monkeypatch, tmp_path) -> None:
        monkeypatch.setattr(conv_module, "CHATS_DIR", tmp_path)
        with TestClient(main_module.app) as client:
            for bad in ("..%5C..%5Cetc", "..\\..\\etc"):
                assert client.get(f"/api/v1/conversations/{bad}").status_code == 400
                assert client.delete(f"/api/v1/conversations/{bad}").status_code == 400

    def test_api_rejects_invalid_ids(self, monkeypatch, tmp_path) -> None:
        monkeypatch.setattr(conv_module, "CHATS_DIR", tmp_path)
        with TestClient(main_module.app) as client:
            for bad in ("a$b!", "id.with.dot"):
                assert client.get(f"/api/v1/conversations/{bad}").status_code == 400
                assert client.delete(f"/api/v1/conversations/{bad}").status_code == 400

    def test_api_slash_traversal_never_leaks(self, monkeypatch, tmp_path) -> None:
        monkeypatch.setattr(conv_module, "CHATS_DIR", tmp_path)
        with TestClient(main_module.app) as client:
            r = client.get("/api/v1/conversations/..%2F..%2Fetc")
            # Unknown /api/* paths are rejected with JSON 404 — never the SPA,
            # never file contents.
            assert r.status_code == 404
            assert "text/html" not in r.headers["content-type"]

    def test_api_rejects_traversal_in_body(self, monkeypatch, tmp_path) -> None:
        monkeypatch.setattr(conv_module, "CHATS_DIR", tmp_path)
        with TestClient(main_module.app) as client:
            r = client.post(
                "/api/v1/conversations/",
                json={"id": "../../x", "title": "t", "messages": []},
            )
            assert r.status_code == 400

    def test_crud_roundtrip(self, monkeypatch, tmp_path) -> None:
        monkeypatch.setattr(conv_module, "CHATS_DIR", tmp_path)
        conv_id = str(uuid.uuid4())
        with TestClient(main_module.app) as client:
            r = client.post(
                "/api/v1/conversations/",
                json={
                    "id": conv_id,
                    "title": "hi",
                    "messages": [
                        {"role": "user", "text": "hello", "time": "2026-01-01"}
                    ],
                    "createdAt": "",
                    "updatedAt": "",
                },
            )
            assert r.status_code == 200

            r = client.get(f"/api/v1/conversations/{conv_id}")
            assert r.status_code == 200
            assert r.json()["title"] == "hi"
            assert r.json()["messages"][0]["text"] == "hello"

            listing = client.get("/api/v1/conversations/").json()
            assert any(x["id"] == conv_id for x in listing)

            assert client.delete(f"/api/v1/conversations/{conv_id}").status_code == 200
            assert client.get(f"/api/v1/conversations/{conv_id}").status_code == 404

    def test_missing_conversation_returns_404(self, monkeypatch, tmp_path) -> None:
        monkeypatch.setattr(conv_module, "CHATS_DIR", tmp_path)
        with TestClient(main_module.app) as client:
            r = client.get(f"/api/v1/conversations/{uuid.uuid4()}")
            assert r.status_code == 404


class TestApiTokenGuard:
    def test_token_required_when_configured(self, monkeypatch) -> None:
        monkeypatch.setattr(settings, "api_token", "sekret")
        with TestClient(main_module.app) as client:
            assert client.get("/api/v1/tools/time").status_code == 401
            assert (
                client.get(
                    "/api/v1/tools/time", headers={"X-Falso-Token": "sekret"}
                ).status_code
                == 200
            )
            assert (
                client.get(
                    "/api/v1/tools/time",
                    headers={"Authorization": "Bearer sekret"},
                ).status_code
                == 200
            )
            assert client.get("/api/v1/tools/time", headers={"X-Falso-Token": "wrong"}).status_code == 401
            assert client.get("/health").status_code == 200

    def test_no_token_required_when_unconfigured(self, monkeypatch) -> None:
        monkeypatch.setattr(settings, "api_token", "")
        with TestClient(main_module.app) as client:
            assert client.get("/api/v1/tools/time").status_code == 200

    def test_token_compared_via_compare_digest(self, monkeypatch) -> None:
        """Regression: token equality must go through hmac.compare_digest,
        never a plain `==`/`!=` (timing side-channel on LAN). A spy proves the
        comparison mechanism and that the Bearer prefix is stripped first.
        """
        monkeypatch.setattr(settings, "api_token", "sekret")
        calls: list[tuple[str, str]] = []
        real = hmac.compare_digest

        def spy(a: str, b: str) -> bool:
            calls.append((a, b))
            return real(a, b)

        monkeypatch.setattr(hmac, "compare_digest", spy)
        with TestClient(main_module.app) as client:
            assert client.get(
                "/api/v1/tools/time", headers={"X-Falso-Token": "wrong"}
            ).status_code == 401
            assert client.get(
                "/api/v1/tools/time", headers={"Authorization": "Bearer sekret"}
            ).status_code == 200

        assert calls == [("wrong", "sekret"), ("sekret", "sekret")]
        assert all(
            isinstance(a, str) and isinstance(b, str) for a, b in calls
        )


class TestOriginGuard:
    def test_disallowed_origin_rejected(self) -> None:
        with TestClient(main_module.app) as client:
            r = client.post(
                "/api/v1/chat",
                json={"prompt": CHAT_TOOL_PROMPT},
                headers={"Origin": "https://evil.example"},
            )
            assert r.status_code == 403

    def test_allowed_origin_accepted(self, monkeypatch) -> None:
        monkeypatch.setattr(
            settings, "allowed_origins", ["http://localhost:8000", "https://api.falso.dev"]
        )
        with TestClient(main_module.app) as client:
            r = client.post(
                "/api/v1/chat",
                json={"prompt": CHAT_TOOL_PROMPT},
                headers={"Origin": "https://api.falso.dev"},
            )
            assert r.status_code == 200

    def test_no_origin_accepted(self) -> None:
        with TestClient(main_module.app) as client:
            r = client.post("/api/v1/chat", json={"prompt": CHAT_TOOL_PROMPT})
            assert r.status_code == 200

    def test_gets_never_origin_checked(self) -> None:
        with TestClient(main_module.app) as client:
            r = client.get(
                "/api/v1/system/stats", headers={"Origin": "https://evil.example"}
            )
            assert r.status_code == 200


def _save_payload(conv_id: str) -> bytes:
    return json.dumps(
        {
            "id": conv_id,
            "title": "hi",
            "messages": [{"role": "user", "text": "hello", "time": "2026-01-01"}],
            "createdAt": "",
            "updatedAt": "",
        }
    ).encode("utf-8")


class TestRequestBodyLimit:
    """Size enforcement must cover both declared Content-Length and
    chunked/streamed bodies, reject with 413, and never read the full body."""

    def test_declared_length_over_limit_rejected(self, monkeypatch, tmp_path) -> None:
        monkeypatch.setattr(conv_module, "CHATS_DIR", tmp_path)
        payload = _save_payload(str(uuid.uuid4()))
        monkeypatch.setattr(settings, "max_request_bytes", len(payload) - 1)
        with TestClient(main_module.app) as client:
            r = client.post(
                "/api/v1/conversations/",
                content=payload,
                headers={"Content-Type": "application/json"},
            )
        assert r.status_code == 413
        assert r.json()["detail"] == "Request body too large"

    def test_declared_length_exactly_at_limit_accepted(self, monkeypatch, tmp_path) -> None:
        monkeypatch.setattr(conv_module, "CHATS_DIR", tmp_path)
        payload = _save_payload(str(uuid.uuid4()))
        monkeypatch.setattr(settings, "max_request_bytes", len(payload))
        with TestClient(main_module.app) as client:
            r = client.post(
                "/api/v1/conversations/",
                content=payload,
                headers={"Content-Type": "application/json"},
            )
        assert r.status_code == 200

    def test_streamed_chunked_body_rejected_midstream(self, monkeypatch, tmp_path) -> None:
        """Chunked encoding has no Content-Length; the streamed counter must
        reject with 413. (TestClient's transport coalesces chunked bodies into
        one message, so the 'stops reading' invariant is proven at unit level
        in TestMiddlewareBodyStreamGuard instead.)
        """
        monkeypatch.setattr(conv_module, "CHATS_DIR", tmp_path)
        monkeypatch.setattr(settings, "max_request_bytes", 64)

        def chunks():
            for size in (32, 32, 32, 32):
                yield b"x" * size

        with TestClient(main_module.app) as client:
            r = client.post(
                "/api/v1/conversations/",
                content=chunks(),
                headers={"Content-Type": "application/json"},
            )

        assert r.status_code == 413
        assert r.json()["detail"] == "Request body too large"

    def test_chunked_body_at_limit_accepted(self, monkeypatch, tmp_path) -> None:
        monkeypatch.setattr(conv_module, "CHATS_DIR", tmp_path)
        payload = _save_payload(str(uuid.uuid4()))
        monkeypatch.setattr(settings, "max_request_bytes", len(payload))
        with TestClient(main_module.app) as client:
            r = client.post(
                "/api/v1/conversations/",
                content=iter([payload[:40], payload[40:]]),
                headers={"Content-Type": "application/json"},
            )
        assert r.status_code == 200

    def test_chunked_body_over_limit_by_one_rejected(self, monkeypatch, tmp_path) -> None:
        monkeypatch.setattr(conv_module, "CHATS_DIR", tmp_path)
        payload = _save_payload(str(uuid.uuid4()))
        monkeypatch.setattr(settings, "max_request_bytes", len(payload) - 1)
        with TestClient(main_module.app) as client:
            r = client.post(
                "/api/v1/conversations/",
                content=iter([payload[:40], payload[40:]]),
                headers={"Content-Type": "application/json"},
            )
        assert r.status_code == 413

    def test_chat_body_limit_applies_before_route(self, monkeypatch) -> None:
        """A streamed body over the limit on the streaming chat endpoint is
        rejected during body parsing, before the route can run."""
        monkeypatch.setattr(settings, "max_request_bytes", 8)
        with TestClient(main_module.app) as client:
            r = client.post("/api/v1/chat", content=iter([b'{"prompt":"hi"}']))
        assert r.status_code == 413
        assert r.json()["detail"] == "Request body too large"

    def test_body_limit_not_applied_outside_api(self, monkeypatch) -> None:
        monkeypatch.setattr(settings, "max_request_bytes", 16)
        with TestClient(main_module.app) as client:
            r = client.post("/", content=iter([b"x" * 100]))
        assert r.status_code == 405
        assert r.json()["detail"] == "Method Not Allowed"


class TestMiddlewareBodyStreamGuard:
    """Drives SecurityMiddleware directly with scripted ASGI messages to prove
    the streaming guard: overflow raises 413 at the exact message that crosses
    the limit, and no further body messages are ever read (the request body is
    never buffered or consumed to completion)."""

    def _scope(self) -> dict:
        return {"type": "http", "method": "POST", "path": "/api/v1/x", "headers": []}

    async def test_stops_reading_at_overflow(self, monkeypatch) -> None:
        monkeypatch.setattr(settings, "max_request_bytes", 64)
        scripted: list[bytes] = [b"x" * 32, b"x" * 32, b"x" * 32, b"x" * 32]
        receive_calls = 0

        async def receive() -> dict:
            nonlocal receive_calls
            receive_calls += 1
            if scripted:
                chunk = scripted.pop(0)
                return {
                    "type": "http.request",
                    "body": chunk,
                    "more_body": bool(scripted),
                }
            return {"type": "http.disconnect"}

        async def send(message: dict) -> None:
            raise AssertionError("middleware must not send; overflow must raise")

        async def fake_app(scope, receive, send) -> None:
            while True:
                message = await receive()
                if message["type"] != "http.request":
                    return

        middleware = security_module.SecurityMiddleware(fake_app)
        with pytest.raises(StarletteHTTPException) as excinfo:
            await middleware(self._scope(), receive, send)

        assert excinfo.value.status_code == 413
        assert excinfo.value.detail == "Request body too large"
        assert receive_calls == 3

    async def test_small_body_reads_to_completion(self, monkeypatch) -> None:
        monkeypatch.setattr(settings, "max_request_bytes", 128)
        scripted: list[bytes] = [b"a" * 40, b"b" * 40]
        receive_calls = 0

        async def receive() -> dict:
            nonlocal receive_calls
            receive_calls += 1
            if scripted:
                chunk = scripted.pop(0)
                return {
                    "type": "http.request",
                    "body": chunk,
                    "more_body": bool(scripted),
                }
            return {"type": "http.disconnect"}

        async def fake_app(scope, receive, send) -> None:
            while True:
                message = await receive()
                if message["type"] != "http.request":
                    return

        middleware = security_module.SecurityMiddleware(fake_app)
        await middleware(self._scope(), receive, lambda message: None)

        assert receive_calls == 3
