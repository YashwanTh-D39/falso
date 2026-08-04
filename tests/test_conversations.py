import asyncio
import json
import uuid
from pathlib import Path

from fastapi.testclient import TestClient

import app.main as main_module

NEW_ID = f"test-{uuid.uuid4().hex[:8]}"


def _payload(conv_id: str) -> dict:
    return {
        "id": conv_id,
        "title": "Roundtrip",
        "createdAt": "2026-01-01T00:00:00Z",
        "updatedAt": "2026-01-01T00:00:00Z",
        "messages": [{"role": "user", "text": "hi", "time": "12:00"}],
    }


class TestConversationRoundtrip:
    def test_save_list_get_delete(self) -> None:
        with TestClient(main_module.app) as client:
            r = client.post("/api/v1/conversations/", json=_payload(NEW_ID))
            assert r.status_code == 200
            assert r.json() == {"ok": True}

            r = client.get("/api/v1/conversations/")
            assert r.status_code == 200
            ids = [item["id"] for item in r.json()]
            assert NEW_ID in ids

            r = client.get(f"/api/v1/conversations/{NEW_ID}")
            assert r.status_code == 200
            assert r.json()["id"] == NEW_ID
            assert r.json()["title"] == "Roundtrip"

            r = client.delete(f"/api/v1/conversations/{NEW_ID}")
            assert r.status_code == 200
            assert r.json() == {"ok": True}

            r = client.get(f"/api/v1/conversations/{NEW_ID}")
            assert r.status_code == 404

    def test_invalid_id_rejected(self) -> None:
        with TestClient(main_module.app) as client:
            r = client.get("/api/v1/conversations/evil.id")
            assert r.status_code == 400


class TestConversationConcurrency:
    def test_list_survives_file_vanishing_during_stat(self, monkeypatch, tmp_path) -> None:
        import app.routes.conversations as conv_module

        monkeypatch.setattr(conv_module, "CHATS_DIR", tmp_path)
        for i in range(10):
            cid = f"race{i}"
            (tmp_path / f"{cid}.json").write_text(
                f'{{"id": "{cid}", "title": "T", "createdAt": "", "updatedAt": "", "messages": []}}',
                encoding="utf-8",
            )

        # Simulate a concurrent DELETE: file gone from disk AND stat failing
        # (the window between glob() and the sort key).
        (tmp_path / "race5.json").unlink()
        real_stat = Path.stat

        def flaky_stat(self):
            if self.name == "race5.json":
                raise FileNotFoundError(self)
            return real_stat(self)

        monkeypatch.setattr(Path, "stat", flaky_stat)
        items = conv_module._list_files()
        assert all(item["id"] != "race5" for item in items)
        assert len(items) == 9

    async def test_concurrent_saves_same_id_never_crash(self, monkeypatch, tmp_path) -> None:
        import app.routes.conversations as conv_module

        monkeypatch.setattr(conv_module, "CHATS_DIR", tmp_path)
        payload = {
            "id": "contended",
            "title": "T",
            "createdAt": "2026-01-01T00:00:00Z",
            "updatedAt": "2026-01-01T00:00:00Z",
            "messages": [],
        }
        loop = asyncio.get_running_loop()
        await asyncio.gather(
            *[
                loop.run_in_executor(None, conv_module._write_file, "contended", payload)
                for _ in range(20)
            ]
        )
        data = json.loads((tmp_path / "contended.json").read_text(encoding="utf-8"))
        assert data["id"] == "contended"
