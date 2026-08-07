import json
import pytest
from app.services.brain import BrainService
from voice.cleaner import clean_text_for_speech


@pytest.mark.asyncio
async def test_web_intelligence_synthesis_weather():
    """Verify live web facts are synthesized into conversational response and spoken text strips sources."""
    bs = BrainService()
    query = "What's the weather in Visakhapatnam?"

    full_resp = ""
    async for chunk_str in bs.chat(query):
        data = json.loads(chunk_str)
        if "response" in data:
            full_resp += data["response"]

    assert len(full_resp) > 0
    assert "http" not in full_resp.lower() or "<details>" in full_resp.lower()

    spoken = clean_text_for_speech(full_resp)
    assert "http" not in spoken
    assert "www" not in spoken
    assert "details" not in spoken.lower()
    assert "sources" not in spoken.lower()
    assert len(spoken) > 0
