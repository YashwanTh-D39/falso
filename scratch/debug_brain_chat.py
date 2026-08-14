import asyncio
import json
import logging

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")

async def test_brain_chat():
    from app.services.brain import BrainService

    brain = BrainService()
    print("\n--- TEST: BrainService.chat('FALSO open Chrome') ---")
    chunks = []
    async for chunk in brain.chat("FALSO open Chrome", request_id="TEST-VOICE-CHROME"):
        chunks.append(chunk)
        print(f"CHUNK: {chunk!r}")

    full_text = "".join(chunks)
    print(f"\nFULL STREAM OUTPUT:\n{full_text}")

if __name__ == "__main__":
    asyncio.run(test_brain_chat())
