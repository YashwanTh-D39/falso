# Importing the submodules executes their @register_personality decorators,
# so importing this package registers every built-in personality.
from app.personality.personalities.default import DefaultPersonality
from app.personality.personalities.friendly import FriendlyPersonality
from app.personality.personalities.jarvis import JarvisPersonality
from app.personality.personalities.minimal import MinimalPersonality
from app.personality.personalities.technician import TechnicianPersonality
from app.personality.personalities.ultron import UltronPersonality

__all__ = [
    "DefaultPersonality",
    "FriendlyPersonality",
    "JarvisPersonality",
    "MinimalPersonality",
    "TechnicianPersonality",
    "UltronPersonality",
]