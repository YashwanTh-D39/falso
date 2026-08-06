"""REST API routes for User Profile management."""

from __future__ import annotations

import logging
from typing import Any, Dict

from fastapi import APIRouter
from pydantic import BaseModel

from app.services.user_profile import user_profile_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/profile", tags=["User Profile"])


class ProfileUpdateRequest(BaseModel):
    name: str | None = None
    preferences: Dict[str, Any] | None = None
    projects: list[str] | None = None
    coding_style: str | None = None
    daily_routine: str | None = None
    favorite_apps: list[str] | None = None
    common_folders: list[str] | None = None
    frequently_used_websites: list[str] | None = None
    devices: list[str] | None = None
    goals: list[str] | None = None


@router.get("/")
async def get_profile():
    """Returns full structured user profile."""
    return user_profile_service.get_profile()


@router.put("/")
async def update_profile(request: ProfileUpdateRequest):
    """Updates fields in user profile."""
    updates = request.model_dump(exclude_unset=True)
    updated = user_profile_service.update_profile(updates)
    return updated
