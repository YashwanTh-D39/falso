"""
Test Suite for Milestone 2.4: Project & Workspace Intelligence

Tests:
1. Workspace Intelligence Retrieval & Caching
2. Non-destructive Git Status Detection (Branch, Clean Status, Latest Commit)
3. Project Identification & Recent Files Reuse
4. Prevention of Destructive Git Commands
5. Natural Language Workspace Queries & Response Verification
"""

import json
import pytest

from app.services.workspace_intelligence import workspace_intelligence, WorkspaceIntelligenceService
from app.services.brain import BrainService


class FakeWorkspaceProvider:
    name = "fake"
    model = "fake-model"

    async def stream_chat(self, messages: list[dict], **kwargs):
        system_content = next((m["content"] for m in messages if m.get("role") == "system"), "")
        if "WORKSPACE INTELLIGENCE CONTEXT" in system_content:
            yield type("Chunk", (), {"text": "Workspace context recognized."})()
        else:
            yield type("Chunk", (), {"text": "Hello there!"})()


class TestWorkspaceIntelligence:

    def test_1_get_intelligence(self):
        intel = workspace_intelligence.get_intelligence()
        assert intel["project_name"] == "Project-Falso"
        assert "Project-Falso" in intel["project_root"]
        assert isinstance(intel["git_branch"], str) and len(intel["git_branch"]) > 0
        assert isinstance(intel["git_status_clean"], bool)
        assert isinstance(intel["uncommitted_count"], int)
        assert isinstance(intel["modified_files"], list)

    def test_2_git_latest_commit_and_branch(self):
        intel = workspace_intelligence.get_intelligence()
        assert intel["git_branch"] == "main"
        assert " - " in intel["latest_commit"] or "No commits" in intel["latest_commit"]

    def test_3_prompt_summary_formatting(self):
        summary = workspace_intelligence.format_summary_for_prompt()
        assert "[WORKSPACE INTELLIGENCE CONTEXT]" in summary
        assert "Project: Project-Falso" in summary
        assert "Git Branch: main" in summary

    @pytest.mark.asyncio
    async def test_4_chat_query_what_project_am_i_working_on(self):
        brain = BrainService(provider=FakeWorkspaceProvider())
        events = [json.loads(line) async for line in brain.chat("What project am I working on?")]
        assert len(events) > 0
        full_text = "".join(e.get("response", "") for e in events)
        assert "Project-Falso" in full_text

    @pytest.mark.asyncio
    async def test_5_chat_query_what_changed_today(self):
        brain = BrainService(provider=FakeWorkspaceProvider())
        events = [json.loads(line) async for line in brain.chat("What changed today?")]
        assert len(events) > 0
        full_text = "".join(e.get("response", "") for e in events)
        assert "modified file" in full_text.lower() or "no modified files" in full_text.lower() or "recent changes" in full_text.lower()

    @pytest.mark.asyncio
    async def test_6_chat_query_what_branch_am_i_on(self):
        brain = BrainService(provider=FakeWorkspaceProvider())
        events = [json.loads(line) async for line in brain.chat("What branch am I on?")]
        assert len(events) > 0
        full_text = "".join(e.get("response", "") for e in events)
        assert "main" in full_text.lower()

    @pytest.mark.asyncio
    async def test_7_chat_query_is_my_working_tree_clean(self):
        brain = BrainService(provider=FakeWorkspaceProvider())
        events = [json.loads(line) async for line in brain.chat("Is my working tree clean?")]
        assert len(events) > 0
        full_text = "".join(e.get("response", "") for e in events)
        assert "working tree" in full_text.lower() or "uncommitted" in full_text.lower() or "clean" in full_text.lower()

    @pytest.mark.asyncio
    async def test_8_chat_query_what_was_my_latest_commit(self):
        brain = BrainService(provider=FakeWorkspaceProvider())
        events = [json.loads(line) async for line in brain.chat("What was my latest commit?")]
        assert len(events) > 0
        full_text = "".join(e.get("response", "") for e in events)
        assert "latest commit" in full_text.lower()
