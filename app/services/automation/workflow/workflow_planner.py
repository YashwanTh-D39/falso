"""
Workflow Planner Service for FALSO (FALSO 4.8).

Deconstructs multi-step web and automation goals into dynamic adaptive workflow plans.
Handles idempotency checking, step dependencies, and cybersecurity diagnostic workflow preparation.
"""

from __future__ import annotations

import logging
import re
from typing import Any, Dict, List, Optional

from app.services.automation.workflow.workflow_models import (
    BrowserContextState,
    WorkflowStep,
    WorkflowStepState,
)

logger = logging.getLogger(__name__)


class WorkflowPlanner:
    """Planner creating dynamic, idempotent, precondition-aware WorkflowSteps."""

    def plan_workflow(
        self,
        goal: str,
        context: Optional[BrowserContextState] = None,
        session_id: Optional[str] = None,
        workflow_id: str = ""
    ) -> List[WorkflowStep]:
        """Decompose natural language goal into sequential WorkflowSteps."""
        goal_lower = goal.lower().strip()
        steps: List[WorkflowStep] = []
        step_id = 1
        ctx = context or BrowserContextState()
        w_id = workflow_id or "WORKFLOW-PLAN"

        # ── 1. CYBERSECURITY DIAGNOSTIC WORKFLOW INTENT ──
        if any(k in goal_lower for k in ("cybersecurity", "security scan", "diagnostic", "network state")):
            steps.append(WorkflowStep(
                workflow_id=w_id,
                step_id=step_id,
                action_id=f"ACT-{step_id}",
                action="read_page",
                target="Network State & Security Overview",
                capability="browser.read_form",
                description="Observe network state and active security parameters",
            ))
            step_id += 1
            steps.append(WorkflowStep(
                workflow_id=w_id,
                step_id=step_id,
                action_id=f"ACT-{step_id}",
                action="read_page",
                target="Diagnostic Tool Collector",
                capability="browser.read_form",
                description="Collect diagnostic results from approved defensive security tools",
                dependencies=[1],
            ))
            return steps

        # ── 2. GENERAL BROWSER & FORM MULTI-STEP WORKFLOW ──
        # Check Open Browser Idempotency
        if "chrome" in goal_lower or "browser" in goal_lower or "github.com" in goal_lower or "google.com" in goal_lower:
            if not ctx.current_url or ctx.current_url == "about:blank":
                steps.append(WorkflowStep(
                    workflow_id=w_id,
                    step_id=step_id,
                    action_id=f"ACT-{step_id}",
                    action="open_browser",
                    target="Chrome",
                    capability="browser.open",
                    description="Launch or focus browser",
                ))
                step_id += 1

        # Check New Tab Idempotency
        if "new tab" in goal_lower:
            steps.append(WorkflowStep(
                workflow_id=w_id,
                step_id=step_id,
                action_id=f"ACT-{step_id}",
                action="new_tab",
                target="New Tab",
                capability="browser.interact",
                description="Open a new browser tab",
            ))
            step_id += 1

        # Check Navigation Idempotency
        if "go to" in goal_lower or "github.com" in goal_lower or "google.com" in goal_lower or "example.com" in goal_lower or "navigate" in goal_lower or "test form" in goal_lower:
            target_url = "https://www.google.com"
            if "github.com" in goal_lower:
                target_url = "https://github.com"
            elif "example.com" in goal_lower:
                target_url = "https://example.com"
            elif "test form" in goal_lower:
                target_url = "http://127.0.0.1:8000/test_form"
            elif "go to " in goal_lower:
                target_url = goal_lower.split("go to ", 1)[1].strip()
                if not target_url.startswith("http"):
                    target_url = f"https://{target_url}"

            # Idempotency: skip navigation if already on target URL
            if ctx.current_url and target_url.lower() in ctx.current_url.lower():
                logger.info("[WORKFLOW][PLAN] Idempotency: Already on URL '%s', skipping navigation.", target_url)
            else:
                steps.append(WorkflowStep(
                    workflow_id=w_id,
                    step_id=step_id,
                    action_id=f"ACT-{step_id}",
                    action="navigate",
                    target=target_url,
                    capability="browser.navigate",
                    description=f"Navigate browser to {target_url}",
                ))
                step_id += 1

        # Check Search
        if "search" in goal_lower:
            query = "FALSO"
            if "search for " in goal_lower:
                query = goal_lower.split("search for ", 1)[1].strip()
            elif "search " in goal_lower:
                query = goal_lower.split("search ", 1)[1].strip()

            steps.append(WorkflowStep(
                workflow_id=w_id,
                step_id=step_id,
                action_id=f"ACT-{step_id}",
                action="search",
                target=query,
                capability="browser.navigate",
                description=f"Search Google for '{query}'",
            ))
            step_id += 1

        # Check Form Filling
        if "fill" in goal_lower and "form" in goal_lower:
            steps.append(WorkflowStep(
                workflow_id=w_id,
                step_id=step_id,
                action_id=f"ACT-{step_id}",
                action="fill_form",
                target="Form",
                capability="browser.fill_safe_field",
                description="Fill web form fields",
            ))
            step_id += 1

        # Check Form Submission
        if "submit" in goal_lower or ("fill" in goal_lower and "form" in goal_lower and "submit" in goal_lower):
            steps.append(WorkflowStep(
                workflow_id=w_id,
                step_id=step_id,
                action_id=f"ACT-{step_id}",
                action="submit_form",
                target="Form",
                capability="browser.submit_form",
                requires_confirmation=True,
                description="Submit filled form (requires user confirmation)",
                dependencies=[step_id - 1] if step_id > 1 else [],
            ))
            step_id += 1

        # Fallback if no specific step matched
        if not steps:
            steps.append(WorkflowStep(
                workflow_id=w_id,
                step_id=1,
                action_id="ACT-1",
                action="open_browser",
                target="Chrome",
                capability="browser.open",
                description="Open browser",
            ))

        return steps


workflow_planner = WorkflowPlanner()
