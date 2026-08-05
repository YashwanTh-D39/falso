"""Provider factory — maps the configured ``AI_PROVIDER`` to a concrete class.

This is the single place to register a new provider. Every other layer depends
only on :class:`BaseAIProvider`, so switching vendors is a config value plus
one entry here.

The factory is deliberately duck-typed: ``settings`` only needs the provider
fields it reads, so tests can hand it a lightweight stand-in object instead of
the full pydantic Settings object.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from typing import Any

from app.providers.base import AIProviderError, BaseAIProvider
from app.providers.gemini import GeminiProvider
from app.providers.ollama import OllamaProvider
from app.providers.openai import OpenAIProvider

logger = logging.getLogger(__name__)


class UnknownProviderError(AIProviderError):
    """Raised when ``AI_PROVIDER`` names a provider that is not registered."""


#: provider name -> factory that maps a settings-like object to an instance.
#: Wrong config fails here at startup, so the server never streams errors.
build = {
    "gemini": lambda s: GeminiProvider(
        model=getattr(s, "gemini_model", "gemini-2.5-flash"),
        api_key=getattr(s, "gemini_api_key", ""),
        base_url=getattr(s, "gemini_base_url", None),
    ),
    "ollama": lambda s: OllamaProvider(
        model=s.ollama_model,
        base_url=s.ollama_base_url,
    ),
    "openai": lambda s: OpenAIProvider(
        model=getattr(s, "openai_model", "gpt-4o"),
        api_key=getattr(s, "openai_api_key", ""),
        base_url=getattr(s, "openai_base_url", None),
    ),
}


def build_provider(settings: Any) -> BaseAIProvider:
    """Instantiate the provider named by ``settings.ai_provider``."""
    name = (getattr(settings, "ai_provider", "gemini") or "gemini").strip().lower() or "gemini"
    factory: Callable[[Any], BaseAIProvider] | None = build.get(name)
    if factory is None:
        raise UnknownProviderError(
            f"Unknown AI provider {name!r}; available: {', '.join(sorted(build))}"
        )
    provider = factory(settings)
    logger.info("AI provider active: %s (model=%s)", provider.name, provider.model)
    return provider