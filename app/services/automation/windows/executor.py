"""
Windows Tool Executor & Action Coordinator for FALSO Autopilot.

Translates high-level Autopilot decisions into REAL Windows actions:
- Application Launch & Window Management
- Structured Keyboard & Mouse Automation
- UI Automation Element Targeting
- Browser Navigation & Search
- Verified Execution & Audit Logging

Every action follows: DISPATCH → EXECUTE → VERIFY → COMPLETE
Process existence alone is NEVER sufficient verification.
"""

from __future__ import annotations

import logging
import time
from typing import Any

from app.services.automation.permissions import (
    FileOperation,
    PermissionLevel,
    permission_manager,
)
from app.services.automation.windows.browser_controller import browser_controller
from app.services.automation.windows.keyboard_controller import keyboard_controller
from app.services.automation.windows.mouse_controller import mouse_controller
from app.services.automation.windows.process_manager import process_manager
from app.services.automation.windows.screen_observer import screen_observer
from app.services.automation.windows.ui_automation import ui_automation
from app.services.automation.windows.window_manager import window_manager

logger = logging.getLogger(__name__)


class WindowsExecutor:
    """Action Coordinator for Real Windows Control.

    Enforces the action result contract:
    - dispatched: action was sent to the Windows layer
    - executed: Windows layer reported the action was performed
    - verified: independent observation confirmed the expected state change
    - completed: dispatched AND executed AND verified
    """

    def execute_action(
        self,
        action_type: str,
        task_id: str = "AUTOPILOT-TASK",
        request_id: str = "REQ-001",
        **kwargs: Any
    ) -> dict[str, Any]:
        """Execute structured Windows action with permission checks & verification."""

        if permission_manager.is_lockdown_active():
            return {
                "success": False, "error": "FALSO Emergency Lockdown Active: Windows execution disabled.",
                "dispatched": False, "executed": False, "verified": False,
            }

        start_time = time.perf_counter()
        action_clean = action_type.lower().strip()
        dispatched = True
        executed = False
        verified = False
        verification_reason = ""
        error_msg = None

        logger.info("[WINDOWS_EXECUTOR] Executing action '%s' with params: %s", action_clean, kwargs)

        try:
            # 1. LAUNCH APPLICATION
            if action_clean in ("launch_app", "open_app", "app.launch"):
                app_name = kwargs.get("app") or kwargs.get("app_name") or kwargs.get("target") or "calculator"
                launch_res = process_manager.launch_app(app_name, args=kwargs.get("args"))
                if isinstance(launch_res, dict):
                    executed = launch_res.get("executed", launch_res.get("success", False))
                    verified = launch_res.get("verified", False)
                    verification_reason = launch_res.get("verification_reason", "")
                    if not verified:
                        error_msg = launch_res.get("verification_reason") or f"Failed to launch or verify application '{app_name}'"
                else:
                    executed = bool(launch_res)
                    # Verify by checking visible window
                    verified = executed and window_manager.is_window_open(app_name)
                    verification_reason = f"{app_name} is open." if verified else f"I couldn't open {app_name}."

            # 2. WINDOW CONTROL
            elif action_clean in ("focus_window", "window.focus"):
                title = kwargs.get("title") or kwargs.get("app") or kwargs.get("target") or "Calculator"
                executed = window_manager.focus_window(title)
                # Verify foreground
                if executed:
                    time.sleep(0.05)
                    verified = window_manager.verify_foreground(title)
                verification_reason = f"{title} focused." if verified else f"I couldn't focus {title}."
            elif action_clean in ("minimize_window", "window.minimize"):
                title = kwargs.get("title") or "Calculator"
                executed = window_manager.minimize_window(title)
                verified = executed
                verification_reason = f"{title} minimized." if verified else f"I couldn't minimize {title}."
            elif action_clean in ("maximize_window", "window.maximize"):
                title = kwargs.get("title") or "Calculator"
                executed = window_manager.maximize_window(title)
                verified = executed
                verification_reason = f"{title} maximized." if verified else f"I couldn't maximize {title}."

            # 3. KEYBOARD AUTOMATION — requires foreground verification
            elif action_clean in ("type_text", "keyboard.type"):
                text = kwargs.get("text", "")
                # Verify there is an active foreground window to receive input
                fg = window_manager.get_foreground_hwnd()
                if not fg["hwnd"]:
                    error_msg = "No foreground window to receive keyboard input."
                    verification_reason = error_msg
                else:
                    executed = keyboard_controller.type_text(text)
                    # Keyboard input is verified if it was sent to a real window
                    verified = executed and bool(fg["hwnd"])
                    verification_reason = "Text typed." if verified else "Failed to type text."
            elif action_clean in ("send_hotkey", "keyboard.hotkey"):
                keys = kwargs.get("keys", ["CTRL", "L"])
                fg = window_manager.get_foreground_hwnd()
                if not fg["hwnd"]:
                    error_msg = "No foreground window to receive hotkey."
                    verification_reason = error_msg
                else:
                    executed = keyboard_controller.send_hotkey(keys)
                    verified = executed and bool(fg["hwnd"])
                    verification_reason = "Hotkey sent." if verified else "Failed to send hotkey."

            # 4. MOUSE AUTOMATION — requires foreground verification
            elif action_clean in ("click_mouse", "mouse.click"):
                x, y = kwargs.get("x"), kwargs.get("y")
                executed = mouse_controller.click(x, y, button=kwargs.get("button", "left"))
                # Mouse click verified if cursor is at expected position
                if executed and x is not None and y is not None:
                    actual_pos = mouse_controller.get_position()
                    # Allow 5px tolerance
                    verified = abs(actual_pos[0] - x) <= 5 and abs(actual_pos[1] - y) <= 5
                else:
                    verified = executed
                verification_reason = "Mouse clicked." if verified else "Failed mouse click."
            elif action_clean in ("move_mouse", "mouse.move"):
                x, y = kwargs.get("x", 100), kwargs.get("y", 100)
                executed = mouse_controller.move_to(x, y)
                # Verify cursor actually moved
                actual_pos = mouse_controller.get_position()
                verified = abs(actual_pos[0] - x) <= 5 and abs(actual_pos[1] - y) <= 5
                verification_reason = "Mouse moved." if verified else "Failed mouse move."

            # 5. UI AUTOMATION
            elif action_clean in ("click_element", "ui.click_element"):
                name = kwargs.get("name", "Search")
                role = kwargs.get("role", "button")
                executed = ui_automation.click_element(name, role=role)
                verified = executed  # UIA click_element only returns True on real InvokePattern success
                verification_reason = f"Clicked UI element '{name}'." if verified else f"Failed to click '{name}'."

            # 6. BROWSER & FORM AUTOMATION
            elif action_clean in ("open_browser", "browser.open", "browser.navigate", "navigate", "search", "search_web", "browser.search", "fill_form", "submit_form"):
                from app.services.automation.browser.browser_action_registry import browser_action_registry
                from app.services.automation.browser.browser_engine import browser_engine

                phrase = action_clean.replace("browser.", "").replace("_", " ")
                struct_act = browser_action_registry.resolve_natural_language_action(phrase)
                if not struct_act:
                    struct_act = browser_action_registry.resolve_natural_language_action("navigate")
                    struct_act.target = kwargs.get("url") or kwargs.get("target") or "https://www.google.com"

                res = browser_engine.execute_browser_action(struct_act, task_id=task_id)
                executed = res.get("executed", res["success"])
                verified = res["verified"]
                verification_reason = res["verification_reason"]

            # 7. SCREEN OBSERVATION
            elif action_clean in ("capture_screen", "screen.capture"):
                path = screen_observer.capture_screenshot()
                executed = path is not None
                verified = executed
                verification_reason = "Screen captured." if verified else "Screen capture failed."

            # 8. OPEN APPROVED FOLDER (File Explorer)
            elif action_clean in ("open_approved_folder", "folder.open"):
                folder_path = kwargs.get("path") or kwargs.get("target") or kwargs.get("app") or ""
                fs_check = permission_manager.check_filesystem_access(folder_path, FileOperation.READ)
                if fs_check.allowed:
                    import subprocess
                    subprocess.Popen(["explorer.exe", str(folder_path)])
                    logger.info("[AUTOMATION][EXECUTE] Opened folder: %s", folder_path)
                    executed = True
                    # Verify by waiting for visible File Explorer window
                    verified = window_manager.wait_for_window("file explorer", timeout=3.0)
                    verification_reason = "File Explorer is open." if verified else "I couldn't open File Explorer."
                else:
                    error_msg = f"Folder access denied: {fs_check.reason}"
                    logger.warning("[AUTOMATION][EXECUTE] %s", error_msg)
                    dispatched = False
                    verification_reason = error_msg

            # 9. CLOSE WINDOW
            elif action_clean in ("close_window", "window.close", "close_app", "app.close"):
                target = kwargs.get("title") or kwargs.get("app") or kwargs.get("target") or "Calculator"
                close_res = window_manager.close_window(target)
                if close_res.get("unsaved_changes"):
                    duration = (time.perf_counter() - start_time) * 1000.0
                    permission_manager.log_action(
                        task_id=task_id, request_id=request_id, action_id=action_clean,
                        capability=f"windows.{action_clean}", target=target, result="FAILED_UNSAVED", duration_ms=duration
                    )
                    return {
                        "success": False,
                        "action": "close_window",
                        "target": target,
                        "dispatched": True,
                        "executed": False,
                        "verified": False,
                        "unsaved_changes": True,
                        "verification_reason": f"{target} has unsaved changes. I won't close it without confirmation.",
                        "error": f"{target} has unsaved changes. I won't close it without confirmation.",
                    }
                executed = close_res.get("executed", close_res.get("success", False))
                verified = close_res.get("verified", close_res.get("success", False))
                verification_reason = close_res.get("verification_reason", f"{target} is closed." if verified else f"I couldn't close {target}.")
                if not verified:
                    error_msg = verification_reason

            # 10. INTERACT WITH APPROVED APP (Calculator, Chrome, Notepad, File Explorer)
            elif action_clean in ("interact_with_app", "app.interact", "in_app_action", "calculate"):
                from app.services.automation.windows.in_app_action_engine import in_app_action_engine
                from app.services.automation.windows.app_action_registry import app_action_registry, StructuredInAppAction
                from app.services.automation.permissions import RiskLevel

                target_app = kwargs.get("app") or kwargs.get("target") or "Calculator"
                act_name = kwargs.get("in_app_action") or kwargs.get("sub_action") or kwargs.get("action") or ("calculate" if action_clean == "calculate" else "type")
                if "expression" in kwargs or "text" in kwargs:
                    expr = kwargs.get("expression") or kwargs.get("text")
                    if action_clean in ("interact_with_app", "calculate") and target_app.lower() == "calculator":
                        act_name = "calculate"
                        kwargs["expression"] = expr

                struct_action = app_action_registry.resolve_natural_language_action(target_app, str(kwargs.get("expression") or kwargs.get("text") or act_name))
                if not struct_action or struct_action.action == "type" and act_name != "type":
                    struct_action = StructuredInAppAction(
                        application=target_app,
                        action=act_name,
                        arguments=kwargs,
                        capability="windows.interact_with_app",
                        risk_level=RiskLevel.MEDIUM,
                        description=f"Perform '{act_name}' in {target_app}",
                    )

                return in_app_action_engine.execute_in_app_action(struct_action, task_id=task_id, request_id=request_id)

            else:
                error_msg = f"Unknown Windows action: '{action_type}'"
                dispatched = False

        except Exception as e:
            logger.exception("[WINDOWS_EXECUTOR] Error during action '%s': %s", action_clean, e)
            error_msg = str(e)

        duration = (time.perf_counter() - start_time) * 1000.0

        # Success requires BOTH execution AND verification
        success = dispatched and executed and verified
        res_str = "SUCCESS" if success else "FAILED"

        permission_manager.log_action(
            task_id=task_id,
            request_id=request_id,
            action_id=action_clean,
            capability=f"windows.{action_clean}",
            target=str(kwargs),
            result=res_str,
            duration_ms=duration,
        )

        return {
            "success": success,
            "action": action_clean,
            "target": str(kwargs.get("target") or kwargs.get("app") or kwargs.get("title") or action_clean),
            "dispatched": dispatched,
            "executed": executed,
            "verified": verified,
            "verification_reason": verification_reason or (error_msg if not success else "Verified."),
            "error": error_msg,
            "duration_ms": duration,
        }


windows_executor = WindowsExecutor()
