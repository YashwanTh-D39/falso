"""AI provider abstraction.

The Brain service (app/services/brain.py) never talks to a specific vendor:
it calls :meth:`BaseAIProvider.stream_chat` with an OpenAI-style message list
and receives text chunks back. Concrete providers (OpenAI, Ollama, ...)
translate between this neutral contract and their vendor API, so switching
vendors never touches the service, route, config, or UI layers.

Adding a new provider (Claude, DeepSeek, ...) means:

1. subclass :class:`BaseAIProvider`,
2. add one entry to the factory in ``app/providers/factory.py``,
3. set ``AI_PROVIDER=<name>`` in ``.env``.

No other file in the project changes.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import AsyncIterator
from dataclasses import dataclass


class AIProviderError(Exception):
    """A user-safe, provider-specific failure.

    Raised by providers when the vendor is unreachable or rejects the
    request. The message may be shipped straight into the chat stream, so it
    must never contain secrets (API keys, tokens, full URLs with secrets).
    """


@dataclass
class ProviderChunk:
    """A piece of assistant text produced by a provider.

    ``done`` is informational (some upstreams signal end of stream). The
    Brain service always terminates its own stream with a final ``done: true``
    line regardless of provider, so the UI contract is stable across vendors.
    """

    text: str = ""
    done: bool = False


class BaseAIProvider(ABC):
    """Common contract that every AI provider must implement.

    The message list uses the neutral OpenAI-style shape::

        [{"role": "system" | "user" | "assistant", "content": str}, ...]

    Each provider maps it to its native request format. Providers must:

    - raise :class:`AIProviderError` with a user-safe message on any failure
      (network error, non-200 status, missing config);
    - stream text incrementally instead of buffering the whole reply;
    - never log or echo credentials.
    """

    #: Provider identifier used in logs/errors ("openai", "ollama", ...).
    name: str

    #: Model identifier reported to the UI (e.g. "gpt-5").
    model: str

    @abstractmethod
    def stream_chat(self, messages: list[dict]) -> AsyncIterator[ProviderChunk]:
        """Stream a chat completion for ``messages``, yielding text chunks."""