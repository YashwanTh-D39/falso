"""
Real Windows Control Package for FALSO.
Exposes WindowManager, ProcessManager, KeyboardController, MouseController,
UIAutomation, ScreenObserver, BrowserController, and WindowsExecutor.
"""

from app.services.automation.windows.browser_controller import browser_controller, BrowserController
from app.services.automation.windows.executor import windows_executor, WindowsExecutor
from app.services.automation.windows.keyboard_controller import keyboard_controller, KeyboardController
from app.services.automation.windows.mouse_controller import mouse_controller, MouseController
from app.services.automation.windows.process_manager import process_manager, ProcessManager
from app.services.automation.windows.screen_observer import screen_observer, ScreenObserver
from app.services.automation.windows.ui_automation import ui_automation, UIAutomation
from app.services.automation.windows.window_manager import window_manager, WindowManager

__all__ = [
    "windows_executor",
    "WindowsExecutor",
    "window_manager",
    "WindowManager",
    "process_manager",
    "ProcessManager",
    "keyboard_controller",
    "KeyboardController",
    "mouse_controller",
    "MouseController",
    "ui_automation",
    "UIAutomation",
    "screen_observer",
    "ScreenObserver",
    "browser_controller",
    "BrowserController",
]
