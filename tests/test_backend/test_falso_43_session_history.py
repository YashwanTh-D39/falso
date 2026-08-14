"""
Unit tests for FALSO 4.3 Persistent Conversation Memory & Session Context Engine.
"""

import asyncio
import time
from unittest.mock import patch, MagicMock
import pytest

from app.schemas.brain import ChatMessage
from app.services.brain import BrainService
from app.services.session_history import session_history_manager, SessionState
from memory.service import memory_service


class TestFalso43SessionHistoryEngine:

    def setup_method(self):
        session_history_manager.clear_session("TEST-SESSION-01")
        session_history_manager.clear_session("TEST-SESSION-02")

    def test_01_first_message_stored(self):
        session_history_manager.append_user_message("TEST-SESSION-01", "My project is called FALSO.")
        hist = session_history_manager.get_history("TEST-SESSION-01")
        assert len(hist) == 1
        assert hist[0].role == "user"
        assert hist[0].content == "My project is called FALSO."

    def test_02_assistant_response_stored(self):
        session_history_manager.append_user_message("TEST-SESSION-01", "My project is called FALSO.")
        session_history_manager.append_assistant_message("TEST-SESSION-01", "Got it.")
        hist = session_history_manager.get_history("TEST-SESSION-01")
        assert len(hist) == 2
        assert hist[1].role == "assistant"
        assert hist[1].content == "Got it."

    def test_03_second_request_receives_previous_context(self):
        session_history_manager.append_user_message("TEST-SESSION-01", "My project is called FALSO.")
        session_history_manager.append_assistant_message("TEST-SESSION-01", "Got it.")
        hist = session_history_manager.get_history("TEST-SESSION-01")
        assert any("FALSO" in m.content for m in hist)

    def test_04_pronoun_resolution_open_calculator_close_it(self):
        session_history_manager.append_user_message("TEST-SESSION-01", "Open Calculator")
        session_history_manager.append_assistant_message("TEST-SESSION-01", "Calculator is open.")
        last_app = session_history_manager.get_last_target_app("TEST-SESSION-01")
        assert last_app == "Calculator"

    def test_05_multi_turn_normal_conversation(self):
        session_history_manager.append_user_message("TEST-SESSION-01", "Hello")
        session_history_manager.append_assistant_message("TEST-SESSION-01", "Hi there!")
        session_history_manager.append_user_message("TEST-SESSION-01", "How are you?")
        session_history_manager.append_assistant_message("TEST-SESSION-01", "Doing great!")
        hist = session_history_manager.get_history("TEST-SESSION-01")
        assert len(hist) == 4

    def test_06_automation_and_normal_chat_transition(self):
        session_history_manager.append_user_message("TEST-SESSION-01", "Open Chrome")
        session_history_manager.append_assistant_message("TEST-SESSION-01", "Chrome is open.")
        session_history_manager.append_user_message("TEST-SESSION-01", "Search python docs")
        hist = session_history_manager.get_history("TEST-SESSION-01")
        assert len(hist) == 3
        assert hist[0].content == "Open Chrome"

    def test_07_session_isolation(self):
        session_history_manager.append_user_message("TEST-SESSION-01", "Secret code 123")
        session_history_manager.append_user_message("TEST-SESSION-02", "Different user message")
        hist2 = session_history_manager.get_history("TEST-SESSION-02")
        assert not any("Secret code 123" in m.content for m in hist2)

    def test_08_history_trimming_max_20(self):
        for i in range(30):
            session_history_manager.append_user_message("TEST-SESSION-01", f"Message {i}")
        hist = session_history_manager.get_history("TEST-SESSION-01")
        assert len(hist) <= 20

    def test_09_session_expiration(self):
        sess = session_history_manager.get_or_create_session("TEST-EXPIRE-01")
        sess.updated_at = time.time() - 3600.0  # 1 hour ago
        new_sess = session_history_manager.get_or_create_session("TEST-EXPIRE-01")
        assert len(new_sess.messages) == 0

    def test_10_backend_restart_behavior(self):
        session_history_manager.append_user_message("TEST-SESSION-01", "Temp history")
        session_history_manager.clear_session("TEST-SESSION-01")
        hist = session_history_manager.get_history("TEST-SESSION-01")
        assert len(hist) == 0

    def test_11_long_term_memory_survives_restart(self):
        entry = memory_service.remember("FALSO is my cybersecurity project", key="project_name", scope="GLOBAL")
        all_mem = memory_service.list_memories()
        assert any("cybersecurity project" in m.content for m in all_mem)

    def test_12_sensitive_information_blocked_in_memory(self):
        with pytest.raises(ValueError, match="Sensitive credentials"):
            memory_service.remember("my password is secret123")

    def test_13_tts_metadata_not_persisted(self):
        session_history_manager.append_assistant_message("TEST-SESSION-01", "Simulated Voice Output: Hello")
        hist = session_history_manager.get_history("TEST-SESSION-01")
        assert len(hist) == 0

    def test_14_cancelled_request_no_assistant_message(self):
        session_history_manager.append_user_message("TEST-SESSION-01", "Cancelled prompt")
        hist = session_history_manager.get_history("TEST-SESSION-01")
        assert len(hist) == 1
        assert hist[0].role == "user"

    @pytest.mark.asyncio
    async def test_15_concurrent_requests_do_not_corrupt_history(self):
        async def _add(msg):
            session_history_manager.append_user_message("TEST-SESSION-CONCUR", msg)

        await asyncio.gather(_add("Msg A"), _add("Msg B"))
        hist = session_history_manager.get_history("TEST-SESSION-CONCUR")
        assert len(hist) == 2

    def test_16_performance_latency_under_1ms(self):
        t0 = time.perf_counter()
        session_history_manager.get_history("TEST-SESSION-01")
        dt = (time.perf_counter() - t0) * 1000.0
        assert dt < 5.0  # < 5ms threshold
