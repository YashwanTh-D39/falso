import asyncio
import logging
import sys

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")

async def test_automation():
    from app.services.automation.autopilot import autopilot_agent
    from app.services.brain import BrainService, is_automation_intent

    print("\n--- TEST 1: Intent Classification ---")
    prompts = ["open chrome", "FALSO open Chrome", "FALSO, open Chrome", "open Chrome"]
    for p in prompts:
        print(f"Prompt: {p!r} -> is_automation_intent = {is_automation_intent(p)}")

    print("\n--- TEST 2: Run Goal 'open chrome' ---")
    res1 = await autopilot_agent.run_goal("open chrome", task_id="DEBUG-01")
    print(f"Result for 'open chrome': {res1!r}")

    print("\n--- TEST 3: Run Goal 'FALSO open Chrome' ---")
    res2 = await autopilot_agent.run_goal("FALSO open Chrome", task_id="DEBUG-02")
    print(f"Result for 'FALSO open Chrome': {res2!r}")

if __name__ == "__main__":
    asyncio.run(test_automation())
