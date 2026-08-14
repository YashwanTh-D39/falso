"""
Windows Keyboard Controller Service for FALSO.

Uses native Win32 API via ctypes keybd_event to simulate structured typing and hotkeys.
"""

from __future__ import annotations

import ctypes
import logging
import time

logger = logging.getLogger(__name__)

user32 = ctypes.windll.user32

KEYEVENTF_KEYUP = 0x0002

# Standard Win32 Virtual Key Map
VK_MAP: dict[str, int] = {
    "BACKSPACE": 0x08,
    "TAB": 0x09,
    "ENTER": 0x0D,
    "RETURN": 0x0D,
    "SHIFT": 0x10,
    "CTRL": 0x11,
    "CONTROL": 0x11,
    "ALT": 0x12,
    "PAUSE": 0x13,
    "CAPSLOCK": 0x14,
    "ESC": 0x1B,
    "ESCAPE": 0x1B,
    "SPACE": 0x20,
    "PAGEUP": 0x21,
    "PAGEDOWN": 0x22,
    "END": 0x23,
    "HOME": 0x24,
    "LEFT": 0x25,
    "UP": 0x26,
    "RIGHT": 0x27,
    "DOWN": 0x28,
    "DELETE": 0x2E,
}


class KeyboardController:
    """Native Win32 Keyboard Controller."""

    def _get_vk(self, key_name: str) -> int:
        clean = key_name.upper().strip()
        if clean in VK_MAP:
            return VK_MAP[clean]
        if len(clean) == 1:
            char_code = ord(clean)
            if 65 <= char_code <= 90:  # A-Z
                return char_code
            if 48 <= char_code <= 57:  # 0-9
                return char_code
        logger.warning("[KEYBOARD] Unrecognized key: %r — rejecting", key_name)
        return 0

    def press_key(self, key_name: str) -> bool:
        """Simulate single key down + key up."""
        vk = self._get_vk(key_name)
        if not vk:
            return False
        user32.keybd_event(vk, 0, 0, 0)
        time.sleep(0.02)
        user32.keybd_event(vk, 0, KEYEVENTF_KEYUP, 0)
        return True

    def send_hotkey(self, keys: list[str]) -> bool:
        """Simulate hotkey combination (e.g. ['CTRL', 'L'] or ['ALT', 'TAB'])."""
        vks = [self._get_vk(k) for k in keys if self._get_vk(k)]
        if not vks:
            return False

        # Press down in order
        for vk in vks:
            user32.keybd_event(vk, 0, 0, 0)
            time.sleep(0.01)

        time.sleep(0.05)

        # Release in reverse order
        for vk in reversed(vks):
            user32.keybd_event(vk, 0, KEYEVENTF_KEYUP, 0)
            time.sleep(0.01)

        logger.info("[KEYBOARD] Sent hotkey combo: %s", keys)
        return True

    def type_text(self, text: str) -> bool:
        """Type characters sequentially into active focused window."""
        logger.info("[KEYBOARD] Typing text: %r", text)
        for char in text:
            if char == '\n':
                self.press_key("ENTER")
            elif char == '\t':
                self.press_key("TAB")
            else:
                vk = user32.VkKeyScanW(ord(char)) & 0xFF
                shift = (user32.VkKeyScanW(ord(char)) >> 8) & 1
                if shift:
                    user32.keybd_event(0x10, 0, 0, 0)  # Shift down
                user32.keybd_event(vk, 0, 0, 0)
                time.sleep(0.01)
                user32.keybd_event(vk, 0, KEYEVENTF_KEYUP, 0)
                if shift:
                    user32.keybd_event(0x10, 0, KEYEVENTF_KEYUP, 0)  # Shift up
            time.sleep(0.01)
        return True


keyboard_controller = KeyboardController()
