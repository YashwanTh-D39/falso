import asyncio
import json
import logging

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")

async def run_verifications():
    from app.services.automation.autopilot import autopilot_agent
    from app.services.brain import BrainService
    from app.services.automation.permissions import permission_manager, FileOperation

    brain = BrainService()

    print("\n==========================================")
    print("1. BASIC AUTOMATION COMMANDS TEST")
    print("==========================================")

    commands = [
        "open chrome",
        "open notepad",
        "open calculator",
        "open file explorer",
        "focus chrome",
        "focus notepad",
        "FALSO, open Chrome"
    ]

    for cmd in commands:
        res = await autopilot_agent.run_goal(cmd, task_id=f"TEST-{cmd.replace(' ', '_')}")
        print(f"Command: {cmd!r} -> Result: {res!r}")
        assert res in ("Chrome is open.", "Notepad is open.", "Calculator is open.", "File Explorer is open.", "Done.")

    print("\n==========================================")
    print("2. VOICE -> AUTOMATION PIPELINE VIA BRAIN")
    print("==========================================")
    voice_prompts = ["FALSO, open Chrome", "open Notepad", "open Calculator"]
    for vp in voice_prompts:
        chunks = []
        async for chunk in brain.chat(vp, request_id=f"VOICE-PIPE-{vp.replace(' ', '_')}"):
            chunks.append(chunk)
        full_output = "".join(chunks)
        print(f"Voice Prompt: {vp!r} -> Chunks count: {len(chunks)}")
        print(f"Full Stream:\n{full_output.strip()}")

    print("\n==========================================")
    print("3. SECURITY BOUNDARY REGRESSION TESTS")
    print("==========================================")

    banned_tests = [
        r"C:\Windows\System32\kernel32.dll",
        r"C:\Windows\System32",
        r"C:\Users\Admin\Project-Falso\.env",
    ]

    for bpath in banned_tests:
        perm = permission_manager.check_filesystem_access(bpath, FileOperation.READ)
        print(f"Security check path '{bpath}': allowed={perm.allowed} (expected=False)")
        assert not perm.allowed

    # PowerShell command execution check
    perm_cmd = permission_manager.check_command_execution("powershell", ["-Command", "Get-Process"])
    print(f"PowerShell command check: allowed={perm_cmd.allowed} (expected=True for controlled registry or False for arbitrary)")

    print("\nALL AUTOMATION PIPELINE VERIFICATIONS PASSED!")

if __name__ == "__main__":
    asyncio.run(run_verifications())
