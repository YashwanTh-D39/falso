"""Text cleaning module for TTS speech synthesis.

Strips URLs, markdown formatting, HTML tags, API metadata, source citations,
slashes, backslashes, and non-conversational symbols so TTS engines receive
only natural human spoken language.
"""

from __future__ import annotations

import re


def clean_text_for_speech(text: str) -> str:
    """Cleans raw text response for natural TTS vocalization."""
    if not text:
        return ""

    # 1. Remove URLs (http, https, www)
    cleaned = re.sub(r'https?://\S+|www\.\S+', '', text)

    # 2. Convert markdown links [title](url) -> title
    cleaned = re.sub(r'\[([^\]]+)\]\([^)]+\)', r'\1', cleaned)

    # 3. Strip Source metadata, timestamps, and confidence ratings
    cleaned = re.sub(r'(?:Source|Retrieved|Confidence|Map Link):\s*\S+', '', cleaned, flags=re.IGNORECASE)

    # 4. Remove HTML tags
    cleaned = re.sub(r'<[^>]+>', '', cleaned)

    # 5. Remove Code blocks & inline code backticks
    cleaned = re.sub(r'```[\s\S]*?```', '', cleaned)
    cleaned = re.sub(r'`[^`]+`', '', cleaned)

    # 6. Remove Markdown symbols: *, #, _, ~, >, |, [, ], (, ), +, =
    cleaned = re.sub(r'[*#_~>|\[\]()+=]', ' ', cleaned)

    # 7. Clean slashes, backslashes, dashes, and repeated dots
    cleaned = re.sub(r'[/\\–—\-]+', ' ', cleaned)
    cleaned = re.sub(r'\.{2,}', '.', cleaned)

    # 8. Normalize degree symbols for natural speech (e.g., 28°C -> 28 degrees Celsius)
    cleaned = re.sub(r'(\d+)\s*°\s*C\b', r'\1 degrees Celsius', cleaned)
    cleaned = re.sub(r'(\d+)\s*°\s*F\b', r'\1 degrees Fahrenheit', cleaned)
    cleaned = re.sub(r'(\d+)\s*°', r'\1 degrees', cleaned)

    # 9. Collapse multiple spaces and return clean natural speech string
    cleaned = re.sub(r'\s+', ' ', cleaned).strip()
    return cleaned
