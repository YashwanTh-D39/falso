import pytest

from app.providers.base import AIProviderError
from app.providers.gemini import GeminiProvider


def test_gemini_provider_init_defaults():
    provider = GeminiProvider()
    assert provider.name == "gemini"
    assert "gemini" in provider.model


def test_gemini_to_payload_conversion():
    messages = [
        {"role": "system", "content": "You are Falso AI."},
        {"role": "user", "content": "Hello!"},
        {"role": "assistant", "content": "Hi there!"},
        {"role": "user", "content": "How are you?"},
    ]

    payload = GeminiProvider.to_gemini_payload(messages)
    assert "systemInstruction" in payload
    assert payload["systemInstruction"]["parts"][0]["text"] == "You are Falso AI."

    contents = payload["contents"]
    assert len(contents) == 3
    assert contents[0]["role"] == "user"
    assert contents[1]["role"] == "model"
    assert contents[2]["role"] == "user"


@pytest.mark.asyncio
async def test_gemini_provider_missing_key_raises_ai_provider_error():
    provider = GeminiProvider(api_key="")
    with pytest.raises(AIProviderError, match="Gemini API key not configured"):
        async for _ in provider.stream_chat([{"role": "user", "content": "hi"}]):
            pass
