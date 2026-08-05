# Intelligent Voice Conversation System

Falso includes a full-duplex, low-latency voice AI pipeline built for continuous streaming conversations with real-time barge-in interruption.

```
┌─────────────────────────────────────────────────────────────────────────┐
│                        Browser / Client Microphone                      │
│        (Audio Constraints: Echo Cancellation, Noise Suppression)         │
└────────────────────────────────────┬────────────────────────────────────┘
                                     │ Streamed Audio Input
┌────────────────────────────────────▼────────────────────────────────────┐
│                    VoiceConversationOrchestrator                        │
│                                                                         │
│  1. Speech-to-Text (STT)           LocalSTTEngine / Cloud STT           │
│  2. Memory Context Recall          MemoryService (Vector / TF-IDF)      │
│  3. Brain LLM Reasoning            BrainService (Token Stream)          │
│  4. Text-to-Speech (TTS)           ElevenLabsTTSEngine                  │
│                                    (Fallback: LocalTTSEngine WAV)       │
└────────────────────────────────────┬────────────────────────────────────┘
                                     │ Streamed MP3 / WAV Audio Chunks
┌────────────────────────────────────▼────────────────────────────────────┐
│                      Client Web Audio API Queue                         │
│             (Barge-In: Immediate Interruption & Flush)                  │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## Configuration & Environment

Add your ElevenLabs API credentials to `.env`:

```ini
ELEVENLABS_API_KEY=your_elevenlabs_api_key_here
ELEVENLABS_VOICE_ID=21m00Tcm4TlvDq8ikWAM
```

If `ELEVENLABS_API_KEY` is omitted or empty, Falso automatically falls back to `LocalTTSEngine` (16-bit PCM WAV audio generation) without interrupting user flow or failing API calls.

---

## REST & Streaming API Endpoints

- **`POST /api/v1/voice/tts`**: Synthesize single text response into audio bytes.
- **`POST /api/v1/voice/stream`**: Stream synthesized audio chunks as text tokens arrive.
- **`POST /api/v1/voice/conversation`**: End-to-end full duplex voice turn (`STT -> Memory -> Brain -> ElevenLabs TTS`).

---

## Architecture & Future Extensibility

The voice layer is decoupled from the brain via modular interfaces:

- **`VoiceConfig`**: Configures voice ID, personality, wake word (`Hey Falso`), emotion style (`neutral`, `empathetic`, `excited`), speaking rate, and pitch.
- **`BaseVoiceTransport`**: Abstract transport channel supporting `WebAudioHTTPTransport`, WebRTC streams, WebSockets, and SIP/Phone call gateways.
- **`VoiceProviderRegistry`**: Dynamic registry for adding new STT/TTS vendor engines without touching core routing logic.
