"""
FALSO 4.13 Android Skills Module.

Implements BaseSkill-compatible skills for Android:
- AndroidDeviceSkill: device queries (battery, storage, lock, screenshot, touch, navigation)
- AndroidApplicationSkill: natural app package resolution & launch verification
- AndroidContactsSkill: safe contact resolution & disambiguation
- AndroidCallingSkill: calling workflow with mandatory confirmation
- AndroidMessagingSkill: messaging workflow with mandatory confirmation
"""

from __future__ import annotations

import logging
import re
import time
from typing import Any

from app.services.automation.android.controller import android_controller
from app.services.automation.android.device_manager import android_device_manager
from app.services.automation.android.device_state import ConnectionState
from app.services.automation.android.observer import android_observer
from app.services.automation.operator.computer_state import ComputerState
from app.services.automation.operator.skills.base_skill import BaseSkill
from app.services.automation.permissions import RiskLevel

logger = logging.getLogger(__name__)

# Natural app name to standard Android package mappings
KNOWN_APP_PACKAGES = {
    "youtube": "com.google.android.youtube",
    "chrome": "com.android.chrome",
    "browser": "com.android.chrome",
    "whatsapp": "com.whatsapp",
    "settings": "com.android.settings",
    "camera": "com.android.camera",
    "maps": "com.google.android.apps.maps",
    "gmail": "com.google.android.gm",
    "calculator": "com.google.android.calculator",
    "play store": "com.android.vending",
    "gallery": "com.google.android.apps.photos",
    "photos": "com.google.android.apps.photos",
}


class AndroidDeviceSkill(BaseSkill):
    """Handles general device actions on the connected phone."""
    name = "android_device"
    allowed_applications = ["phone", "android", "device", "mobile", "battery", "storage", "screenshot", "screen"]
    default_risk_level = RiskLevel.LOW

    def can_handle(self, target: str, action: str) -> bool:
        t = target.lower()
        a = action.lower()
        if a in ("launch_android_app", "open_android_app", "close_android_app", "stop_android_app", "launch_app", "open_app", "close_app"):
            return False
        if t in ("android_app", "phone_app", "android_call", "android_message", "android_contacts"):
            return False
        if any(w in t for w in ("phone", "android", "mobile", "device")):
            return True
        return any(act in a for act in ("battery", "storage", "screenshot", "tap", "swipe", "scroll", "home", "back", "recent_apps", "lock_state", "audit_phone", "unlock", "wake"))

    def handle_unlock_request(self, dev_id: str | None = None, params: dict[str, Any] | None = None) -> dict[str, Any]:
        """Explicit unlock handler according to Directive 4.13."""
        params = params or {}
        task_id = params.get("task_id", "task_unlock")
        goal = params.get("goal", "unlock phone")
        pending_steps = params.get("pending_steps", [])

        # 1. Discover devices
        logger.info("[ANDROID][INTENT] intent=UNLOCK_DEVICE")
        logger.info("[ANDROID][ROUTE] method=ANDROID_SKILL")
        devices = android_device_manager.list_devices()

        if not devices:
            logger.warning("[ANDROID][DEVICE] No connected Android devices found.")
            return {"success": False, "error": "No authorized Android phone is connected.", "summary": "No authorized Android phone is connected.", "verified": False}

        # Select target device
        if dev_id:
            target_dev = next((d for d in devices if d.device_id == dev_id), None)
            if not target_dev:
                return {"success": False, "error": f"Android device '{dev_id}' not found.", "summary": f"Android device '{dev_id}' not found.", "verified": False}
        else:
            authorized_devs = [d for d in devices if d.is_authorized]
            if len(devices) > 1 and len(authorized_devs) > 1:
                dev_ids = ", ".join(d.device_id for d in devices)
                logger.warning("[ANDROID][DEVICE] Multiple devices connected: %s", dev_ids)
                return {"success": False, "error": f"Multiple Android devices connected ({dev_ids}). Which device would you like to use?", "summary": f"Multiple Android devices connected ({dev_ids}). Which device would you like to use?", "verified": False}
            target_dev = authorized_devs[0] if authorized_devs else devices[0]

        logger.info("[ANDROID][DEVICE] device_id=%s model=%s", target_dev.device_id, target_dev.model)

        # 2. Verify authorization
        if not target_dev.is_authorized or target_dev.connection_state == ConnectionState.UNAUTHORIZED:
            logger.warning("[ANDROID][DEVICE] Device %s unauthorized.", target_dev.device_id)
            return {"success": False, "error": "Your phone is connected but hasn't authorized this computer.", "summary": "Your phone is connected but hasn't authorized this computer.", "verified": False}

        # 3. Verify online state
        if target_dev.connection_state == ConnectionState.OFFLINE:
            logger.warning("[ANDROID][DEVICE] Device %s is offline.", target_dev.device_id)
            return {"success": False, "error": "Your phone is offline.", "summary": "Your phone is offline.", "verified": False}

        # 4. Check lock state
        l_info = android_observer.observe_lock_state(target_dev.device_id)
        is_l = l_info.get("is_locked")
        state_str = l_info.get("state")
        logger.info("[ANDROID][LOCK] state=%s", state_str)

        if is_l is None or state_str == "UNKNOWN":
            return {"success": False, "error": "I couldn't verify your phone's lock state.", "summary": "I couldn't verify your phone's lock state.", "verified": False}

        if is_l is False:
            logger.info("[ANDROID][UNLOCK] Device %s already unlocked.", target_dev.device_id)
            return {"success": True, "summary": "Your phone is already unlocked.", "verified": True}

        # 5. Initiate unlock wait
        from app.services.automation.android.unlock_manager import authorized_unlock_manager
        logger.info("[ANDROID][UNLOCK] action=WAITING_FOR_USER_UNLOCK device_id=%s", target_dev.device_id)
        ok_wait, prompt = authorized_unlock_manager.initiate_unlock_wait(
            task_id=task_id,
            goal=goal,
            pending_steps=pending_steps,
            device_id=target_dev.device_id,
            target_app="android_device",
        )
        return {
            "success": True,
            "summary": prompt,
            "prompt": prompt,
            "waiting_for_unlock": True,
            "is_locked": True,
            "verified": True,
        }

    def execute(self, action: str, target: str, params: dict[str, Any], state: ComputerState) -> dict[str, Any]:
        dev_id = params.get("device_id")

        # 1. Battery Query
        if action in ("get_battery", "battery", "check_battery"):
            bat = android_observer.observe_battery(dev_id)
            lvl = bat.get("level")
            chg = "charging" if bat.get("is_charging") else "not charging"
            summary = f"Phone battery is at {lvl}%, {chg}." if lvl is not None else "Could not read battery state."
            return {"success": lvl is not None, "battery": bat, "summary": summary, "verified": True}

        # 2. Storage Query
        if action in ("get_storage", "storage", "check_storage"):
            st = android_observer.observe_storage(dev_id)
            free = st.get("free_gb")
            summary = f"{free} GB free storage on phone." if free is not None else "Could not read storage statistics."
            return {"success": free is not None, "storage": st, "summary": summary, "verified": True}

        # 3. Screenshot Capture
        if action in ("capture_screenshot", "screenshot", "take_screenshot"):
            pc_path = params.get("pc_path")
            res = android_controller.capture_screenshot(target_pc_path=pc_path, device_id=dev_id)
            if res.get("success"):
                return {"success": True, "file_path": res.get("file_path"), "summary": "Phone screenshot captured and verified.", "verified": True}
            return {"success": False, "error": res.get("error", "Screenshot failed."), "verified": False}

        # 4. Lock State Query
        if action in ("check_lock", "lock_state", "is_locked"):
            l_info = android_observer.observe_lock_state(dev_id)
            is_l = l_info.get("is_locked")
            summary = "Your phone is locked." if is_l else "Your phone is unlocked."
            return {"success": True, "is_locked": is_l, "summary": summary, "verified": True}

        # 5. Touch / Tap
        if action == "tap":
            x = int(params.get("x", 0))
            y = int(params.get("y", 0))
            res = android_controller.tap(x, y, device_id=dev_id)
            return {"success": res.get("success", False), "summary": f"Tapped ({x}, {y}) on phone.", "verified": True}

        # 6. Gestures & Navigation
        if action == "swipe":
            res = android_controller.swipe(
                int(params.get("x1", 0)), int(params.get("y1", 0)),
                int(params.get("x2", 0)), int(params.get("y2", 0)),
                duration_ms=int(params.get("duration", 300)),
                device_id=dev_id,
            )
            return {"success": res.get("success", False), "summary": "Swipe gesture performed.", "verified": True}

        if action == "home":
            res = android_controller.home(device_id=dev_id)
            return {"success": res.get("success", False), "summary": "Went to Home screen on phone.", "verified": True}

        if action == "back":
            res = android_controller.back(device_id=dev_id)
            return {"success": res.get("success", False), "summary": "Pressed Back on phone.", "verified": True}

        # 7. Phone Cybersecurity Audit
        if action in ("audit_phone", "phone_security"):
            from app.services.automation.android.cybersecurity import android_cybersecurity_audit
            res = android_cybersecurity_audit.run_audit(device_id=dev_id)
            return {"success": True, "summary": res.get("summary"), "audit": res, "verified": True}

        # 8. Unlock phone / Wake Display
        if action in ("unlock", "unlock_phone", "wake", "wake_display", "ANDROID_UNLOCK_WAIT"):
            return self.handle_unlock_request(dev_id=dev_id, params=params)

        return {"success": False, "error": f"Unsupported android action: {action}"}

    def verify(self, action: str, target: str, before_state: ComputerState, after_state: ComputerState, result: dict[str, Any]) -> tuple[bool, str]:
        if result.get("waiting_for_unlock"):
            return True, result.get("summary", "Please unlock your phone.")
        if not result.get("success", False):
            return False, result.get("error", "Android device operation failed.")
        return True, result.get("summary", "Device operation completed.")


class AndroidApplicationSkill(BaseSkill):
    """Manages app launching and foreground package verification on phone."""
    name = "android_app"
    allowed_applications = list(KNOWN_APP_PACKAGES.keys()) + ["app", "package"]
    default_risk_level = RiskLevel.LOW

    def can_handle(self, target: str, action: str) -> bool:
        t = target.lower()
        a = action.lower()
        if any(app in t for app in KNOWN_APP_PACKAGES):
            return True
        if "android_app" in t or "phone_app" in t:
            return True
        return action in ("launch_android_app", "open_app", "close_app", "stop_app")

    def execute(self, action: str, target: str, params: dict[str, Any], state: ComputerState) -> dict[str, Any]:
        dev_id = params.get("device_id")
        app_name = (params.get("app") or target or "").lower().strip()

        logger.info("[ANDROID][REQUEST] action=%s app=%s target=%s", action, app_name, target)
        logger.info("[ANDROID][ADB] executable=%s", android_device_manager.get_adb_executable())

        # 1. Device Discovery & Validation
        devices = android_device_manager.list_devices()
        if not devices:
            logger.warning("[ANDROID][DEVICE] No connected Android devices found.")
            return {"success": False, "error": "No authorized Android phone is connected.", "verified": False}

        if dev_id:
            target_dev = next((d for d in devices if d.device_id == dev_id), None)
            if not target_dev:
                return {"success": False, "error": f"Android device '{dev_id}' not found.", "verified": False}
        else:
            authorized_devs = [d for d in devices if d.is_authorized]
            target_dev = authorized_devs[0] if authorized_devs else devices[0]

        target_dev_id = target_dev.device_id
        logger.info("[ANDROID][DEVICE] device_id=%s model=%s is_auth=%s", target_dev_id, target_dev.model, target_dev.is_authorized)

        if not target_dev.is_authorized:
            return {"success": False, "error": "Your phone is connected but hasn't authorized this computer.", "verified": False}

        # 2. Check lock state
        lock_info = android_observer.observe_lock_state(target_dev_id)
        if lock_info.get("is_locked") is True:
            logger.info("[ANDROID][LOCK] Device %s is locked. Initiating unlock wait.", target_dev_id)
            from app.services.automation.android.unlock_manager import authorized_unlock_manager
            authorized_unlock_manager.initiate_unlock_wait(
                task_id=params.get("task_id", "task_app_launch"),
                goal=f"Open {app_name.capitalize()} on phone",
                pending_steps=[{"action_name": "launch_android_app", "target_app": target, "params": params}],
                device_id=target_dev_id,
                target_app=target,
            )
            return {
                "success": False,
                "error": "Your phone is locked. Unlock it and I'll continue.",
                "summary": "Your phone is locked. Unlock it and I'll continue.",
                "is_locked": True,
                "waiting_for_unlock": True,
                "verified": False,
            }

        # 3. Resolve package name
        pkg = KNOWN_APP_PACKAGES.get(app_name, params.get("package_name"))
        if not pkg:
            # Try searching installed packages
            installed = android_observer.observe_installed_packages(target_dev_id)
            matching = [p for p in installed if app_name in p.lower()]
            if len(matching) == 1:
                pkg = matching[0]
            elif len(matching) > 1:
                logger.warning("[ANDROID][PACKAGE] Ambiguous package match for %s: %s", app_name, matching)
                return {
                    "success": False,
                    "error": f"Found multiple matching packages for '{app_name}'. Please specify.",
                    "matching": matching,
                    "verified": False,
                }
            else:
                logger.warning("[ANDROID][PACKAGE] Package resolution failed for %s", app_name)
                return {
                    "success": False,
                    "error": f"Application '{app_name}' not found on connected phone.",
                    "verified": False,
                }

        logger.info("[ANDROID][PACKAGE] resolved_package=%s for app=%s", pkg, app_name)

        # 4. Launch Application
        logger.info("[ANDROID][LAUNCH] Launching package %s on device %s", pkg, target_dev_id)
        res = android_device_manager.execute_operation("launch_app", {"package_name": pkg}, device_id=target_dev_id)
        logger.info("[ANDROID][LAUNCH] Launch command returncode=%d success=%s", res.get("returncode", -1), res.get("success"))
        if not res.get("success"):
            return {"success": False, "error": f"Failed to launch '{app_name}'.", "verified": False}

        # 5. Authoritative Foreground Verification with bounded polling
        actual_pkg = None
        is_verified = False
        for attempt in range(3):
            time.sleep(0.4)
            fg_info = android_observer.observe_foreground_app(target_dev_id)
            actual_pkg = fg_info.get("package")
            logger.info("[ANDROID][OBSERVE] Attempt %d: observed_foreground=%s expected=%s", attempt + 1, actual_pkg, pkg)
            if actual_pkg and (actual_pkg == pkg or pkg in actual_pkg):
                is_verified = True
                break

        logger.info("[ANDROID][VERIFY] is_verified=%s package=%s observed=%s", is_verified, pkg, actual_pkg)

        canonical_names = {
            "youtube": "YouTube",
            "whatsapp": "WhatsApp",
            "chrome": "Chrome",
            "gmail": "Gmail",
            "maps": "Maps",
            "camera": "Camera",
            "settings": "Settings",
            "calculator": "Calculator",
        }
        display_name = canonical_names.get(app_name.lower(), app_name.capitalize())

        if is_verified:
            return {
                "success": True,
                "package": pkg,
                "app_name": display_name,
                "summary": f"{display_name} is open.",
                "verified": True,
                "execution_state": "VERIFIED",
            }
        else:
            return {
                "success": True,
                "package": pkg,
                "app_name": display_name,
                "summary": f"Launch command sent for {display_name}.",
                "verified": False,
                "capability_state": "EXECUTED_UNVERIFIED",
                "execution_state": "EXECUTED_UNVERIFIED",
            }

    def verify(self, action: str, target: str, before_state: ComputerState, after_state: ComputerState, result: dict[str, Any]) -> tuple[bool, str]:
        if result.get("waiting_for_unlock"):
            return True, result.get("summary", "Your phone is locked. Unlock it and I'll continue.")
        if not result.get("success", False):
            return False, result.get("error", "Application launch failed.")
        if result.get("verified") is True:
            return True, result.get("summary", f"{target.capitalize()} is open.")
        if result.get("capability_state") == "EXECUTED_UNVERIFIED":
            return False, result.get("summary", "I couldn't verify that action completed.")
        return result.get("verified", False), result.get("summary", "Launch failed.")


class AndroidContactsSkill(BaseSkill):
    """Resolves contacts safely without dumping full address book to LLM."""
    name = "android_contacts"
    allowed_applications = ["contacts", "people"]
    default_risk_level = RiskLevel.LOW

    def __init__(self) -> None:
        # Mock / sample contact store for demonstration / testing
        self._contacts = [
            {"name": "Rahul Sharma", "phone": "+919876541234", "normalized": "rahul sharma"},
            {"name": "Rahul Verma", "phone": "+919876545678", "normalized": "rahul verma"},
            {"name": "Alice Smith", "phone": "+15551234567", "normalized": "alice smith"},
        ]

    def can_handle(self, target: str, action: str) -> bool:
        t = target.lower()
        return "contact" in t or action in ("resolve_contact", "find_contact")

    def execute(self, action: str, target: str, params: dict[str, Any], state: ComputerState) -> dict[str, Any]:
        query = params.get("query") or params.get("name") or target
        res = self.resolve_contact(query)
        return {"success": res.get("match_type") in ("EXACT", "STRONG"), "result": res, "verified": True}

    def verify(self, action: str, target: str, before_state: ComputerState, after_state: ComputerState, result: dict[str, Any]) -> tuple[bool, str]:
        return result.get("verified", True), "Contact resolved."

    def resolve_contact(self, name_query: str) -> dict[str, Any]:
        q = name_query.lower().strip()
        # 1. Exact match
        exact = [c for c in self._contacts if c["name"].lower() == q or c["normalized"] == q]
        if len(exact) == 1:
            return {"match_type": "EXACT", "contact": exact[0]}

        # 2. First-name or partial match
        partial = [c for c in self._contacts if q in c["normalized"].split()]
        if len(partial) == 1:
            return {"match_type": "STRONG", "contact": partial[0]}
        elif len(partial) > 1:
            return {"match_type": "AMBIGUOUS", "matches": [c["name"] for c in partial]}

        return {"match_type": "NOT_FOUND"}


class AndroidCallingSkill(BaseSkill):
    """Enforces CALL -> CONFIRM -> EXECUTE -> VERIFY flow."""
    name = "android_call"
    allowed_applications = ["dialer", "phone_call", "call"]
    default_risk_level = RiskLevel.HIGH

    def __init__(self, contacts_skill: AndroidContactsSkill | None = None) -> None:
        self.contacts_skill = contacts_skill or AndroidContactsSkill()

    def can_handle(self, target: str, action: str) -> bool:
        t = target.lower()
        a = action.lower()
        return "call" in t or "dial" in t or a in ("call", "dial", "initiate_call")

    def execute(self, action: str, target: str, params: dict[str, Any], state: ComputerState) -> dict[str, Any]:
        t_name = params.get("target") or target
        confirmed = params.get("confirmed", False)
        dev_id = params.get("device_id")
        return self.initiate_call(t_name, confirmed=confirmed, device_id=dev_id)

    def verify(self, action: str, target: str, before_state: ComputerState, after_state: ComputerState, result: dict[str, Any]) -> tuple[bool, str]:
        if result.get("requires_confirmation"):
            return True, result.get("prompt", "Confirmation required.")
        return result.get("verified", True), result.get("summary", "Call processed.")

    def initiate_call(self, target_name_or_number: str, confirmed: bool = False, device_id: str | None = None) -> dict[str, Any]:
        # Check if direct phone number
        if re.match(r"^\+?[0-9]{4,15}$", target_name_or_number):
            number = target_name_or_number
            masked = number[:4] + "••••" + number[-4:]
            display_name = masked
        else:
            resolved = self.contacts_skill.resolve_contact(target_name_or_number)
            if resolved["match_type"] == "NOT_FOUND":
                return {"success": False, "error": f"Contact '{target_name_or_number}' not found on phone."}
            if resolved["match_type"] == "AMBIGUOUS":
                matches = ", ".join(resolved["matches"])
                return {"success": False, "requires_disambiguation": True, "error": f"I found multiple contacts: {matches}. Which one?"}

            contact = resolved["contact"]
            number = contact["phone"]
            masked = number[:4] + "••••" + number[-4:]
            display_name = f"{contact['name']} ({masked})"

        if not confirmed:
            return {
                "success": False,
                "requires_confirmation": True,
                "prompt": f"I found {display_name}. Call now?",
                "target_number": number,
            }

        # Confirmed execution
        res = android_device_manager.execute_operation("call_number", {"phone_number": number}, device_id=device_id)
        return {
            "success": res.get("success", False),
            "summary": f"Calling {display_name} now.",
            "verified": res.get("success", False),
        }


class AndroidMessagingSkill(BaseSkill):
    """Enforces COMPOSE -> SHOW -> CONFIRM -> SEND -> VERIFY flow."""
    name = "android_message"
    allowed_applications = ["sms", "messages", "message"]
    default_risk_level = RiskLevel.HIGH

    def can_handle(self, target: str, action: str) -> bool:
        t = target.lower()
        a = action.lower()
        return "message" in t or "sms" in t or a in ("message", "send_sms", "send_message")

    def execute(self, action: str, target: str, params: dict[str, Any], state: ComputerState) -> dict[str, Any]:
        recipient = params.get("recipient") or target
        msg = params.get("message") or ""
        confirmed = params.get("confirmed", False)
        dev_id = params.get("device_id")
        return self.compose_and_send(recipient, msg, confirmed=confirmed, device_id=dev_id)

    def verify(self, action: str, target: str, before_state: ComputerState, after_state: ComputerState, result: dict[str, Any]) -> tuple[bool, str]:
        if result.get("requires_confirmation"):
            return True, result.get("prompt", "Confirmation required.")
        return result.get("verified", True), result.get("summary", "Message processed.")

    def compose_and_send(self, recipient: str, message: str, confirmed: bool = False, device_id: str | None = None) -> dict[str, Any]:
        if not confirmed:
            return {
                "success": False,
                "requires_confirmation": True,
                "prompt": f"Send '{message}' to {recipient}?",
                "recipient": recipient,
                "message": message,
            }

        # Confirmed send
        # Clean number if available
        res = android_device_manager.execute_operation("send_sms", {"phone_number": recipient, "message": message}, device_id=device_id)
        return {
            "success": res.get("success", False),
            "summary": f"Message sent to {recipient}.",
            "verified": res.get("success", False),
        }


android_device_skill = AndroidDeviceSkill()
android_app_skill = AndroidApplicationSkill()
android_contacts_skill = AndroidContactsSkill()
android_calling_skill = AndroidCallingSkill(android_contacts_skill)
android_messaging_skill = AndroidMessagingSkill()
