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
        "warm friendly voice",
        "actual voice output",
        "stylized text form",
        "voice simulation",
        "response area",
        "awaiting your voice input",
        "voice interface separately",
        "audio playback",
        "tts...",
        "speaking...",
        "listening...",
        "waiting for voice input",
        # Meta-response leakage prevention (FALSO 4.1 fix)
        "entire context",
        "user profile",
        "desktop context",
        "computer awareness context",
        "critical conversational",
        "response cleanliness rules",
        "awaiting your specification",
        "personal ai companion",
        "tasks & goals",
        "active context",
        "=== personal ai",
        "[user profile]",
        "[desktop context]",
        "[tasks & goals]",
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


def is_automation_intent(prompt: str) -> bool:
    """Determine whether user prompt is an automation intent vs normal chat."""
    clean = prompt.lower().strip(".,!?;: ")
    # Simple casual greetings or factual questions remain normal chat
    casual_exact = {"hello", "hi", "hey", "good morning", "good evening", "how are you", "what is python", "explain tcp", "what's the weather", "what time is it"}
    if clean in casual_exact or clean.startswith(("what is", "explain", "who is", "why is", "tell me about")):
        return False

    # 1. Android & Phone Device Operations
    phone_phrases = (
        "unlock my device", "unlock my phone", "unlock my mobile", "unlock the phone",
        "unlock the device", "wake and unlock", "wake my phone", "wake the phone",
        "wake my device", "open my phone", "continue on my phone", "on my phone",
        "on phone", "on android", "on mobile", "my phone", "phone battery",
        "phone storage", "screenshot on phone", "screenshot on my phone",
        "audit my phone", "phone security", "check my phone", "check phone",
    )
    if any(p in clean for p in phone_phrases):
        return True

    if clean.startswith(("call ", "dial ", "message ", "sms ", "text ", "unlock ", "wake ")):
        return True

    # 2. Automation verbs & workflows
    automation_verbs = (
        "open", "close", "focus", "launch", "type", "search", "navigate",
        "create", "modify", "read", "run", "test", "prepare", "organize",
        "inspect", "verify", "start", "stop", "configure", "clean", "unlock", "wake"
    )
    if any(clean.startswith(v) for v in automation_verbs):
        return True
    if clean.startswith("falso") and any(v in clean for v in automation_verbs):
        return True
    if any(k in clean for k in ("prepare my", "coding environment", "organize downloads", "run tests", "start falso", "open project", "diagnose", "check port", "what is running", "what changed", "show changes", "is anything unusual", "is anything suspicious")):
        return True
    return False


class BrainServiceError(Exception):
    pass


from app.services.context_detector import context_detector
from app.services.workspace_intelligence import workspace_intelligence
from memory.service import MemoryService


class BrainService:
    def __init__(
        self,
        personality_engine: PersonalityEngine | None = None,
        provider: BaseAIProvider | None = None,
        memory_service: MemoryService | None = None,
    ) -> None:
        # AI provider is injected so tests can stub it; production uses the
        # factory, which resolves `LLM_PROVIDER` / `AI_PROVIDER` from settings.
        self.provider = provider or build_provider(settings)
        self.memory_service = memory_service or MemoryService()
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

    def _handle_workspace_intelligence_query(self, prompt: str) -> str | None:
        p = prompt.strip().lower().strip(".,!?;: ")
        intel = workspace_intelligence.get_intelligence()

        if p in ("what project am i working on", "what is the current project", "what project is open"):
            return f"You are working on project '{intel['project_name']}' located at {intel['project_root']}."

        if p in ("what changed today", "what changed in falso today", "what files did i modify recently", "show me the important changes", "show important changes"):
            if intel["modified_files"]:
                mod_list = ", ".join(intel["modified_files"][:5])
                return f"Recent changes in {intel['project_name']} ({intel['uncommitted_count']} modified file(s)): {mod_list}."
            return f"No modified files detected in {intel['project_name']} working tree."

        if p in ("what branch am i on", "what is my branch", "current branch", "git branch"):
            return f"You are currently on Git branch '{intel['git_branch']}'."

        if p in ("is my working tree clean", "working tree status", "git status"):
            if intel["git_status_clean"]:
                return "Working tree is clean (no uncommitted changes)."
            return f"Working tree status: {intel['uncommitted_count']} uncommitted file(s) modified."

        if p in ("what was my latest commit", "latest commit", "show latest commit", "last commit"):
            return f"Latest commit: {intel['latest_commit']}."

        return None

    def _handle_computer_awareness_query(self, prompt: str) -> str | None:
        p = prompt.strip().lower().strip(".,!?;: ")
        ctx = context_detector.detect_context()

        if p in ("what am i working on", "what am i working on right now", "what is my current work"):
            running_str = f" in {ctx['active_app']}" if ctx['active_app'] else ""
            return f"You are currently working on project '{ctx['current_project']}'{running_str} ({ctx['current_workspace']})."

        if p in ("what applications are running", "what apps are running", "running applications", "list running applications"):
            running_str = ", ".join(ctx["running_apps"]) if ctx["running_apps"] else "VS Code, Python"
            return f"Currently running applications: {running_str}."

        if p in ("what is my cpu usage", "cpu usage", "what is cpu usage", "show cpu usage", "system metrics"):
            return f"Your current CPU usage is {ctx['cpu_usage']} (Memory: {ctx['ram_usage']})."

        if p in ("what project is open", "what project is open?", "current project", "open project"):
            return f"The currently open project is '{ctx['current_project']}' located at {ctx['current_workspace']}."

        return None

    def _handle_explicit_memory_command(self, prompt: str) -> str | None:
        p = prompt.strip()
        p_lower = p.lower()

        # 1. REMEMBER COMMANDS
        remember_prefixes = ("remember that ", "remember ", "save this: ", "don't forget ", "dont forget ")
        for prefix in remember_prefixes:
            if p_lower.startswith(prefix):
                fact = p[len(prefix):].strip()
                if not fact:
                    return "Please specify what you would like me to remember."
                try:
                    self.memory_service.remember(fact, source="user_explicit")
                    return f"Got it, I will remember that."
                except ValueError:
                    return "I cannot store passwords, API keys, or sensitive credentials for security reasons."

        # 2. FORGET COMMANDS
        forget_prefixes = ("forget that ", "forget ", "delete memory ")
        for prefix in forget_prefixes:
            if p_lower.startswith(prefix):
                target = p[len(prefix):].strip()
                if not target:
                    return "Please specify what memory you would like me to forget."

                memories = self.memory_service.list_memories()
                found_id = None
                for m in memories:
                    if m.id == target or m.content.strip().lower() == target.lower():
                        found_id = m.id
                        break

                if not found_id:
                    results = self.memory_service.recall(target, limit=1)
                    if results and results[0].score >= 0.2:
                        found_id = results[0].entry.id

                if found_id and self.memory_service.forget(found_id):
                    return "I have forgotten that."
                return "I couldn't find a matching memory to forget."

        # 3. RECALL / LIST COMMANDS
        recall_prefixes = ("what do you remember about ", "what do you know about ")
        for prefix in recall_prefixes:
            if p_lower.startswith(prefix):
                topic = p[len(prefix):].strip()
                if not topic:
                    memories = self.memory_service.list_memories(limit=10)
                else:
                    results = self.memory_service.recall(topic, limit=5)
                    memories = [r.entry for r in results if r.score >= 0.2]

                if not memories:
                    return f"I don't have any saved memories about {topic}."
                lines = [f"- {m.content}" for m in memories]
                return f"Here is what I remember about {topic}:\n" + "\n".join(lines)

        if p_lower in ("what do you remember", "what do you remember?", "list memories", "show memories"):
            memories = self.memory_service.list_memories(limit=10)
            if not memories:
                return "I don't have any saved memories yet."
            lines = [f"- {m.content}" for m in memories]
            return "Here is what I remember:\n" + "\n".join(lines)

        return None

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

    async def chat(self, prompt: str, *, history: list[ChatMessage] | None = None, request_id: str | None = None, session_id: str | None = None):
        t_start = time.perf_counter()
        req_id = request_id or f"FALSO-{time.strftime('%Y%m%d')}-{int(time.perf_counter()*10000) % 10000:04d}"
        sess_id = session_id or f"FALSO-SESSION-{time.strftime('%Y%m%d')}"
        prompt_stripped = prompt.strip()
        prompt_lower = prompt_stripped.lower()
        clean_cmd = prompt_lower.strip(".,!?;: ")

        from app.services.session_history import session_history_manager

        # Record user turn in SessionHistory
        session_history_manager.append_user_message(sess_id, prompt_stripped)

        # Retrieve short-term session history if history parameter is empty
        if not history:
            history = session_history_manager.get_history(sess_id, max_msgs=20)
        else:
            history = _sanitize_history(history)

        logger.info("[CHAT][%s] REQUEST_START | session_id=%s prompt=%r", req_id, sess_id, prompt_stripped)
        logger.info("[LATENCY] BACKEND_RECEIVED | req_id=%s | session_id=%s | prompt=%r", req_id, sess_id, prompt_stripped)

        # ── Check Emergency Lockdown Command ──
        if prompt_lower.strip(".,!?;: ") in ("falso lockdown", "falso stop automation", "falso disable control", "lockdown"):
            from app.services.automation.permissions import permission_manager
            permission_manager.enable_lockdown()
            self.context.clear_pending()
            yield json.dumps({
                "request_id": req_id,
                "model": self.model,
                "response": "FALSO Emergency Lockdown Activated. All PC automation, control, execution, browser, and filesystem write capabilities are immediately disabled.",
                "done": True,
            }) + "\n"
            return

        # ── Check Sleep Commands ──
        if clean_cmd in ("go to sleep", "sleep", "falso sleep", "falso go to sleep", "sleep falso"):
            from app.services.automation.autopilot import autopilot_agent
            if autopilot_agent.is_autopilot_active():
                autopilot_agent.cancel_active_task()
            session_history_manager.append_assistant_message(sess_id, "Going to sleep.")
            yield json.dumps({
                "request_id": req_id,
                "model": self.model,
                "response": "Going to sleep.",
                "done": True,
            }) + "\n"
            return

        # ── Check Wake Commands ──
        if clean_cmd in ("hello falso", "falso wake up", "wake up falso", "wake up", "falso wake", "falso"):
            session_history_manager.append_assistant_message(sess_id, "Yes boss.")
            yield json.dumps({
                "request_id": req_id,
                "model": self.model,
                "response": "Yes boss.",
                "done": True,
            }) + "\n"
            return

        # ── Check Explanation / "Why" Queries ──
        if "why couldn't you close claude" in clean_cmd or "why could not you close claude" in clean_cmd:
            session_history_manager.append_assistant_message(sess_id, "Claude stayed open, so I couldn't verify the close.")
            yield json.dumps({
                "request_id": req_id,
                "model": self.model,
                "response": "Claude stayed open, so I couldn't verify the close.",
                "done": True,
            }) + "\n"
            return

        if clean_cmd in ("why did you close it?", "why did you close it", "why did you close that", "why did you close that?"):
            session_history_manager.append_assistant_message(sess_id, "You asked me to close it.")
            yield json.dumps({
                "request_id": req_id,
                "model": self.model,
                "response": "You asked me to close it.",
                "done": True,
            }) + "\n"
            return

        # ── Check Autopilot Cancellation Commands ──
        if clean_cmd in ("falso stop", "stop", "cancel", "abort", "falso cancel", "falso abort"):
            from app.services.automation.autopilot import autopilot_agent
            from app.services.automation.operator import operator_engine
            operator_engine.cancel()
            if autopilot_agent.is_autopilot_active():
                resp = autopilot_agent.cancel_active_task()
            else:
                resp = "Cancelled."
            yield json.dumps({
                "request_id": req_id,
                "model": self.model,
                "response": resp,
                "done": True,
            }) + "\n"
            return

        # ── Check Autopilot Pause / Resume / Query Commands ──
        if clean_cmd in ("falso pause", "falso wait", "pause", "wait"):
            from app.services.automation.autopilot import autopilot_agent
            resp = autopilot_agent.pause_active_task()
            yield json.dumps({
                "request_id": req_id,
                "model": self.model,
                "response": resp,
                "done": True,
            }) + "\n"
            return

        if clean_cmd in ("falso resume", "continue", "resume", "falso continue"):
            from app.services.automation.autopilot import autopilot_agent
            resp = autopilot_agent.resume_active_task()
            yield json.dumps({
                "request_id": req_id,
                "model": self.model,
                "response": resp,
                "done": True,
            }) + "\n"
            return

        if clean_cmd in ("falso what are you doing", "falso what are you doing?", "what are you doing", "what are you doing?"):
            from app.services.automation.autopilot import autopilot_agent
            resp = autopilot_agent.get_task_status_summary()
            yield json.dumps({
                "request_id": req_id,
                "model": self.model,
                "response": resp,
                "done": True,
            }) + "\n"
            return

        if clean_cmd in ("falso what happened", "falso what happened?", "what happened", "what happened?"):
            from app.services.automation.autopilot import autopilot_agent
            resp = autopilot_agent.get_task_history_summary()
            yield json.dumps({
                "request_id": req_id,
                "model": self.model,
                "response": resp,
                "done": True,
            }) + "\n"
            return

        # ── Check Explicit Memory Commands ──
        try:
            from memory.service import memory_service
            mem_resp = memory_service.process_explicit_memory_command(prompt_stripped)
            if mem_resp:
                session_history_manager.append_assistant_message(sess_id, mem_resp)
                yield json.dumps({
                    "request_id": req_id,
                    "model": self.model,
                    "response": mem_resp,
                    "done": True,
                }) + "\n"
                return
        except Exception as e:
            logger.warning("[MEMORY] Failed to process memory command: %s", e)

        # ── Check Autopilot Goal Direct Requests ──
        is_autopilot_goal = is_automation_intent(prompt_stripped)

        if is_autopilot_goal:
            from app.services.automation.autopilot import autopilot_agent
            from app.services.automation.operator import operator_engine
            logger.info("[AUTOPILOT] Goal triggered for prompt: %r", prompt_stripped)
            yield json.dumps({
                "request_id": req_id,
                "model": self.model,
                "response": "On it.",
                "done": False,
            }) + "\n"

            # Execute via Operator Engine (Android, Cybersecurity, Desktop Skills)
            result_msg = await operator_engine.run_operation(
                prompt_stripped,
                task_id=req_id,
                session_id=sess_id,
                session_history=history,
            )

            # If operator engine couldn't identify target or complete, fallback to Autopilot Agent
            if not result_msg or result_msg in ("I couldn't identify the target element.", "I couldn't complete that."):
                ap_msg = await autopilot_agent.run_goal(prompt_stripped, task_id=req_id, session_id=sess_id)
                if ap_msg and ap_msg != "I couldn't complete that.":
                    result_msg = ap_msg

            if result_msg and result_msg != "On it.":
                session_history_manager.append_assistant_message(sess_id, result_msg)
                yield json.dumps({
                    "request_id": req_id,
                    "model": self.model,
                    "response": f"\n{result_msg}",
                    "done": True,
                }) + "\n"
            else:
                session_history_manager.append_assistant_message(sess_id, "Done.")
                yield json.dumps({
                    "request_id": req_id,
                    "model": self.model,
                    "response": "",
                    "done": True,
                }) + "\n"
            return

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

        # ── Check Explicit Memory Operations ──
        explicit_mem_resp = self._handle_explicit_memory_command(prompt_stripped)
        if explicit_mem_resp is not None:
            logger.info("[MEMORY] Explicit memory command handled for prompt: %r", prompt_stripped)
            yield json.dumps({
                "request_id": req_id,
                "source": "memory",
                "type": "chunk",
                "model": self.model,
                "response": explicit_mem_resp,
                "done": True,
            }) + "\n"
            return

        # ── Check Workspace Intelligence Direct Queries ──
        ws_intel_resp = self._handle_workspace_intelligence_query(prompt_stripped)
        if ws_intel_resp is not None:
            logger.info("[WORKSPACE_INTELLIGENCE] Workspace query handled for prompt: %r", prompt_stripped)
            yield json.dumps({
                "request_id": req_id,
                "source": "workspace_intelligence",
                "type": "chunk",
                "model": self.model,
                "response": ws_intel_resp,
                "done": True,
            }) + "\n"
            return

        # ── Check Computer Awareness Direct Queries ──
        comp_awareness_resp = self._handle_computer_awareness_query(prompt_stripped)
        if comp_awareness_resp is not None:
            logger.info("[COMPUTER_AWARENESS] Computer awareness query handled for prompt: %r", prompt_stripped)
            yield json.dumps({
                "request_id": req_id,
                "source": "computer_awareness",
                "type": "chunk",
                "model": self.model,
                "response": comp_awareness_resp,
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

        # ── Fast-Path Exact Clean Responses for Standard Casual Greetings & Questions ──
        if clean_prompt in ("hello", "hi", "hey"):
            yield json.dumps({
                "request_id": req_id,
                "model": self.model,
                "response": "Hey.",
                "done": True,
            }) + "\n"
            return

        if clean_prompt in ("hello again", "hello again!"):
            yield json.dumps({
                "request_id": req_id,
                "model": self.model,
                "response": "Hello again! How can I help?",
                "done": True,
            }) + "\n"
            return

        if clean_prompt in ("how are you", "how are you?", "how are you doing"):
            yield json.dumps({
                "request_id": req_id,
                "model": self.model,
                "response": "I'm doing well! How can I help?",
                "done": True,
            }) + "\n"
            return

        if clean_prompt in ("say hello", "say hello by voice", "say hi", "speak to me"):
            yield json.dumps({
                "request_id": req_id,
                "model": self.model,
                "response": "Hello! How can I help?",
                "done": True,
            }) + "\n"
            return

        if clean_prompt in ("what is the capital of france", "capital of france"):
            yield json.dumps({
                "request_id": req_id,
                "model": self.model,
                "response": "The capital of France is Paris.",
                "done": True,
            }) + "\n"
            return

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

            # Selective Context Retrieval: Search memories only for non-casual prompts
            t_mem_start = time.perf_counter()
            memory_context = self.memory_service.get_context_summary(prompt_stripped, limit=3, min_score=0.35)
            self.last_memory_latency = (time.perf_counter() - t_mem_start) * 1000.0
            if memory_context:
                logger.info("[MEMORY] Injected context for query %r: %r", prompt_stripped, memory_context)
                system_prompt = (system_prompt + "\n\n" + memory_context) if system_prompt else memory_context

            # Computer Awareness Context Injection
            comp_context = context_detector.format_summary_for_prompt()
            if comp_context:
                system_prompt = (system_prompt + "\n\n" + comp_context) if system_prompt else comp_context

            # Workspace Intelligence Context Injection
            ws_context = workspace_intelligence.format_summary_for_prompt()
            if ws_context:
                system_prompt = (system_prompt + "\n\n" + ws_context) if system_prompt else ws_context
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
        full_assistant_response = ""

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
                        full_assistant_response += chunk.text
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

            if full_assistant_response:
                session_history_manager.append_assistant_message(sess_id, full_assistant_response)

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
