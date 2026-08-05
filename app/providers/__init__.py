"""AI provider layer — pluggable chat backends.

The rest of the app depends only on three symbols: :class:`BaseAIProvider`,
:class:`AIProviderError`, and :func:`build_provider`. Adding a new vendor
(Claude, DeepSeek, ...) is a new class in this package plus one entry in
:data:`factory.build` — nothing in the services, routes, config, or UI
changes.
"""

from app.providers.base import AIProviderError, BaseAIProvider, ProviderChunk
from app.providers.factory import UnknownProviderError, build_provider

__all__ = [
    "AIProviderError",
    "BaseAIProvider",
    "ProviderChunk",
    "UnknownProviderError",
    "build_provider",
]