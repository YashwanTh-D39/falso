from __future__ import annotations

import logging

from fastapi import APIRouter, Request
from fastapi.responses import Response, StreamingResponse
from pydantic import BaseModel, Field

from voice import SileroVADService, VoiceService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/voice", tags=["Voice"])
voice_service = VoiceService()
silero_vad_service = SileroVADService()


class TTSRequest(BaseModel):
    text: str = Field(min_length=1, max_length=10_000)


class VADRequest(BaseModel):
    audio_base64: str = Field(..., description="Base64 encoded 16kHz PCM audio bytes")
    sample_rate: int = Field(default=16000, description="Audio sample rate in Hz")
    threshold: float = Field(default=0.75, ge=0.0, le=1.0)
    min_speech_duration_ms: int = Field(default=400, ge=100, le=2000)


@router.post("/vad")
async def process_vad(request: VADRequest):
    """Process audio chunk through Silero VAD neural speech classifier."""
    result = silero_vad_service.process_base64_pcm(
        request.audio_base64,
        sample_rate=request.sample_rate,
        threshold=request.threshold,
        min_speech_duration_ms=request.min_speech_duration_ms,
    )
    return result


@router.get("/vad/diagnostics")
async def get_vad_diagnostics():
    """Get real-time Silero VAD status and diagnostics."""
    return silero_vad_service.get_diagnostics()


@router.post("/tts")
async def text_to_speech(request: TTSRequest):
    result = await voice_service.synthesize_speech(request.text)
    media_type = "audio/mpeg" if result.format == "mp3" else "audio/wav"
    provider_name = "ElevenLabs" if result.format == "mp3" else "Local TTS"
    return Response(
        content=result.audio_data,
        media_type=media_type,
        headers={"X-TTS-Provider": provider_name}
    )


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

