from __future__ import annotations

import json
import logging
import time
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.schemas.brain import ChatMessage

# Tool modules self-register with ToolRegistry on import; importing them here
# guarantees every tool is available to chat routing.
import app.tools.file_tool
import app.tools.github_tool
import app.tools.maps_tool
import app.tools.pypi_tool
import app.tools.system_tool
import app.tools.time_tool
import app.tools.weather_tool
import app.tools.web_search_tool  # noqa: F401
from app.personality import (
    ConversationState,
    PersonalityEngine,
    RuntimeContext,
    UserPreferences,
)
from app.providers import AIProviderError, BaseAIProvider, build_provider
from app.services.context import ConversationContext
from app.tools.manager import ToolManager
from app.tools.registry import ToolRegistry
from config.settings import settings

logger = logging.getLogger(__name__)


class BrainServiceError(Exception):
    pass


class BrainService:
    def __init__(
        self,
        personality_engine: PersonalityEngine | None = None,
        provider: BaseAIProvider | None = None,
    ) -> None:
        # AI provider is injected so tests can stub it; production uses the
        # factory, which already resolves `AI_PROVIDER` from settings.
        self.provider = provider or build_provider(settings)
        self.tool_manager = ToolManager()
        self.personality_engine = personality_engine or PersonalityEngine(
            core_prompt=self._load_system_prompt(),
            default_personality=settings.assistant_personality,
            user_preferences=UserPreferences(
                language=settings.user_language,
                verbosity=settings.user_verbosity,
            ),
        )
        self.context = ConversationContext()
        self.last_first_token_latency: float = 0.0
        self.last_tool_latency: float = 0.0
        self.last_memory_latency: float = 0.0

    @property
    def model(self) -> str:
        return self.provider.model

    def _load_system_prompt(self) -> str | None:
        try:
            with open(settings.system_prompt_path, encoding="utf-8") as f:
                content = f.read().strip()
                if content:
                    logger.info("Loaded system prompt from %s", settings.system_prompt_path)
                    return content
                return None
        except FileNotFoundError:
            logger.warning("System prompt file not found at %s", settings.system_prompt_path)
            return None

    def validate_prompt(self, prompt: str) -> None:
        if not prompt or not prompt.strip():
            raise BrainServiceError("Prompt cannot be empty")

    async def _execute_pending(self) -> str:
        action = self.context.pending
        redo_kwargs = dict(action.args)
        redo_kwargs["confirmed"] = True
        result = await self.tool_manager.execute(action.tool, **redo_kwargs)
        tool_cls = ToolRegistry.get(action.tool)
        response = tool_cls.format_result(result) if tool_cls else str(result)
        logger.debug("Pending action executed | tool=%s intent=%s", action.tool, action.intent)
        self.context.clear_pending()

        # Update last_filename from result
        if result.data:
            for key in ("path", "from"):
                val = result.data.get(key)
                if val:
                    self.context.last_filename = val
                    break
        return response

    async def chat(self, prompt: str, *, history: list[ChatMessage] | None = None):
        prompt_stripped = prompt.strip()
        prompt_lower = prompt_stripped.lower()

        logger.info("Chat with model %s, prompt=%r", self.model, prompt_stripped)

        # ── Phase 0: Handle pending action before anything else ──
        if self.context.has_pending:
            action = self.context.pending

            clean = prompt_lower.strip(".,!?;:")
            affirmative_keywords = {"yes", "y", "yeah", "yep", "sure", "ok", "okay",
                                    "do it", "continue", "go ahead", "proceed", "confirm"}
            negative_keywords = {"no", "n", "nope", "cancel", "stop", "never mind", "dont", "don't", "forget it"}

            is_affirmative = (
                clean in affirmative_keywords
                or any(w in clean for w in ("do it", "go ahead"))
            )
            is_negative = (
                clean in negative_keywords
                or any(clean.startswith(w) for w in ("no", "nope", "cancel", "stop"))
                or any(w in clean for w in ("never mind", "forget it"))
            )

            if is_affirmative:
                response_text = await self._execute_pending()
                yield json.dumps({
                    "model": self.model,
                    "response": response_text,
                    "done": True,
                }) + "\n"
                return

            if is_negative:
                logger.debug("Pending action cancelled | tool=%s intent=%s",
                             action.tool, action.intent)
                self.context.clear_pending()
                yield json.dumps({
                    "model": self.model,
                    "response": "Cancelled.",
                    "done": True,
                }) + "\n"
                return

            # Unrelated message — keep pending action alive, fall through to normal routing

        # ── Phase 1: Route to a registered tool ──
        for tool_def in ToolRegistry.list():
            tool_cls = ToolRegistry.get(tool_def["name"])
            if tool_cls is None:
                continue

            kwargs = tool_cls.match_prompt(prompt_stripped, self.context)
            if kwargs is not None:
                logger.debug(
                    "Intent: %s | Selected tool: %s | Params: %s",
                    kwargs.get("command", "?"), tool_cls.name, kwargs,
                )
                yield json.dumps({
                    "type": "tool_start",
                    "tool": tool_cls.name,
                    "action": kwargs.get("command", "execute"),
                    "detail": kwargs.get("path") or kwargs.get("new_name") or "",
                }) + "\n"
                result = await self.tool_manager.execute(tool_cls.name, **kwargs)
                response_text = tool_cls.format_result(result)
                if isinstance(result.data, dict):
                    diagnostic = (
                        result.data.get("message")
                        or result.data.get("error")
                        or response_text[:80]
                    )
                else:
                    diagnostic = response_text[:80]
                logger.debug(
                    "Tool result: success=%s | %s",
                    result.success, diagnostic,
                )

                # ── Store pending action if confirmation is required ──
                if isinstance(result.data, dict) and result.data.get("confirmation_required"):
                    self.context.store_pending(
                        tool=tool_cls.name,
                        intent=kwargs.get("command", "?"),
                        args=kwargs,
                        confirmation_required=True,
                    )
                    logger.debug(
                        "Pending action created | tool=%s intent=%s args=%s",
                        tool_cls.name, kwargs.get("command", "?"), kwargs,
                    )
                else:
                    self.context.clear_pending()

                # Store filename for pronoun resolution
                file_candidates = [
                    result.data.get("path") if isinstance(result.data, dict) else None,
                    result.data.get("from") if isinstance(result.data, dict) else None,
                    kwargs.get("path"),
                    kwargs.get("new_name"),
                ]
                for fc in file_candidates:
                    if fc:
                        self.context.last_filename = fc
                        logger.debug("Context: last_filename=%r", fc)
                        break

                WEB_TOOLS = {"weather", "web_search", "maps", "github", "pypi"}
                if tool_cls.name in WEB_TOOLS and result.success:
                    tool_raw_facts = str(result.data)
                    synthesis_messages = [
                        {
                            "role": "user",
                            "content": (
                                f"User question: {prompt_stripped}\n\n"
                                f"Extracted Live Search Facts:\n{tool_raw_facts}\n\n"
                                "INSTRUCTIONS:\n"
                                "1. Answer the user's question directly in a clean, direct, natural, conversational way (like ChatGPT Voice).\n"
                                "2. DO NOT write or read URLs, http, www, markdown links, or raw JSON in your primary conversational answer.\n"
                                "3. If source URLs or provider names exist, place them ONLY at the very end in a `<details><summary>Sources</summary>...</details>` block so they render as an expandable link in the UI."
                            )
                        }
                    ]

                    logger.info("[WEB INTELLIGENCE] Synthesizing facts into conversational answer via LLM...")
                    async for chunk in self.provider.stream_chat(synthesis_messages):
                        text_content = chunk.text if hasattr(chunk, "text") else (chunk.content if hasattr(chunk, "content") else str(chunk))
                        yield json.dumps({
                            "model": self.model,
                            "response": text_content,
                            "done": False,
                        }) + "\n"

                    yield json.dumps({
                        "model": self.model,
                        "response": "",
                        "done": True,
                    }) + "\n"
                    return

                yield json.dumps({
                    "model": self.model,
                    "response": response_text,
                    "done": True,
                }) + "\n"
                return

        # ── Phase 2: No tool matched — stream from the AI provider ──
        logger.debug("No tool matched → routing to AI provider %s", self.provider.name)
        messages = []
        system_prompt = self.personality_engine.build_prompt(
            runtime_context=RuntimeContext(
                model=self.model,
                capabilities=tuple(t["name"] for t in ToolRegistry.list()),
            ),
            conversation_state=ConversationState(
                last_filename=self.context.last_filename,
                pending_tool=self.context.pending.tool if self.context.pending else None,
                pending_intent=self.context.pending.intent if self.context.pending else None,
            ),
        )
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})

        # ── Sliding-window history truncation ──
        if history:
            max_msgs = settings.max_history_messages
            truncated = history[-max_msgs:] if len(history) > max_msgs else history
            for msg in truncated:
                messages.append({"role": msg.role, "content": msg.content})

        messages.append({"role": "user", "content": prompt_stripped})
        start_time = time.perf_counter()
        first_token_received = False
        try:
            # stream_chat is a provider-agnostic async generator; each vendor
            # maps these OpenAI-style messages to its native request.
            async for chunk in self.provider.stream_chat(messages):
                if chunk.text:
                    if not first_token_received:
                        self.last_first_token_latency = time.perf_counter() - start_time
                        first_token_received = True
                        logger.info("First LLM token received in %.3fs", self.last_first_token_latency)
                    yield json.dumps({
                        "model": self.model,
                        "response": chunk.text,
                        "done": False,
                    }) + "\n"
            # Always terminate with a done line — the UI relies on it, and it
            # keeps the frontend contract identical across every provider.
            yield json.dumps({
                "model": self.model,
                "response": "",
                "done": True,
            }) + "\n"
        except AIProviderError as e:
            # Provider failures are user-safe and should not kill the reply:
            # surface them as an error line inside the stream instead.
            logger.warning("%s provider error: %s", self.provider.name, e)
            err_msg = "Local model unavailable." if self.provider.name == "ollama" else str(e)
            yield json.dumps({"error": err_msg}) + "\n"
        except Exception as e:
            # Keep the stream alive with an error line instead of aborting
            # mid-response with no explanation.
            logger.exception("Unexpected error streaming from provider %s", self.provider.name)
            err_msg = "Local model unavailable." if self.provider.name == "ollama" else f"{self.provider.name} error: {e}"
            yield json.dumps({"error": err_msg}) + "\n"
