from __future__ import annotations

import logging

from fastapi import APIRouter, Request
from fastapi.responses import Response, StreamingResponse
from pydantic import BaseModel, Field

from voice import VoiceService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/voice", tags=["Voice"])
voice_service = VoiceService()


class TTSRequest(BaseModel):
    text: str = Field(min_length=1, max_length=10_000)


@router.post("/tts")
async def text_to_speech(request: TTSRequest):
    result = await voice_service.synthesize_speech(request.text)
    media_type = "audio/mpeg" if result.format == "mp3" else "audio/wav"
    return Response(content=result.audio_data, media_type=media_type)


@router.post("/stream")
async def stream_text_to_speech(request: TTSRequest):
    async def text_generator():
        # Yield words in chunks to simulate streaming text token feed
        words = request.text.split()
        for i in range(0, len(words), 3):
            yield " ".join(words[i:i + 3]) + " "

    media_type = "audio/mpeg" if hasattr(voice_service.tts_engine, "api_key") and voice_service.tts_engine.api_key else "audio/wav"
    return StreamingResponse(
        voice_service.stream_speech(text_generator()),
        media_type=media_type,
    )


@router.post("/conversation")
async def voice_conversation(request: Request):
    """Full-duplex end-to-end voice conversation endpoint:
    STT -> Memory Recall -> Brain LLM Streaming -> ElevenLabs TTS Audio Stream.
    """
    from voice.orchestrator import VoiceConversationOrchestrator

    orchestrator = VoiceConversationOrchestrator(voice_service=voice_service)
    audio_data = await request.body()
    if not audio_data:
        audio_data = b"\x00" * 3200

    media_type = "audio/mpeg" if hasattr(voice_service.tts_engine, "api_key") and voice_service.tts_engine.api_key else "audio/wav"
    return StreamingResponse(
        orchestrator.process_voice_turn(audio_data),
        media_type=media_type,
    )

