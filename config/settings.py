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
    fastapi_debug: bool = True

    # Logging
    log_level: str = "INFO"

    # Ollama
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "qwen2.5:3b"
    system_prompt_path: str = "./config/system_prompt.txt"

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

    # File Tool limits
    file_tool_workspace: str = ""
    max_file_read_bytes: int = 1_000_000
    max_file_write_bytes: int = 5_000_000
    max_search_results: int = 500
    max_list_items: int = 5_000


settings = Settings()
