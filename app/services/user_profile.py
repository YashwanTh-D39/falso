"""Structured User Profile Service for FALSO Personal AI Companion.

Stores core user identity, preferences, routines, favorite tools, and goals locally
in `data/user_profile.json` so FALSO never asks for known information repeatedly.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

PROFILE_PATH = Path("data/user_profile.json")

DEFAULT_PROFILE: Dict[str, Any] = {
    "name": "Yashwanth",
    "preferences": {
        "language": "English",
        "verbosity": "concise",
        "tone": "helpful, natural, companion-like",
    },
    "projects": ["Project-Falso"],
    "coding_style": "Clean modular code, Python type hints, modern HTML5/JS",
    "daily_routine": "Coding, AI research, testing local models",
    "favorite_apps": ["VS Code", "Chrome", "Terminal", "Explorer"],
    "common_folders": [
        "c:/Users/Admin/Project-Falso",
        "c:/Users/Admin/Downloads",
        "c:/Users/Admin/Desktop"
    ],
    "frequently_used_websites": ["github.com", "duckduckgo.com"],
    "devices": ["Windows PC"],
    "goals": [
        "Build FALSO Spatial AI Companion",
        "Optimize local LLM voice response latency"
    ],
    "preferred_city": "Visakhapatnam",
    "interaction_mode": "voice_only"
}


class UserProfileService:
    def __init__(self, file_path: Path = PROFILE_PATH) -> None:
        self.file_path = file_path
        self.profile: Dict[str, Any] = self._load()

    def _load(self) -> Dict[str, Any]:
        if not self.file_path.exists():
            self.file_path.parent.mkdir(parents=True, exist_ok=True)
            self._save_to_disk(DEFAULT_PROFILE)
            return dict(DEFAULT_PROFILE)

        try:
            with open(self.file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                # Merge defaults for any missing key
                for k, v in DEFAULT_PROFILE.items():
                    if k not in data:
                        data[k] = v
                return data
        except Exception as exc:
            logger.warning("Failed to load user profile from %s (%s). Using defaults.", self.file_path, exc)
            return dict(DEFAULT_PROFILE)

    def _save_to_disk(self, data: Dict[str, Any]) -> None:
        try:
            self.file_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self.file_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
        except Exception as exc:
            logger.error("Failed to save user profile to %s: %s", self.file_path, exc)

    def get_profile(self) -> Dict[str, Any]:
        return dict(self.profile)

    def update_profile(self, updates: Dict[str, Any]) -> Dict[str, Any]:
        for k, v in updates.items():
            if k in self.profile and isinstance(self.profile[k], dict) and isinstance(v, dict):
                self.profile[k].update(v)
            else:
                self.profile[k] = v
        self._save_to_disk(self.profile)
        return dict(self.profile)

    def add_list_item(self, field_name: str, item: str) -> None:
        if field_name in self.profile and isinstance(self.profile[field_name], list):
            if item not in self.profile[field_name]:
                self.profile[field_name].append(item)
                self._save_to_disk(self.profile)

    def format_summary_for_prompt(self) -> str:
        """Formats structured user profile for system prompt context injection."""
        p = self.profile
        lines = [
            f"User Name: {p.get('name', 'User')}",
            f"Preferred Style: {p.get('coding_style', 'Clean, modern code')}",
            f"Active Projects: {', '.join(p.get('projects', []))}",
            f"Goals: {', '.join(p.get('goals', []))}",
            f"Favorite Apps: {', '.join(p.get('favorite_apps', []))}",
            f"Common Folders: {', '.join(p.get('common_folders', []))}"
        ]
        return "\n".join(lines)


user_profile_service = UserProfileService()
