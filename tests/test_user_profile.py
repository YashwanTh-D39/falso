"""Unit tests for UserProfileService."""

import pytest
from pathlib import Path
from app.services.user_profile import UserProfileService


def test_user_profile_service_load_and_update(tmp_path: Path):
    profile_file = tmp_path / "user_profile.json"
    service = UserProfileService(file_path=profile_file)

    p = service.get_profile()
    assert p["name"] == "Yashwanth"

    service.update_profile({"name": "Yashwanth D", "coding_style": "Pythonic, concise"})
    updated = service.get_profile()
    assert updated["name"] == "Yashwanth D"
    assert updated["coding_style"] == "Pythonic, concise"

    summary = service.format_summary_for_prompt()
    assert "Yashwanth D" in summary
