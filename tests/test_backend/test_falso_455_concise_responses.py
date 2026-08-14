"""
Unit tests for FALSO 4.5.5 Concise Natural Response & Output Noise Elimination.
"""

import json
import pytest
from unittest.mock import patch, MagicMock

from app.services.brain import BrainService
from app.services.automation.autopilot import autopilot_agent
from app.services.session_history import session_history_manager


from app.services.automation.permissions import permission_manager


class TestFalso455ConciseResponses:

    def setup_method(self):
        permission_manager.disable_lockdown()
        session_history_manager.clear_session("TEST-CONCISE-SESSION")

    def teardown_method(self):
        permission_manager.disable_lockdown()

    @pytest.mark.asyncio
    async def test_01_hello_produces_hey(self):
        brain = BrainService()
        responses = [json.loads(line).get("response", "") async for line in brain.chat("Hello", session_id="TEST-CONCISE-SESSION")]
        full_text = "".join(responses).strip()
        assert "Hey." in full_text

    @pytest.mark.asyncio
    async def test_02_open_calculator_concise_confirmation(self):
        brain = BrainService()
        with patch.object(autopilot_agent, "run_goal", return_value="Calculator is open."):
            responses = [json.loads(line).get("response", "") async for line in brain.chat("Open Calculator", session_id="TEST-CONCISE-SESSION")]
            full_text = "".join(responses).strip()
            assert "Calculator is open." in full_text
            assert "Here is what I did" not in full_text
            assert "task_id" not in full_text

    @pytest.mark.asyncio
    async def test_03_ten_plus_ten_produces_twenty(self):
        brain = BrainService()
        with patch.object(autopilot_agent, "run_goal", return_value="20."):
            responses = [json.loads(line).get("response", "") async for line in brain.chat("Add 10 + 10", session_id="TEST-CONCISE-SESSION")]
            full_text = "".join(responses).strip()
            assert "20" in full_text

    @pytest.mark.asyncio
    async def test_04_open_chrome_concise_confirmation(self):
        brain = BrainService()
        with patch.object(autopilot_agent, "run_goal", return_value="Chrome is open."):
            responses = [json.loads(line).get("response", "") async for line in brain.chat("Open Chrome", session_id="TEST-CONCISE-SESSION")]
            full_text = "".join(responses).strip()
            assert "Chrome is open." in full_text

    @pytest.mark.asyncio
    async def test_05_open_new_tab_concise_confirmation(self):
        brain = BrainService()
        with patch.object(autopilot_agent, "run_goal", return_value="New tab opened."):
            responses = [json.loads(line).get("response", "") async for line in brain.chat("Open a new tab", session_id="TEST-CONCISE-SESSION")]
            full_text = "".join(responses).strip()
            assert "New tab opened." in full_text

    @pytest.mark.asyncio
    async def test_06_failed_action_concise_failure(self):
        brain = BrainService()
        with patch.object(autopilot_agent, "run_goal", return_value="I couldn't complete that."):
            responses = [json.loads(line).get("response", "") async for line in brain.chat("Open NonExistentApp", session_id="TEST-CONCISE-SESSION")]
            full_text = "".join(responses).strip()
            assert "I couldn't complete that." in full_text

    @pytest.mark.asyncio
    async def test_07_verification_failure_concise_failure(self):
        brain = BrainService()
        with patch.object(autopilot_agent, "run_goal", return_value="I couldn't verify that."):
            responses = [json.loads(line).get("response", "") async for line in brain.chat("Close Claude", session_id="TEST-CONCISE-SESSION")]
            full_text = "".join(responses).strip()
            assert "I couldn't verify that." in full_text

    @pytest.mark.asyncio
    async def test_08_permission_denial_concise(self):
        brain = BrainService()
        responses = [json.loads(line).get("response", "") async for line in brain.chat("lockdown", session_id="TEST-CONCISE-SESSION")]
        full_text = "".join(responses).strip()
        assert "Emergency Lockdown" in full_text

    @pytest.mark.asyncio
    async def test_09_knowledge_question_useful(self):
        brain = BrainService()
        responses = [json.loads(line).get("response", "") async for line in brain.chat("What is the capital of France?", session_id="TEST-CONCISE-SESSION")]
        full_text = "".join(responses).strip()
        assert "Paris" in full_text

    @pytest.mark.asyncio
    async def test_10_explicit_explain_request_detailed(self):
        brain = BrainService()
        responses = [json.loads(line).get("response", "") async for line in brain.chat("Why couldn't you close Claude?", session_id="TEST-CONCISE-SESSION")]
        full_text = "".join(responses).strip()
        assert "Claude stayed open" in full_text or "couldn't verify" in full_text

    @pytest.mark.asyncio
    async def test_11_diagnostics_never_leak_into_normal_chat(self):
        brain = BrainService()
        responses = [json.loads(line).get("response", "") async for line in brain.chat("Hello", session_id="TEST-CONCISE-SESSION")]
        full_text = "".join(responses)
        assert "[AUTOMATION]" not in full_text
        assert "request_id" not in full_text

    @pytest.mark.asyncio
    async def test_12_task_ids_never_appear_in_chat(self):
        brain = BrainService()
        responses = [json.loads(line).get("response", "") async for line in brain.chat("Hello", session_id="TEST-CONCISE-SESSION")]
        full_text = "".join(responses)
        assert "task_id" not in full_text

    @pytest.mark.asyncio
    async def test_13_request_ids_never_appear_in_chat_text(self):
        brain = BrainService()
        responses = [json.loads(line).get("response", "") async for line in brain.chat("Hello", session_id="TEST-CONCISE-SESSION")]
        full_text = "".join(responses)
        assert "FALSO-2026" not in full_text

    @pytest.mark.asyncio
    async def test_14_internal_logs_never_appear_in_chat(self):
        brain = BrainService()
        responses = [json.loads(line).get("response", "") async for line in brain.chat("Hello", session_id="TEST-CONCISE-SESSION")]
        full_text = "".join(responses)
        assert "[KEYBOARD]" not in full_text
        assert "[WINDOW]" not in full_text

    @pytest.mark.asyncio
    async def test_15_memory_retrieval_remains_invisible(self):
        from memory.service import memory_service
        memory_service.remember("User main goal is Cybersecurity Automation", source="user_explicit")
        brain = BrainService()
        responses = [json.loads(line).get("response", "") async for line in brain.chat("Hello", session_id="TEST-CONCISE-SESSION")]
        full_text = "".join(responses)
        assert "I retrieved this from memory" not in full_text

    @pytest.mark.asyncio
    async def test_16_voice_responses_remain_concise(self):
        brain = BrainService()
        responses = [json.loads(line).get("response", "") async for line in brain.chat("hello falso", session_id="TEST-CONCISE-SESSION")]
        full_text = "".join(responses).strip()
        assert full_text == "Yes boss."

    @pytest.mark.asyncio
    async def test_17_no_unnecessary_repeated_confirmations(self):
        brain = BrainService()
        responses = [json.loads(line).get("response", "") async for line in brain.chat("Hello", session_id="TEST-CONCISE-SESSION")]
        full_text = "".join(responses)
        assert "Certainly" not in full_text
        assert "Of course" not in full_text

    @pytest.mark.asyncio
    async def test_18_no_fake_success(self):
        resp = autopilot_agent._concise_failure_response("unknown action")
        assert resp == "I couldn't complete that."
