from __future__ import annotations

import asyncio
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


def _sanitize_history(history: list[ChatMessage] | None) -> list[ChatMessage]:
    if not history:
        return []
    banned_substrings = [
        "simulated voice output",
        "voice activation",
        "warm, friendly voice",
        "actual voice output",
        "stylized text form",
        "voice simulation",
    ]
    sanitized: list[ChatMessage] = []
    for msg in history:
        content = getattr(msg, "content", "") or ""
        lower_content = content.lower()
        if any(b in lower_content for b in banned_substrings):
            lines = [line for line in content.splitlines() if not any(b in line.lower() for b in banned_substrings)]
            cleaned = "\n".join(lines).strip()
            if cleaned:
                from app.schemas.brain import ChatMessage
                sanitized.append(ChatMessage(role=msg.role, content=cleaned))
        else:
            sanitized.append(msg)
    return sanitized


class BrainServiceError(Exception):
    pass


class BrainService:
    def __init__(
        self,
        personality_engine: PersonalityEngine | None = None,
        provider: BaseAIProvider | None = None,
    ) -> None:
        # AI provider is injected so tests can stub it; production uses the
        # factory, which resolves `LLM_PROVIDER` / `AI_PROVIDER` from settings.
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

    async def chat(self, prompt: str, *, history: list[ChatMessage] | None = None, request_id: str | None = None):
        t_start = time.perf_counter()
        req_id = request_id or f"FALSO-{time.strftime('%Y%m%d')}-{int(time.perf_counter()*10000) % 10000:04d}"
        history = _sanitize_history(history)
        prompt_stripped = prompt.strip()
        prompt_lower = prompt_stripped.lower()

        logger.info("[CHAT][%s] REQUEST_START | prompt=%r", req_id, prompt_stripped)
        logger.info("[LATENCY] BACKEND_RECEIVED | req_id=%s | prompt=%r", req_id, prompt_stripped)

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

        # ── Fast-path Intent Classification for Simple Questions & Casual Chat ──
        casual_triggers = (
            "hello", "hi", "hey", "hello again", "howdy", "greetings", "good morning",
            "good afternoon", "good evening", "how are you", "who are you",
            "what can you do", "what's up", "whats up", "tell me a joke",
            "what is 2+2", "2+2", "who made you", "who created you",
            "say hello", "say hello by voice", "say hi", "speak to me", "talk to me"
        )
        clean_prompt = prompt_lower.strip(".,!?;: ")
        is_casual = (
            clean_prompt in casual_triggers
            or (len(clean_prompt) < 20 and any(clean_prompt.startswith(g) for g in ("hello", "hi", "hey", "good morning", "good evening", "tell me a joke", "what is 2+2", "say hello", "say hi")))
        )

        if not is_casual:
            # ── Phase 1: Route to a registered tool if prompt matches tool intent ──
            for tool_def in ToolRegistry.list():
                tool_cls = ToolRegistry.get(tool_def["name"])
                if tool_cls is None:
                    continue

                kwargs = tool_cls.match_prompt(prompt_stripped, self.context)
                if kwargs is not None:
                    logger.info("[LATENCY] tool_matched | tool=%s | t=%.3fs", tool_cls.name, time.perf_counter() - t_start)
                    yield json.dumps({
                        "type": "tool_start",
                        "tool": tool_cls.name,
                        "action": kwargs.get("command", "execute"),
                        "detail": kwargs.get("path") or kwargs.get("new_name") or "",
                    }) + "\n"
                    result = await self.tool_manager.execute(tool_cls.name, **kwargs)
                    response_text = tool_cls.format_result(result)

                    # Store pending action if confirmation is required
                    if isinstance(result.data, dict) and result.data.get("confirmation_required"):
                        self.context.store_pending(
                            tool=tool_cls.name,
                            intent=kwargs.get("command", "?"),
                            args=kwargs,
                            confirmation_required=True,
                        )
                    else:
                        self.context.clear_pending()

                    WEB_TOOLS = {"weather", "web_search", "maps", "github", "pypi"}
                    if tool_cls.name in WEB_TOOLS and result.success:
                        logger.info("[WEB] Searching")
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

        # ── Phase 2: Simple Chat or LLM Completion Stream with Fallback ──
        active_provider = self.provider
        fallback_name = settings.effective_fallback_provider
        key_configured = bool(settings.effective_nvidia_api_key)

        logger.info(
            "\n[CHAT DEBUG]\n"
            "provider=%s\n"
            "model=%s\n"
            "fallback=%s\n"
            "nvidia_key_configured=%s\n"
            "nvidia_request_started=True\n"
            "nvidia_status=Attempting streaming request...\n"
            "first_token_ms=0.00\n"
            "fallback_triggered=False",
            active_provider.name,
            active_provider.model,
            fallback_name,
            key_configured,
        )

        logger.info("[LATENCY] LLM_STREAM_START | provider=%s | prompt=%r", active_provider.name, prompt_stripped)
        messages = []
        stream_kwargs = {}
        if is_casual:
            system_prompt = (
                "You are FALSO, a concise AI assistant. Respond to greetings and casual prompts with a brief, "
                "friendly 1-sentence message. Output standard plain text only. NEVER write disclaimers, labels, "
                "brackets, or meta-text about voice synthesis (such as 'Simulated Voice Output' or 'Voice Activation')."
            )
            messages.append({"role": "system", "content": system_prompt})
            stream_kwargs["max_tokens"] = 48
            if history:
                truncated = history[-4:]
                for msg in truncated:
                    messages.append({"role": msg.role, "content": msg.content})
        else:
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
            if history:
                max_msgs = settings.max_history_messages
                truncated = history[-max_msgs:] if len(history) > max_msgs else history
                for msg in truncated:
                    messages.append({"role": msg.role, "content": msg.content})

        messages.append({"role": "user", "content": prompt_stripped})
        first_token_received = False
        first_token_latency_ms = 0.0

        try:
            backend_chunk_index = 0
            warming_sent = False

            # Cold-start UX: emit a 'warming' status event if NVIDIA
            # hasn't produced the first token after 3 seconds.  We use an
            # asyncio.Queue so the SSE generator can yield the warming
            # event *while* still waiting for the provider stream.
            chunk_queue: asyncio.Queue = asyncio.Queue()
            warming_delay_s = 3.0

            async def _provider_reader():
                """Read chunks from the provider and push them to the queue."""
                try:
                    async for chunk in active_provider.stream_chat(messages, **stream_kwargs):
                        await chunk_queue.put(("chunk", chunk))
                    await chunk_queue.put(("done", None))
                except Exception as exc:
                    await chunk_queue.put(("error", exc))

            async def _warming_timer():
                """After warming_delay_s seconds, push a warming signal."""
                await asyncio.sleep(warming_delay_s)
                await chunk_queue.put(("warming", None))

            reader_task = asyncio.create_task(_provider_reader())
            timer_task = asyncio.create_task(_warming_timer())

            try:
                while True:
                    event_type, event_data = await chunk_queue.get()

                    if event_type == "warming":
                        if not first_token_received and not warming_sent:
                            warming_sent = True
                            elapsed_ms = (time.perf_counter() - t_start) * 1000.0
                            logger.warning(
                                "[NVIDIA] COLD_START_UX | warming status sent to frontend | elapsed=%.0fms",
                                elapsed_ms,
                            )
                            yield json.dumps({
                                "request_id": req_id,
                                "source": "system",
                                "type": "status",
                                "status": "warming",
                                "message": "NVIDIA warming...",
                                "done": False,
                            }) + "\n"
                        continue

                    if event_type == "done":
                        break

                    if event_type == "error":
                        raise event_data

                    # event_type == "chunk"
                    chunk = event_data
                    if chunk.text:
                        t_chunk_received = time.perf_counter()
                        prov_elapsed_ms = (t_chunk_received - t_start) * 1000.0
                        if not first_token_received:
                            first_token_latency_ms = prov_elapsed_ms
                            self.last_first_token_latency = first_token_latency_ms / 1000.0
                            first_token_received = True
                            logger.info("[LATENCY] BACKEND_FIRST_TOKEN | t=%.2fms", first_token_latency_ms)
                            # Cancel the warming timer — no longer needed
                            timer_task.cancel()

                        backend_chunk_index += 1
                        payload_line = json.dumps({
                            "request_id": req_id,
                            "source": "llm",
                            "type": "chunk",
                            "model": active_provider.model,
                            "response": chunk.text,
                            "done": False,
                        }) + "\n"
                        yield_elapsed_ms = (time.perf_counter() - t_start) * 1000.0
                        fwd_delay_ms = yield_elapsed_ms - prov_elapsed_ms
                        logger.info(
                            "[BACKEND_STREAM][%s] chunk=%d provider_elapsed=%.2fms yield_elapsed=%.2fms fwd_delay=%.3fms",
                            req_id,
                            backend_chunk_index,
                            prov_elapsed_ms,
                            yield_elapsed_ms,
                            fwd_delay_ms,
                        )
                        yield payload_line
            finally:
                timer_task.cancel()
                # Ensure reader finishes cleanly
                if not reader_task.done():
                    try:
                        await reader_task
                    except Exception:
                        pass

            total_duration_ms = (time.perf_counter() - t_start) * 1000.0
            logger.info("[LATENCY][%s] RESPONSE_COMPLETE | total=%.2fms", req_id, total_duration_ms)
            logger.info(
                "\n[CHAT DEBUG SUMMARY]\n"
                "provider=%s\n"
                "model=%s\n"
                "fallback=%s\n"
                "nvidia_key_configured=%s\n"
                "nvidia_request_started=True\n"
                "nvidia_status=200 OK\n"
                "first_token_ms=%.2f\n"
                "fallback_triggered=False",
                active_provider.name,
                active_provider.model,
                fallback_name,
                key_configured,
                first_token_latency_ms,
            )
            yield json.dumps({
                "request_id": req_id,
                "source": "llm",
                "type": "done",
                "model": active_provider.model,
                "response": "",
                "done": True,
            }) + "\n"

        except (AIProviderError, Exception) as primary_exc:
            err_reason = str(primary_exc)
            logger.error(
                "\n[CHAT DEBUG FAILURE]\n"
                "provider=%s\n"
                "model=%s\n"
                "fallback=%s\n"
                "nvidia_key_configured=%s\n"
                "nvidia_request_started=True\n"
                "nvidia_status=FAILED (%s)\n"
                "first_token_ms=0.00\n"
                "fallback_triggered=%s",
                active_provider.name,
                active_provider.model,
                fallback_name,
                key_configured,
                err_reason,
                bool(fallback_name and fallback_name != active_provider.name),
            )
            # If primary provider fails and a fallback provider is configured
            if fallback_name and fallback_name != active_provider.name:
                logger.warning(
                    "[FALLBACK] Primary AI provider '%s' failed (%s). Falling back to '%s'...",
                    active_provider.name,
                    primary_exc,
                    fallback_name,
                )
                try:
                    fallback_provider = build_provider(settings, provider_name=fallback_name)
                    async for chunk in fallback_provider.stream_chat(messages):
                        if chunk.text:
                            if not first_token_received:
                                first_token_latency_ms = (time.perf_counter() - t_start) * 1000.0
                                self.last_first_token_latency = first_token_latency_ms / 1000.0
                                first_token_received = True
                                logger.info(
                                    "[LATENCY] BACKEND_FIRST_TOKEN (via fallback %s) | t=%.2fms",
                                    fallback_name,
                                    first_token_latency_ms,
                                )
                            yield json.dumps({
                                "model": fallback_provider.model,
                                "response": chunk.text,
                                "done": False,
                            }) + "\n"

                    total_duration_ms = (time.perf_counter() - t_start) * 1000.0
                    logger.info(
                        "[LATENCY] RESPONSE_COMPLETE (via fallback %s) | total=%.2fms",
                        fallback_name,
                        total_duration_ms,
                    )
                    yield json.dumps({
                        "model": fallback_provider.model,
                        "response": "",
                        "done": True,
                    }) + "\n"
                    return
                except Exception as fallback_exc:
                    logger.error(
                        "[FALLBACK] Fallback AI provider '%s' also failed: %s",
                        fallback_name,
                        fallback_exc,
                    )
                    err_msg = str(primary_exc) if isinstance(primary_exc, AIProviderError) else f"{active_provider.name} error: {primary_exc}"
                    yield json.dumps({"error": err_msg}) + "\n"
                    return

            logger.warning("%s provider error: %s", active_provider.name, primary_exc)
            err_msg = "Local model unavailable." if active_provider.name == "ollama" else (
                str(primary_exc) if isinstance(primary_exc, AIProviderError) else f"{active_provider.name} error: {primary_exc}"
            )
            yield json.dumps({"error": err_msg}) + "\n"
