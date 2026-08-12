from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    # FastAPI
    fastapi_host: str = "0.0.0.0"
    fastapi_port: int = 8000
    fastapi_debug: bool = False

    # Logging
    log_level: str = "INFO"

    # AI provider configuration
    ai_provider: str = "nvidia"
    llm_provider: str = ""
    llm_fallback_provider: str = "ollama"
    ai_timeout_seconds: float = Field(default=300.0, gt=0.0)
    ai_max_retries: int = Field(default=3, ge=0)
    # Maximum number of conversation history messages forwarded to the LLM.
    # Older messages beyond this window are dropped to prevent token overflow.
    max_history_messages: int = Field(default=50, ge=1)

    # NVIDIA Nemotron API Configuration
    nvidia_inference_api_key: str = ""
    nvidia_api_key: str = ""
    nvidia_model: str = "nvidia/llama-3.1-nemotron-70b-instruct"
    nvidia_base_url: str = "https://integrate.api.nvidia.com/v1"

    @property
    def effective_ai_provider(self) -> str:
        prov = (self.llm_provider or self.ai_provider or "nvidia").strip().lower()
        return prov

    @property
    def effective_fallback_provider(self) -> str:
        return (self.llm_fallback_provider or "").strip().lower()

    @property
    def effective_nvidia_api_key(self) -> str:
        return (self.nvidia_inference_api_key or self.nvidia_api_key or "").strip()


    # Gemini (default primary AI provider — Google AI Studio / Gemini API)
    # API key from https://aistudio.google.com/app/apikey.
    gemini_api_key: str = ""
    gemini_model: str = "gemini-3.6-flash"
    gemini_base_url: str = "https://generativelanguage.googleapis.com/v1beta"

    # OpenAI (optional provider — used when AI_PROVIDER=openai)
    openai_api_key: str = ""
    openai_model: str = "gpt-4o"
    openai_base_url: str = ""

    # Ollama (optional local provider — used when AI_PROVIDER=ollama)
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "gemma3:4b"

    system_prompt_path: str = "./config/system_prompt.txt"

    # Personality engine
    # Personality used to build the system prompt at request time. Options:
    # default, technician, ultron, jarvis, minimal, friendly. The Personality
    # Engine (app/personality/) is the only producer of the system prompt; it
    # never routes tools, calls the LLM, or manages memory.
    assistant_personality: str = "default"
    # User preferences folded into the generated system prompt.
    user_language: str = "English"
    user_verbosity: str = "concise"

    # Security
    # Optional bearer token required for all /api/* requests. Empty = no token.
    # Clients send it as "Authorization: Bearer <token>" or "X-Falso-Token: <token>".
    api_token: str = ""
    # Cross-origin requests are only accepted from these origins.
    # Same-origin (localhost) requests are always allowed.
    allowed_origins: list[str] = [
        "http://localhost:8000",
        "http://127.0.0.1:8000",
    ]
    # Max request body size in bytes for /api/* requests. Enforced for both
    # declared Content-Length and chunked/streamed bodies (never buffered).
    max_request_bytes: int = 10_000_000

    # GPU monitoring
    # How often the background monitor probes nvidia-smi. GPU stats served by
    # /api/v1/system/stats are cached between refreshes, so the per-request
    # cost of monitoring is zero regardless of the frontend poll rate.
    gpu_refresh_interval_seconds: float = Field(default=5.0, gt=0.0)

    # ElevenLabs Voice Integration
    tts_provider: str = "elevenlabs"
    elevenlabs_api_key: str = ""
    elevenlabs_voice_id: str = "21m00Tcm4TlvDq8ikWAM"
    elevenlabs_model_id: str = "eleven_monolingual_v1"

    # File Tool limits
    file_tool_workspace: str = ""
    max_file_read_bytes: int = 1_000_000
    max_file_write_bytes: int = 5_000_000
    max_search_results: int = 500
    max_list_items: int = 5_000


    # Feature Flags
    enable_spatial_os: bool = True
    enable_gestures: bool = False
    enable_filesystem_indexer: bool = True
    enable_watchdog: bool = True


settings = Settings()
