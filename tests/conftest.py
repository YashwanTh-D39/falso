from __future__ import annotations

import os
from pathlib import Path

import pytest

# Ensure test flag is set unconditionally
os.environ["FALSO_TESTING"] = "1"


@pytest.fixture(autouse=True)
def protect_real_env():
    """Autouse fixture ensuring that tests NEVER mutate the real root .env file on disk."""
    env_path = Path(".env")
    initial_content = env_path.read_text(encoding="utf-8") if env_path.is_file() else None

    yield

    if env_path.is_file():
        current_content = env_path.read_text(encoding="utf-8")
        if initial_content is not None and current_content != initial_content:
            # Restore immediately
            env_path.write_text(initial_content, encoding="utf-8")
            pytest.fail("TEST ISOLATION VIOLATION: A test mutated the real root .env file on disk!")
