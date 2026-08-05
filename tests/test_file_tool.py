import os

import pytest

from app.tools.file_tool import FileTool
from config.settings import settings


@pytest.fixture
def workspace(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "file_tool_workspace", str(tmp_path))
    return tmp_path


class TestFileToolExecute:
    async def test_write_read_cycle(self, workspace) -> None:
        tool = FileTool()
        r = await tool.execute(command="write", path="a.txt", content="hello")
        assert r.success

        r = await tool.execute(command="read", path="a.txt")
        assert r.success
        assert r.data["content"] == "hello"

    async def test_delete_requires_confirmation(self, workspace) -> None:
        tool = FileTool()
        target = workspace / "b.txt"
        target.write_text("x", encoding="utf-8")

        r = await tool.execute(command="delete", path="b.txt")
        assert r.success
        assert r.data.get("confirmation_required") is True
        assert target.exists()

        r = await tool.execute(command="delete", path="b.txt", confirmed=True)
        assert r.success
        assert not target.exists()

    async def test_delete_non_empty_directory_fails_cleanly(self, workspace) -> None:
        tool = FileTool()
        d = workspace / "dir"
        d.mkdir()
        (d / "inner.txt").write_text("x", encoding="utf-8")

        r = await tool.execute(command="delete", path="dir", confirmed=True)
        assert not r.success
        assert "not empty" in r.error

    async def test_escape_outside_sandbox_rejected(self, tmp_path, monkeypatch) -> None:
        monkeypatch.setattr(settings, "file_tool_workspace", str(tmp_path))
        secret = tmp_path.parent / "secret.txt"
        secret.write_text("classified", encoding="utf-8")

        tool = FileTool()
        r = await tool.execute(command="read", path=str(secret))
        assert not r.success

    async def test_write_size_limit(self, workspace, monkeypatch) -> None:
        monkeypatch.setattr(settings, "max_file_write_bytes", 10)
        tool = FileTool()
        r = await tool.execute(command="write", path="big.txt", content="x" * 100)
        assert not r.success
        assert "too large" in r.error

    async def test_read_size_limit(self, workspace, monkeypatch) -> None:
        big = workspace / "big.txt"
        big.write_text("x" * 100, encoding="utf-8")
        monkeypatch.setattr(settings, "max_file_read_bytes", 10)
        tool = FileTool()
        r = await tool.execute(command="read", path="big.txt")
        assert not r.success
        assert "too large" in r.error

    async def test_search_result_cap(self, workspace, monkeypatch) -> None:
        for i in range(50):
            (workspace / f"f{i}.txt").write_text("x", encoding="utf-8")
        monkeypatch.setattr(settings, "max_search_results", 5)
        tool = FileTool()
        r = await tool.execute(command="search", pattern="*.txt")
        assert r.success
        assert r.data["count"] <= 5
        assert r.data["truncated"] is True

    async def test_read_directory_is_clean_error(self, workspace) -> None:
        tool = FileTool()
        r = await tool.execute(command="read", path=str(workspace))
        assert not r.success
        assert "Not a file" in r.error

    async def test_unknown_command(self, workspace) -> None:
        tool = FileTool()
        r = await tool.execute(command="teleport")
        assert not r.success
        assert "Unknown command" in r.error


class TestFileToolSearchSandbox:
    """Regression tests for the search sandbox escape.

    Pre-patch, `_search` concatenated the user pattern into `{base}/**/{pattern}`
    with no containment check. glob does not normalize ".." segments, so
    patterns like "../../../../Windows/*.ini" walked out of the sandbox and
    disclosed arbitrary filenames + sizes. Every test here fails on the
    pre-patch code and passes on the patched code.
    """

    async def test_search_rejects_traversal_patterns(self, workspace) -> None:
        tool = FileTool()
        for pat in (
            "../../../../Windows/*.ini",
            "..\\..\\..\\..\\Windows\\*.ini",
            "sub/../../secret.txt",
            "../../secret.txt",
        ):
            r = await tool.execute(command="search", pattern=pat)
            assert not r.success
            assert ".." in r.error

    async def test_search_cannot_disclose_outside_file(self, workspace) -> None:
        outside = workspace.parent / "secret.txt"
        outside.write_text("classified", encoding="utf-8")

        tool = FileTool()
        r = await tool.execute(command="search", pattern="secret.txt")
        assert r.success
        assert r.data["count"] == 0

    async def test_search_symlink_escape_rejected(self, workspace) -> None:
        outside_dir = workspace.parent / "outside"
        outside_dir.mkdir(exist_ok=True)
        (outside_dir / "leak.txt").write_text("x", encoding="utf-8")
        link = workspace / "link"
        try:
            os.symlink(outside_dir, link, target_is_directory=True)
        except (OSError, NotImplementedError):
            pytest.skip("directory symlinks unavailable on this platform")

        tool = FileTool()
        r = await tool.execute(command="search", pattern="link/*.txt")
        assert r.success
        assert r.data["count"] == 0
        assert all("leak.txt" not in m["path"] for m in r.data["matches"])

    async def test_search_filters_escaped_matches_with_clean_pattern(
        self, workspace, monkeypatch
    ) -> None:
        """Defense in depth: even when glob yields a path outside the sandbox
        (e.g. reached via a symlink or junction this platform cannot create in
        CI), the per-match containment filter must drop it."""
        import app.tools.file_tool as file_tool_module

        outside = workspace.parent / "leak.txt"
        outside.write_text("x", encoding="utf-8")
        real_glob = file_tool_module.glob_module.iglob

        # Unique name: matches nothing in the real sandbox bases, so the only
        # match comes from the hostile glob below.
        pattern = "falso_security_test_zzz_does_not_exist.txt"

        def hostile_glob(pattern, **kw):
            yield from real_glob(pattern, **kw)
            yield str(outside)

        monkeypatch.setattr(file_tool_module.glob_module, "iglob", hostile_glob)

        tool = FileTool()
        r = await tool.execute(command="search", pattern=pattern)
        assert r.success
        assert r.data["count"] == 0
        assert all("leak.txt" not in m["path"] for m in r.data["matches"])

    async def test_search_still_finds_files_inside_workspace(self, workspace) -> None:
        (workspace / "sub").mkdir(exist_ok=True)
        (workspace / "sub" / "hello.txt").write_text("x", encoding="utf-8")

        tool = FileTool()
        r = await tool.execute(command="search", pattern="hello.txt")
        assert r.success
        assert any(m["path"].endswith("hello.txt") for m in r.data["matches"])


class TestFileToolMatching:
    def setup_method(self) -> None:
        self.tool = FileTool()

    def test_list_files(self) -> None:
        kwargs = self.tool.match_prompt("list files")
        assert kwargs["command"] == "list"

    def test_workspace_is_default_relative_target(self, workspace) -> None:
        kwargs = self.tool.match_prompt("list files")
        assert kwargs["command"] == "list"
        assert kwargs["path"] == str(workspace)

    def test_read_file(self) -> None:
        kwargs = self.tool.match_prompt("read notes.txt")
        assert kwargs["command"] == "read"
        assert kwargs["path"] == "notes.txt"

    def test_write_with_quoted_content(self) -> None:
        kwargs = self.tool.match_prompt('write "hello world" to greet.txt')
        assert kwargs["command"] == "write"
        assert kwargs["content"] == "hello world"

    def test_delete_requires_confirmation_flag(self) -> None:
        kwargs = self.tool.match_prompt("delete old.txt")
        assert kwargs["command"] == "delete"
        assert kwargs["confirmed"] is False

    def test_unrelated_prompt_does_not_match(self) -> None:
        kwargs = self.tool.match_prompt("what is the meaning of life")
        assert kwargs is None
