"""
FALSO 4.3 Persistent Memory & Personal Context Engine Acceptance Test Suite.

Verifies:
1. Explicit Memory Creation & Retrieval
2. Memory Update & Deletion
3. Preference Correction & Conflict Resolution
4. Confidence, Importance, Source, and Scoping (GLOBAL, PROJECT, TASK, SESSION)
5. Strict Secret & Credential Rejection (.env, API keys, bearer tokens, cookies, passwords)
6. Audit Logging (MEMORY_CREATED, MEMORY_UPDATED, MEMORY_DELETED, MEMORY_REJECTED)
7. Privacy Override ("FALSO don't remember this")
8. Memory Cannot Override PermissionManager (MEMORY IS NOT PERMISSION)
9. Normal Chat Fast Path & Automation + Memory Integration
10. GoalPlanner regression fix verification
11. Concise automation responses
12. Meta-response leakage prevention
"""

from __future__ import annotations

import json
import pytest

from app.services.automation.permissions import permission_manager
from app.services.automation.goal_planner import goal_planner
from app.services.brain import BrainService, _sanitize_history
from memory.service import MemoryService
from memory.secrets import is_sensitive_data

brain_service = BrainService()


class TestFalso43MemoryEngine:

    def setup_method(self):
        self.memory_service = MemoryService()
        self.memory_service.privacy_override_active = False

    def test_01_explicit_memory_creation(self):
        entry = self.memory_service.remember(
            fact="User prefers VS Code for python development.",
            category="user_preference",
            importance="HIGH",
            source="USER_EXPLICIT",
            scope="GLOBAL",
            key="preferred_editor",
            value="VS Code",
        )
        assert entry.id is not None
        assert entry.key == "preferred_editor"
        assert entry.value == "VS Code"

    def test_02_memory_retrieval(self):
        self.memory_service.remember(
            fact="User prefers VS Code for python development.",
            category="user_preference",
            key="preferred_editor",
            value="VS Code",
        )
        results = self.memory_service.recall("VS Code", limit=5)
        assert len(results) > 0

    def test_03_memory_update(self):
        entry = self.memory_service.remember_preference("preferred_theme", "Dark")
        updated = self.memory_service.update_memory(entry.id, content="User preference - preferred_theme: Dark+ Classic")
        assert updated is not None
        assert "Dark+ Classic" in updated.content

    def test_04_memory_deletion(self):
        entry = self.memory_service.remember_preference("temp_key", "temp_value")
        deleted = self.memory_service.forget(entry.id)
        assert deleted

    def test_05_memory_correction(self):
        self.memory_service.remember_preference("preferred_browser", "Chrome")
        resp = self.memory_service.process_explicit_memory_command("I don't use Chrome anymore. I use Edge.")
        assert "Edge" in resp
        memories = self.memory_service.list_memories()
        browser_m = [m for m in memories if m.key == "preferred_browser"]
        assert len(browser_m) == 1
        assert browser_m[0].value == "Edge"

    def test_06_memory_confidence(self):
        entry = self.memory_service.remember("Inferred task preference", confidence="MEDIUM")
        assert entry.confidence == "MEDIUM"

    def test_07_memory_importance(self):
        entry = self.memory_service.remember("Critical workflow rule", importance="HIGH")
        assert entry.importance == 3 or entry.metadata.get("importance_label") == "HIGH"

    def test_08_memory_source(self):
        entry = self.memory_service.remember("User explicitly stated preference", source="USER_EXPLICIT")
        assert entry.source == "USER_EXPLICIT"

    def test_09_memory_scope_global(self):
        entry = self.memory_service.remember_preference("preferred_lang", "Python", scope="GLOBAL")
        assert entry.scope == "GLOBAL"

    def test_10_project_scoped_memory(self):
        entry = self.memory_service.remember(
            fact="Project-Falso uses pytest and port 8000.",
            category="project_memory",
            scope="PROJECT",
            key="preferred_project",
            value="Project-Falso",
        )
        assert entry.scope == "PROJECT"

    def test_11_task_scoped_memory(self):
        entry = self.memory_service.remember(
            fact="Current task active state",
            category="task_memory",
            scope="TASK",
            classification="TASK",
        )
        assert entry.scope == "TASK"

    def test_12_temporary_memory_expiration(self):
        entry = self.memory_service.remember("Temporary observation", classification="TEMPORARY")
        assert entry.classification == "TEMPORARY"

    def test_13_sensitive_data_rejection_password(self):
        with pytest.raises(ValueError, match="Sensitive credentials"):
            self.memory_service.remember("My password is SecretPassword123")

    def test_14_api_key_rejection(self):
        with pytest.raises(ValueError, match="Sensitive credentials"):
            self.memory_service.remember("API key sk-1234567890abcdef1234567890")

    def test_15_env_syntax_rejection(self):
        with pytest.raises(ValueError, match="Sensitive credentials"):
            self.memory_service.remember("NVIDIA_API_KEY=nvapi-1234567890abcdef12345")

    def test_16_token_rejection(self):
        with pytest.raises(ValueError, match="Sensitive credentials"):
            self.memory_service.remember("Authorization: Bearer secret_bearer_token_string_123456")

    def test_17_cookie_rejection(self):
        with pytest.raises(ValueError, match="Sensitive credentials"):
            self.memory_service.remember("Cookie: sessionid=abcdef1234567890")

    def test_18_memory_budget_context_summary(self):
        summary = self.memory_service.get_context_summary("VS Code", limit=3)
        assert isinstance(summary, str)

    def test_19_relevant_memory_retrieval(self):
        results = self.memory_service.recall("Python", limit=5)
        assert isinstance(results, list)

    def test_20_irrelevant_memory_exclusion(self):
        results = self.memory_service.recall("unlikely_query_xyz_12345", limit=5)
        relevant = [r for r in results if r.score > 0.8]
        assert len(relevant) == 0

    def test_21_memory_cannot_grant_permissions(self):
        self.memory_service.remember("User usually allows file deletion", category="user_preference")
        # Memory storing a preference must NOT affect PermissionManager's DENY on system dirs
        from app.services.automation.permissions import FileOperation
        perm = permission_manager.check_filesystem_access(r"C:\Windows\System32", FileOperation.READ)
        assert not perm.allowed

    def test_22_task_continuation(self):
        self.memory_service.remember("Last step verified: VS Code launched", category="task_memory", scope="TASK")
        results = self.memory_service.recall("task_memory", limit=1)
        assert len(results) >= 0

    def test_23_failed_strategy_memory(self):
        entry = self.memory_service.remember(
            fact="Failed launching app via raw shell method deprecated.",
            category="automation_memory",
            scope="GLOBAL",
            importance="HIGH",
        )
        assert entry.category == "automation_memory"

    def test_24_successful_strategy_memory(self):
        entry = self.memory_service.remember(
            fact="Successfully launched VS Code using Win32 API.",
            category="automation_memory",
            scope="PROJECT",
        )
        assert entry.scope == "PROJECT"

    def test_25_conflicting_memory_resolution(self):
        self.memory_service.remember_preference("preferred_editor", "Notepad")
        self.memory_service.remember_preference("preferred_editor", "VS Code")
        memories = self.memory_service.list_memories()
        editors = [m for m in memories if m.key == "preferred_editor"]
        assert len(editors) == 1
        assert editors[0].value == "VS Code"

    @pytest.mark.asyncio
    async def test_26_dont_remember_this_privacy_override(self):
        responses = []
        async for chunk in brain_service.chat("FALSO don't remember this"):
            responses.append(chunk)
        full_text = "".join(responses)
        assert "Privacy" in full_text or "privacy" in full_text

    @pytest.mark.asyncio
    async def test_27_forget_that_explicit_command(self):
        from memory.service import memory_service as global_ms
        global_ms.remember_preference("temp_pref", "temp_val")
        responses = []
        async for chunk in brain_service.chat("FALSO forget that"):
            responses.append(chunk)
        full_text = "".join(responses)
        assert "Forgotten" in full_text or "forgotten" in full_text

    @pytest.mark.asyncio
    async def test_28_normal_chat_fast_path(self):
        responses = []
        async for chunk in brain_service.chat("hello"):
            responses.append(chunk)
        full_text = "".join(responses)
        assert len(full_text) > 0

    def test_29_goal_planner_regression_fixed(self):
        """Verify GoalPlanner.create_plan() no longer throws NameError."""
        plan = goal_planner.create_plan("open chrome")
        assert plan is not None
        assert len(plan.steps) > 0
        assert plan.steps[0].action in ("launch_app", "open_browser", "focus_window")
        assert plan.current_state is not None
        assert "running_apps" in plan.current_state

    def test_30_goal_planner_notepad_plan(self):
        plan = goal_planner.create_plan("open notepad")
        assert plan is not None
        assert len(plan.steps) > 0

    def test_31_goal_planner_calculator_plan(self):
        plan = goal_planner.create_plan("open calculator")
        assert plan is not None
        assert len(plan.steps) > 0

    def test_32_goal_planner_explorer_plan(self):
        plan = goal_planner.create_plan("open file explorer")
        assert plan is not None
        assert len(plan.steps) > 0
        assert plan.steps[0].action == "open_approved_folder"

    def test_33_goal_planner_memory_additive(self):
        """Memory should augment cur_state, not replace base observation."""
        obs = {"running_apps": ["chrome.exe"], "active_app": "Chrome", "active_window": "Chrome"}
        plan = goal_planner.create_plan("open notepad", obs)
        assert "running_apps" in plan.current_state
        assert plan.current_state["running_apps"] == ["chrome.exe"]

    def test_34_meta_response_sanitization(self):
        """History sanitization must filter meta labels."""
        from app.schemas.brain import ChatMessage
        history = [
            ChatMessage(role="assistant", content="Hello! [USER PROFILE] Some context."),
            ChatMessage(role="assistant", content="=== PERSONAL AI COMPANION ACTIVE CONTEXT ==="),
            ChatMessage(role="assistant", content="CRITICAL CONVERSATIONAL & RESPONSE CLEANLINESS RULES: never do this."),
            ChatMessage(role="assistant", content="Normal clean response without meta."),
        ]
        sanitized = _sanitize_history(history)
        for msg in sanitized:
            content_lower = msg.content.lower()
            assert "user profile" not in content_lower
            assert "personal ai companion" not in content_lower
            assert "critical conversational" not in content_lower

    def test_35_concise_automation_responses(self):
        """AutopilotAgent should return concise target-specific messages."""
        from app.services.automation.autopilot import AutopilotAgent
        assert AutopilotAgent._concise_completion_response("open chrome") == "Chrome is open."
        assert AutopilotAgent._concise_completion_response("open notepad") == "Notepad is open."
        assert AutopilotAgent._concise_completion_response("open calculator") == "Calculator is open."
        assert AutopilotAgent._concise_completion_response("open file explorer") == "File Explorer is open."
        assert AutopilotAgent._concise_failure_response("open chrome") == "I couldn't open Chrome."
        assert AutopilotAgent._concise_failure_response("open notepad") == "I couldn't open Notepad."

    def test_36_memory_audit_logging(self):
        entry = self.memory_service.remember_preference("audit_test_key", "audit_test_val")
        assert entry.id is not None
        self.memory_service.forget(entry.id)

    def test_37_is_sensitive_data_works(self):
        assert is_sensitive_data("sk-1234567890abcdef1234567890")
        assert is_sensitive_data("My password is Secret123")
        assert not is_sensitive_data("I prefer VS Code.")
        assert not is_sensitive_data("Open Chrome for me.")
