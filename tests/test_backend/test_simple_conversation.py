"""
Test Suite for Milestone 2.6: Simple, Clean Conversation Mode

Tests exact required prompts:
1. "hello" -> "Hello! How can I help?"
2. "hello again" -> "Hello again! How can I help?"
3. "how are you?" -> "I'm doing well! How can I help?"
4. "what is Python?" -> Concise direct explanation
5. "what is the capital of France?" -> "The capital of France is Paris."
6. "say hello by voice" -> "Hello! How can I help?"
7. Verification that responses contain zero meta/voice disclaimers
"""

import json
import pytest

from app.services.brain import BrainService, _sanitize_history
from app.schemas.brain import ChatMessage


class FakeSimpleProvider:
    name = "fake"
    model = "fake-model"

    async def stream_chat(self, messages: list[dict], **kwargs):
        user_msg = next((m["content"] for m in messages if m.get("role") == "user"), "").lower()
        if "python" in user_msg:
            yield type("Chunk", (), {"text": "Python is a high-level, general-purpose programming language known for readability."})()
        else:
            yield type("Chunk", (), {"text": "Hello! How can I help?"})()


class TestSimpleCleanConversation:

    @pytest.mark.asyncio
    async def test_1_hello(self):
        brain = BrainService(provider=FakeSimpleProvider())
        events = [json.loads(line) async for line in brain.chat("hello")]
        full_text = "".join(e.get("response", "") for e in events)
        assert full_text.strip() == "Hello! How can I help?"

    @pytest.mark.asyncio
    async def test_2_hello_again(self):
        brain = BrainService(provider=FakeSimpleProvider())
        events = [json.loads(line) async for line in brain.chat("hello again")]
        full_text = "".join(e.get("response", "") for e in events)
        assert full_text.strip() == "Hello again! How can I help?"

    @pytest.mark.asyncio
    async def test_3_how_are_you(self):
        brain = BrainService(provider=FakeSimpleProvider())
        events = [json.loads(line) async for line in brain.chat("how are you?")]
        full_text = "".join(e.get("response", "") for e in events)
        assert full_text.strip() == "I'm doing well! How can I help?"

    @pytest.mark.asyncio
    async def test_4_what_is_python(self):
        brain = BrainService(provider=FakeSimpleProvider())
        events = [json.loads(line) async for line in brain.chat("what is Python?")]
        full_text = "".join(e.get("response", "") for e in events)
        assert "Python" in full_text
        assert "programming language" in full_text.lower()
        # Verify no markdown clutter or meta text
        assert "Awaiting Your Voice Input" not in full_text
        assert "Simulated Voice Output" not in full_text

    @pytest.mark.asyncio
    async def test_5_capital_of_france(self):
        brain = BrainService(provider=FakeSimpleProvider())
        events = [json.loads(line) async for line in brain.chat("what is the capital of France?")]
        full_text = "".join(e.get("response", "") for e in events)
        assert full_text.strip() == "The capital of France is Paris."

    @pytest.mark.asyncio
    async def test_6_say_hello_by_voice(self):
        brain = BrainService(provider=FakeSimpleProvider())
        events = [json.loads(line) async for line in brain.chat("say hello by voice")]
        full_text = "".join(e.get("response", "") for e in events)
        assert full_text.strip() == "Hello! How can I help?"

    def test_7_history_sanitization(self):
        raw_history = [
            ChatMessage(role="user", content="hello"),
            ChatMessage(role="assistant", content="Hello! [Simulated Voice Output: Voice Activation] Awaiting Your Voice Input..."),
            ChatMessage(role="user", content="how are you?")
        ]
        clean = _sanitize_history(raw_history)
        for msg in clean:
            assert "Simulated Voice Output" not in msg.content
            assert "Awaiting Your Voice Input" not in msg.content
