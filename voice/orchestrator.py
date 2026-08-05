from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from typing import Any

from app.schemas.brain import ChatMessage
from app.services.brain import BrainService
from memory import MemoryService
from voice.base import AudioBuffer
from voice.config import VoiceConfig
from voice.service import VoiceService

logger = logging.getLogger(__name__)


class VoiceConversationOrchestrator:
    """Full-duplex intelligent voice conversation orchestrator.
    Connects STT -> Memory -> Brain Reasoning -> ElevenLabs TTS Streaming Audio.
    """

    def __init__(
        self,
        voice_service: VoiceService | None = None,
        brain_service: BrainService | None = None,
        memory_service: MemoryService | None = None,
        config: VoiceConfig | None = None,
    ) -> None:
        self.voice_service = voice_service or VoiceService()
        self.brain_service = brain_service or BrainService()
        self.memory_service = memory_service or MemoryService()
        self.config = config or VoiceConfig()

    async def process_voice_turn(
        self,
        audio_input: AudioBuffer | bytes,
        history: list[ChatMessage] | None = None,
        **kwargs: Any,
    ) -> AsyncIterator[bytes]:
        """Execute a complete intelligent voice turn:
        1. Speech-to-Text transcription
        2. Long-term memory context recall
        3. BrainService reasoning stream
        4. ElevenLabs TTS streaming audio synthesis back to client
        """
        # Step 1: Transcribe incoming audio
        stt_result = await self.voice_service.transcribe_audio(audio_input)
        prompt = stt_result.text.strip()
        if not prompt:
            logger.info("Voice turn received empty transcription — skipping LLM/TTS generation")
            return

        logger.info("Voice conversation input transcript: %r", prompt)

        # Step 2: Query long-term memory for relevant context
        memory_context = self.memory_service.get_context_summary(prompt, limit=2)
        augmented_prompt = prompt
        if memory_context:
            augmented_prompt = f"[{memory_context}]\nUser query: {prompt}"

        # Step 3: Stream tokens from BrainService
        async def token_stream() -> AsyncIterator[str]:
            yielded_any = False
            async for chunk_str in self.brain_service.chat(augmented_prompt, history=history):
                try:
                    import json
                    data = json.loads(chunk_str)
                    token = data.get("response", "") or data.get("error", "")
                    if token:
                        yielded_any = True
                        yield token
                except Exception as exc:  # noqa: BLE001
                    logger.debug("Non-JSON chunk in LLM stream: %s", exc)
            if not yielded_any:
                yield "Response generated."

        # Step 4: Stream synthesized ElevenLabs audio chunks back to client
        async for audio_chunk in self.voice_service.stream_speech(token_stream()):
            if audio_chunk:
                yield audio_chunk
