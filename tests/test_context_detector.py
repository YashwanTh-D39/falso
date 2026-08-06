"""Unit tests for ContextDetectorService."""

import pytest
from app.services.context_detector import context_detector


def test_context_detector_detection():
    ctx = context_detector.detect_context()
    assert "current_project" in ctx
    assert "current_folder" in ctx
    assert "running_ide" in ctx
    assert "git_branch" in ctx

    summary = context_detector.format_summary_for_prompt()
    assert "Active Project" in summary
