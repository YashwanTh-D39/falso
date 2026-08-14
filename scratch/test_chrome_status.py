import logging

logging.basicConfig(level=logging.INFO)

def check_chrome():
    from app.services.automation.windows.process_manager import process_manager
    from app.services.automation.windows.window_manager import window_manager

    print("--- PROCESS & WINDOW STATUS ---")
    proc_running = process_manager.is_process_running("chrome")
    win_open = window_manager.is_window_open("chrome")
    print(f"process_manager.is_process_running('chrome'): {proc_running}")
    print(f"window_manager.is_window_open('chrome'): {win_open}")

    # Check executable paths
    import os
    paths = [
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
        os.path.expandvars(r"%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe"),
    ]
    for p in paths:
        print(f"Path {p}: exists={os.path.exists(p)}")

if __name__ == "__main__":
    check_chrome()
