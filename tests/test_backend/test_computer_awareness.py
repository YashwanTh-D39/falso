"""
Test Suite for Milestone 2.2: Computer Awareness

Tests:
1. Computer Context Generation & Normalization
2. Active App & Active Window Detection
3. Project & Workspace Detection
4. System Metrics (CPU, RAM, Network)
5. Computer Awareness Chat Queries & Non-blocking Streaming Performance
"""

import json
import pytest

from app.services.context_detector import context_detector, ContextDetectorService
from app.services.brain import BrainService


class FakeAwarenessProvider:
    name = "fake"
    model = "fake-model"

    async def stream_chat(self, messages: list[dict], **kwargs):
        system_content = next((m["content"] for m in messages if m.get("role") == "system"), "")
        if "COMPUTER AWARENESS CONTEXT" in system_content:
            yield type("Chunk", (), {"text": "Computer context recognized."})()
        else:
            yield type("Chunk", (), {"text": "Hello there!"})()


class TestComputerAwareness:

    def test_1_computer_context_normalization(self):
        ctx = context_detector.detect_context()
        assert "active_app" in ctx
        assert "active_window" in ctx
        assert "current_project" in ctx
        assert "current_workspace" in ctx
        assert "running_apps" in ctx
        assert "cpu_usage" in ctx
        assert "ram_usage" in ctx
        assert "network_status" in ctx
        assert ctx["current_project"] == "Project-Falso"

    def test_2_active_app_and_window_detection(self):
        active_app, active_window = context_detector._detect_active_app_and_window()
        assert isinstance(active_app, str) and len(active_app) > 0
        assert isinstance(active_window, str) and len(active_window) > 0

    def test_3_project_and_workspace_detection(self):
        ctx = context_detector.detect_context()
        assert ctx["current_project"] == "Project-Falso"
        assert "Project-Falso" in ctx["current_workspace"]

    def test_4_system_metrics(self):
        ctx = context_detector.detect_context()
        assert "%" in ctx["cpu_usage"]
        assert "GB" in ctx["ram_usage"]
        assert ctx["network_status"] == "Connected"

    def test_5_prompt_summary_formatting(self):
        summary = context_detector.format_summary_for_prompt()
        assert "[COMPUTER AWARENESS CONTEXT]" in summary
        assert "Active Application:" in summary
        assert "Current Project: Project-Falso" in summary
        assert "CPU Usage:" in summary

    @pytest.mark.asyncio
    async def test_6_chat_query_what_am_i_working_on(self):
        brain = BrainService(provider=FakeAwarenessProvider())
        events = [json.loads(line) async for line in brain.chat("What am I working on?")]
        assert len(events) > 0
        full_text = "".join(e.get("response", "") for e in events)
        assert "Project-Falso" in full_text

    @pytest.mark.asyncio
    async def test_7_chat_query_running_applications(self):
        brain = BrainService(provider=FakeAwarenessProvider())
        events = [json.loads(line) async for line in brain.chat("What applications are running?")]
        assert len(events) > 0
        full_text = "".join(e.get("response", "") for e in events)
        assert "running applications" in full_text.lower() or "currently running" in full_text.lower()

    @pytest.mark.asyncio
    async def test_8_chat_query_cpu_usage(self):
        brain = BrainService(provider=FakeAwarenessProvider())
        events = [json.loads(line) async for line in brain.chat("What is my CPU usage?")]
        assert len(events) > 0
        full_text = "".join(e.get("response", "") for e in events)
        assert "%" in full_text or "cpu" in full_text.lower()

    @pytest.mark.asyncio
    async def test_9_chat_query_what_project_is_open(self):
        brain = BrainService(provider=FakeAwarenessProvider())
        events = [json.loads(line) async for line in brain.chat("What project is open?")]
        assert len(events) > 0
        full_text = "".join(e.get("response", "") for e in events)
        assert "Project-Falso" in full_text

    @pytest.mark.asyncio
    async def test_10_normal_chat_performance_unblocked(self):
        brain = BrainService(provider=FakeAwarenessProvider())
        events = [json.loads(line) async for line in brain.chat("Explain photosynthesizing plants in depth")]
        assert len(events) > 0
        assert events[-1]["done"] is True
