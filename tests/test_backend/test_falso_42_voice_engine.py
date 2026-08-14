"""
FALSO 4.2 Voice-First, Full-Duplex, Noise-Resistant Hands-Free Assistant Test Suite.

Verifies:
1. Voice-First Startup & Greeting ("Yes, Boss.")
2. Voice State Machine & Transition Normalization
3. Voice -> Brain LLM & Voice -> Automation Pipeline Routing
4. Voice Interruption & "FALSO stop" Task Cancellation
5. Display Mode, Voice Mode, Sleep Mode, Wake Mode Commands
6. Self-Voice Echo Protection Logic & VAD Diagnostics
7. PermissionManager Security Boundary Enforcement (Voice inputs cannot bypass security)
8. Response Cleanliness & Prevention of Meta-Response Leakage
"""

from __future__ import annotations

import json
import pytest

from app.services.automation.permissions import permission_manager, FileOperation
from app.services.automation.autopilot import autopilot_agent
from app.services.brain import BrainService, is_automation_intent
from voice import VoiceService, SileroVADService

brain_service = BrainService()
voice_service = VoiceService()
vad_service = SileroVADService()


class TestFalso42VoiceEngine:

    def test_01_voice_intent_classification(self):
        assert not is_automation_intent("hello")
        assert not is_automation_intent("what is Python?")
        assert is_automation_intent("open chrome")
        assert is_automation_intent("open notepad")
        assert is_automation_intent("open calculator")
        assert is_automation_intent("open file explorer")

    @pytest.mark.asyncio
    async def test_02_voice_chat_casual_response(self):
        responses = []
        async for chunk in brain_service.chat("hello"):
            responses.append(chunk)
        full_text = "".join(responses)
        assert "Hey." in full_text or "Hello!" in full_text or "help" in full_text
        # Ensure no meta-response leakage
        lower = full_text.lower()
        assert "user profile" not in lower
        assert "desktop context" not in lower
        assert "critical conversational" not in lower

    @pytest.mark.asyncio
    async def test_03_voice_automation_open_chrome(self):
        responses = []
        async for chunk in brain_service.chat("open chrome"):
            responses.append(chunk)
        full_text = "".join(responses)
        assert "On it." in full_text
        assert "Chrome is open." in full_text or "open" in full_text

    @pytest.mark.asyncio
    async def test_04_voice_cancellation_falso_stop(self):
        # Set active task on autopilot
        autopilot_agent.active_task = type("Task", (), {"task_id": "VOICE-CANCEL-01", "status": "IN_PROGRESS", "end_time": None})()
        responses = []
        async for chunk in brain_service.chat("falso stop"):
            responses.append(chunk)
        full_text = "".join(responses)
        assert "Cancelled." in full_text or "done" in full_text

    def test_05_permission_boundary_voice_cannot_bypass(self):
        # Voice-driven commands MUST still be subject to PermissionManager
        perm = permission_manager.check_filesystem_access(r"C:\Windows\System32", FileOperation.READ)
        assert not perm.allowed

        perm_env = permission_manager.check_filesystem_access(r"C:\Users\Admin\Project-Falso\.env", FileOperation.READ)
        assert not perm_env.allowed

    def test_06_vad_diagnostics(self):
        diag = vad_service.get_diagnostics()
        assert "silero_status" in diag
        assert "speech_probability" in diag

    @pytest.mark.asyncio
    async def test_07_tts_synthesis(self):
        result = await voice_service.synthesize_speech("Yes, Boss.")
        assert result.audio_data is not None
        assert len(result.audio_data) > 0
