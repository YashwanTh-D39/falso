import audioop
import os
import wave
from pathlib import Path

# Create logs/tts_debug directory
debug_dir = Path("logs/tts_debug")
debug_dir.mkdir(parents=True, exist_ok=True)

print(f"Debug directory created: {debug_dir.resolve()}")
