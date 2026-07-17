import json
import logging

import httpx

from config.settings import settings

logger = logging.getLogger(__name__)


class BrainServiceError(Exception):
    pass


class BrainService:
    def __init__(self) -> None:
        self.model = settings.ollama_model
        self.base_url = settings.ollama_base_url

    def validate_prompt(self, prompt: str) -> None:
        if not prompt or not prompt.strip():
            raise BrainServiceError("Prompt cannot be empty")

    async def chat(self, prompt: str):
        logger.info(
            "Streaming chat with model %s, prompt length %d",
            self.model,
            len(prompt),
        )

        async with httpx.AsyncClient(timeout=300) as client:
            async with client.stream(
                "POST",
                f"{self.base_url}/api/generate",
                json={"model": self.model, "prompt": prompt, "stream": True},
            ) as response:
                if response.status_code != 200:
                    error_body = await response.aread()
                    yield json.dumps(
                        {
                            "error": (
                                f"Ollama returned {response.status_code}: "
                                f"{error_body.decode()}"
                            )
                        }
                    ) + "\n"
                    return

                async for line in response.aiter_lines():
                    if line.strip():
                        yield line + "\n"
