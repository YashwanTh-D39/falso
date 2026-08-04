import json
import logging

import httpx

# Tool modules self-register with ToolRegistry on import; importing them here
# guarantees every tool is available to chat routing.
import app.tools.file_tool
import app.tools.system_tool
import app.tools.time_tool  # noqa: F401 — registers TimeTool
from app.services.context import ConversationContext
from app.tools.manager import ToolManager
from app.tools.registry import ToolRegistry
from config.settings import settings

logger = logging.getLogger(__name__)


class BrainServiceError(Exception):
    pass


class BrainService:
    def __init__(self) -> None:
        self.model = settings.ollama_model
        self.base_url = settings.ollama_base_url
        self.tool_manager = ToolManager()
        self.system_prompt = self._load_system_prompt()
        self.context = ConversationContext()

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

    async def chat(self, prompt: str):
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
                diagnostic = (
                    result.data.get("message")
                    or result.data.get("error")
                    or response_text[:80]
                ) if result.data else response_text[:80]
                logger.debug(
                    "Tool result: success=%s | %s",
                    result.success, diagnostic,
                )

                # ── Store pending action if confirmation is required ──
                if result.data and result.data.get("confirmation_required"):
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
                    result.data.get("path") if result.data else None,
                    result.data.get("from") if result.data else None,
                    kwargs.get("path"),
                    kwargs.get("new_name"),
                ]
                for fc in file_candidates:
                    if fc:
                        self.context.last_filename = fc
                        logger.debug("Context: last_filename=%r", fc)
                        break

                yield json.dumps({
                    "model": self.model,
                    "response": response_text,
                    "done": True,
                }) + "\n"
                return

        # ── Phase 2: No tool matched — stream from the LLM ──
        logger.debug("No tool matched → routing to LLM")
        messages = []
        if self.system_prompt:
            messages.append({"role": "system", "content": self.system_prompt})
        messages.append({"role": "user", "content": prompt_stripped})
        try:
            async with httpx.AsyncClient(timeout=300) as client, client.stream(
                "POST",
                f"{self.base_url}/api/chat",
                json={"model": self.model, "messages": messages, "stream": True},
            ) as resp:
                if resp.status_code != 200:
                    error_body = await resp.aread()
                    yield json.dumps({"error": f"Ollama error: {error_body.decode()}"}) + "\n"
                    return

                async for line in resp.aiter_lines():
                    if not line.strip():
                        continue
                    try:
                        data = json.loads(line)
                    except (json.JSONDecodeError, ValueError):
                        # A single malformed line must never kill the whole
                        # stream (proxy corruption, mid-line flush, etc.).
                        logger.debug("Skipping malformed Ollama line: %r", line[:200])
                        continue
                    if not isinstance(data, dict):
                        logger.debug("Skipping non-object Ollama line: %r", line[:200])
                        continue
                    yield json.dumps({
                        "model": data.get("model"),
                        "response": data.get("message", {}).get("content", ""),
                        "done": data.get("done", False),
                    }) + "\n"
        except httpx.RequestError as e:
            logger.warning("Ollama connection failed: %s", e)
            yield json.dumps({"error": f"Ollama connection failed: {e}"}) + "\n"
        except Exception as e:
            # Keep the stream alive with an error line instead of aborting
            # mid-response with no explanation.
            logger.exception("Unexpected error streaming from Ollama")
            yield json.dumps({"error": f"Ollama error: {e}"}) + "\n"
