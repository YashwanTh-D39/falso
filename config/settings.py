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

    # Voice
    stt_model: str = "base"
    tts_voice: str = "alloy"

    # Memory
    chroma_persist_dir: str = "./data/chroma"
    embedding_model: str = "sentence-transformers/all-MiniLM-L6-v2"

    # File Tool
    file_tool_workspace: str = ""

    # Vision
    tesseract_cmd: str = "tesseract"


settings = Settings()
