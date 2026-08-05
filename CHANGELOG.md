# CHANGELOG — Falso

All notable changes to the Falso project are documented in this file.

## [0.2.0] — 2026-08-06

### Added

#### Roadmap Subsystems (Phase 3)
- **Memory Subsystem** (`memory/`):
  - `BaseMemoryStore` abstract contract and `MemoryEntry` / `MemorySearchResult` dataclasses.
  - `JSONMemoryStore`: Zero-dependency, thread-safe, persistent JSON memory store with TF-IDF search scoring.
  - `ChromaMemoryStore`: High-performance vector database memory store powered by ChromaDB.
  - `MemoryService`: Auto-detecting manager that selects ChromaDB when available, gracefully falling back to JSONMemoryStore.
- **Automation Subsystem** (`automation/`):
  - `AutomationJob` and `JobResult` dataclasses for background task specification.
  - `AutomationScheduler`: Non-blocking async loop scheduler for executing one-off or interval-based recurring tasks.
  - `AutomationEngine`: High-level engine for task scheduling, listing, immediate execution, and cancellation.
- **Multi-Agent Subsystem** (`agents/`):
  - `BaseSubAgent` interface and `AgentResult` model.
  - `AgentRegistry`: Decorator-based class registry for sub-agent discovery.
  - `AgentOrchestrator`: Asynchronous orchestrator capable of spawning sub-agents and running multi-agent tasks concurrently.
  - Built-in sub-agents: `ResearchAgent`, `CoderAgent`, and `AnalystAgent`.
- **Voice I/O Subsystem** (`voice/`):
  - `AudioBuffer`, `STTResult`, `TTSResult`, `BaseSTTEngine`, `BaseTTSEngine`.
  - `LocalSTTEngine`: Signal energy and duration analyzer for speech input transcription.
  - `LocalTTSEngine`: Synthesizes PCM WAV audio headers and speech frames.
  - `VoiceService`: Unified voice input and output manager.
- **Vision / OCR Subsystem** (`vision/`):
  - `ImageFrame`, `VisionResult`, `BaseVisionEngine`.
  - `LocalVisionEngine`: Pure-Python header parsing (PNG, GIF, JPEG) with automatic PIL and pytesseract fallback.
  - `VisionService`: High-level manager for image analysis and text extraction.

#### Features & Hardening (Phase 1 & Phase 2)
- **Conversation History & Truncation**:
  - `ChatMessage` Pydantic model for typed, validated history turns.
  - Sliding-window history truncation in `BrainService` controlled by `settings.max_history_messages` (default 50).
- **Settings & Config**:
  - Added `ai_timeout_seconds` (default 300.0s), `ai_max_retries` (default 3), and `max_history_messages` (default 50) to `Settings`.
  - Set default `fastapi_debug` to `False` for production security.
- **Docker Hardening**:
  - Non-root container user (`falso`) with proper directory permissions for `/app/chats` and `/app/logs`.
  - Container `HEALTHCHECK` probing `http://localhost:8000/health`.
  - Added `.dockerignore` to optimize build context and cache efficiency.
  - Hardened `docker-compose.yml` with `restart: unless-stopped`, persistent `chats/` volume, and healthchecks.
- **API Enhancements**:
  - Conversation listing endpoint supports pagination via `page` and `per_page` query params while preserving array response compatibility.

### Fixed
- Fixed misplaced optional dependency groups (`voice`, `memory`, `vision`) in `pyproject.toml` so `pip install falso[memory]` works as expected.
- Added 30-second execution timeout in `ToolManager` to prevent long operations from starving thread executors.
- Hardened `FileTool` sandbox by rejecting symlink resolution attempts.
- Optimized GPU background sampling in `SystemMonitor` by probing for NVIDIA GPUs once at startup and skipping `nvidia-smi` subprocess execution on non-NVIDIA hosts.
- Fixed resource lifecycle management: explicit `aclose()` for `OllamaProvider` clients and clean app lifespan shutdown.
- Configured `logging.basicConfig(force=True)` to guarantee logging format is applied.

### Security
- Set `fastapi_debug: False` by default.
- Added non-root user execution in Docker container.
- Closed symlink resolution vector in file tool sandbox.

---

## [0.1.0] — Initial Release
- Core FastAPI server, OpenAI Responses API & Ollama providers, tool execution, single-page web UI.
