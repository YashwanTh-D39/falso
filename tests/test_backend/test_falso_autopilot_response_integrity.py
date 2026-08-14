"""
Test Suite: FALSO Autopilot Response Integrity & Control-Flow Regression Tests.

Verifies:
1. Successful verified action returns success ("Done." / "Calculator is open." / "20.")
2. Failed Chrome action returns failure ("I couldn't open Chrome." / "I couldn't close Chrome.")
3. Failed Notepad action returns failure ("I couldn't open Notepad." / "I couldn't close Notepad.")
4. Failed Calculator action returns failure ("I couldn't open Calculator." / "I couldn't close Calculator.")
5. Permission denial returns failure ("I couldn't complete that safely." / "I need permission for that action.")
6. Verification failure returns failure (never "Done.")
7. Exception returns failure (never "Done.")
8. Cancellation returns "Cancelled."
9. NOT_IMPLEMENTED / stub workflow returns "I can't automate that yet."
10. Finally cleanup cannot override return value
11. Static inspection: No return statement exists inside finally cleanup
12. No failed task can ever return "Done."
"""

import ast
import inspect
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch
import pytest

from app.services.automation.autopilot import (
    AutopilotAgent,
    OperatingMode,
    TaskState,
    TaskStatus,
    autopilot_agent,
)
from app.services.automation.permissions import (
    PermissionCheckResult,
    RiskLevel,
    permission_manager,
)
from app.services.automation.windows.executor import windows_executor
from app.services.automation.windows.window_manager import window_manager


class TestAutopilotResponseIntegrity:

    def setup_method(self):
        permission_manager.disable_lockdown()

    @pytest.mark.asyncio
    async def test_01_successful_verified_action_returns_success(self):
        agent = AutopilotAgent()
        with patch.object(
            windows_executor,
            "execute_action",
            return_value={
                "success": True,
                "dispatched": True,
                "executed": True,
                "verified": True,
                "verification_reason": "Calculator is open.",
            },
        ), patch.object(window_manager, "is_window_open", return_value=True):
            res = await agent.run_goal("Open Calculator.", task_id="TEST-INT-01")
            assert res in ("Calculator is open.", "Done.")
            assert agent.completed_tasks[-1].status == TaskStatus.COMPLETED

    @pytest.mark.asyncio
    async def test_02_failed_chrome_action_returns_failure(self):
        agent = AutopilotAgent()
        with patch.object(
            windows_executor,
            "execute_action",
            return_value={
                "success": False,
                "dispatched": True,
                "executed": False,
                "verified": False,
                "verification_reason": "I couldn't open Chrome.",
                "error": "Failed to launch Chrome",
            },
        ), patch.object(window_manager, "is_window_open", return_value=False):
            res = await agent.run_goal("Open Chrome.", task_id="TEST-INT-02")
            assert res == "I couldn't open Chrome."
            assert res != "Done."
            assert agent.completed_tasks[-1].status == TaskStatus.FAILED

    @pytest.mark.asyncio
    async def test_03_failed_notepad_action_returns_failure(self):
        agent = AutopilotAgent()
        with patch.object(
            windows_executor,
            "execute_action",
            return_value={
                "success": False,
                "dispatched": True,
                "executed": False,
                "verified": False,
                "verification_reason": "I couldn't open Notepad.",
                "error": "Failed to launch Notepad",
            },
        ), patch.object(window_manager, "is_window_open", return_value=False):
            res = await agent.run_goal("Open Notepad.", task_id="TEST-INT-03")
            assert res == "I couldn't open Notepad."
            assert res != "Done."
            assert agent.completed_tasks[-1].status == TaskStatus.FAILED

    @pytest.mark.asyncio
    async def test_04_failed_calculator_action_returns_failure(self):
        agent = AutopilotAgent()
        with patch.object(
            windows_executor,
            "execute_action",
            return_value={
                "success": False,
                "dispatched": True,
                "executed": False,
                "verified": False,
                "verification_reason": "I couldn't open Calculator.",
                "error": "Failed to launch Calculator",
            },
        ), patch.object(window_manager, "is_window_open", return_value=False):
            res = await agent.run_goal("Open Calculator.", task_id="TEST-INT-04")
            assert res == "I couldn't open Calculator."
            assert res != "Done."
            assert agent.completed_tasks[-1].status == TaskStatus.FAILED

    @pytest.mark.asyncio
    async def test_05_permission_denial_returns_failure(self):
        agent = AutopilotAgent()
        with patch.object(
            permission_manager,
            "check_capability",
            return_value=PermissionCheckResult(allowed=False, reason="Denied by security policy."),
        ):
            res = await agent.run_goal("Open Calculator.", task_id="TEST-INT-05")
            assert res in ("I couldn't complete that safely.", "I need permission for that action.")
            assert res != "Done."
            assert agent.completed_tasks[-1].status == TaskStatus.FAILED

    @pytest.mark.asyncio
    async def test_06_verification_failure_returns_failure_never_done(self):
        agent = AutopilotAgent()
        # Execution says executed=True, but verified=False
        with patch.object(
            windows_executor,
            "execute_action",
            return_value={
                "success": False,
                "dispatched": True,
                "executed": True,
                "verified": False,
                "verification_reason": "Window not found after launch.",
            },
        ), patch.object(window_manager, "is_window_open", return_value=False):
            res = await agent.run_goal("Open Calculator.", task_id="TEST-INT-06")
            assert res == "I couldn't open Calculator."
            assert res != "Done."
            assert agent.completed_tasks[-1].status == TaskStatus.FAILED

    @pytest.mark.asyncio
    async def test_07_exception_returns_failure_never_done(self):
        agent = AutopilotAgent()
        with patch.object(
            windows_executor,
            "execute_action",
            side_effect=RuntimeError("Unexpected subsystem failure"),
        ):
            res = await agent.run_goal("Open Chrome.", task_id="TEST-INT-07")
            assert res in ("I couldn't open Chrome.", "I couldn't complete that.")
            assert res != "Done."
            assert agent.completed_tasks[-1].status == TaskStatus.FAILED

    @pytest.mark.asyncio
    async def test_08_cancellation_remains_cancelled(self):
        agent = AutopilotAgent()

        def cancel_during_execution(*args, **kwargs):
            agent.cancel_active_task()
            return {"success": False, "executed": False, "verified": False}

        with patch.object(windows_executor, "execute_action", side_effect=cancel_during_execution):
            res = await agent.run_goal("Open Calculator.", task_id="TEST-INT-08")
            assert res == "Cancelled."
            assert agent.completed_tasks[-1].status == TaskStatus.CANCELLED

    @pytest.mark.asyncio
    async def test_09_not_implemented_remains_unsupported(self):
        agent = AutopilotAgent()
        res1 = await agent.run_goal("make my project healthy", task_id="TEST-STUB-01")
        assert res1 == "I can't automate that yet."
        assert agent.completed_tasks[-1].status == TaskStatus.FAILED

        res2 = await agent.run_goal("prepare development environment", task_id="TEST-STUB-02")
        assert res2 == "I can't automate that yet."

        res3 = await agent.run_goal("organize my downloads", task_id="TEST-STUB-03")
        assert res3 == "I can't automate that yet."

        res4 = await agent.run_goal("run and fix tests", task_id="TEST-STUB-04")
        assert res4 == "I can't automate that yet."

    @pytest.mark.asyncio
    async def test_10_finally_cleanup_cannot_override_return_value(self):
        agent = AutopilotAgent()
        # Even if cleanup executes, the returned value must be the failure string
        with patch.object(
            windows_executor,
            "execute_action",
            return_value={"success": False, "executed": False, "verified": False},
        ), patch.object(window_manager, "is_window_open", return_value=False):
            res = await agent.run_goal("Open Notepad.", task_id="TEST-INT-10")
            assert res == "I couldn't open Notepad."
            assert agent.mode == OperatingMode.NORMAL
            assert agent.active_task is None

    def test_11_static_check_no_return_in_finally(self):
        """Static AST check: ensure no Try block has a Return node inside its finalbody."""
        autopilot_path = Path(__file__).resolve().parent.parent.parent / "app" / "services" / "automation" / "autopilot.py"
        with open(autopilot_path, "r", encoding="utf-8") as f:
            source = f.read()

        tree = ast.parse(source, filename=str(autopilot_path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Try):
                for final_stmt in node.finalbody:
                    for sub in ast.walk(final_stmt):
                        assert not isinstance(sub, ast.Return), f"Found return statement inside finally block at line {sub.lineno}!"

    def test_12_static_check_single_failure_response_definition(self):
        """Static AST check: confirm exactly ONE _concise_failure_response function definition exists."""
        autopilot_path = Path(__file__).resolve().parent.parent.parent / "app" / "services" / "automation" / "autopilot.py"
        with open(autopilot_path, "r", encoding="utf-8") as f:
            source = f.read()

        tree = ast.parse(source, filename=str(autopilot_path))
        failure_func_count = 0
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                if node.name == "_concise_failure_response":
                    failure_func_count += 1

        assert failure_func_count == 1, f"Expected exactly 1 _concise_failure_response, found {failure_func_count}"
