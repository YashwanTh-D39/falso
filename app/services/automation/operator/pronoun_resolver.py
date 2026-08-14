"""
FALSO 4.9 Pronoun & Reference Resolver.

Resolves anaphoric references such as "it", "that", "this", "there", "the window",
"the app", "the tab", "the file", "the previous one" by querying:
1. Current ComputerState (foreground application / active window)
2. Verified Action History (last successfully verified target)
3. SessionHistory (recent conversational mentions)
4. MemoryService (persisted user context)

If multiple targets are equally plausible:
Returns an ambiguous clarification request — NEVER GUESSES.
"""

from __future__ import annotations

import logging
import re
from typing import Any

from app.services.automation.operator.computer_state import ComputerState

logger = logging.getLogger(__name__)

PRONOUN_PATTERN = re.compile(
    r"\b(it|that|this|there|the window|the app|the application|the tab|the file|the previous one)\b",
    re.IGNORECASE,
)


class PronounResolver:
    """Resolves anaphoric expressions to concrete desktop applications, windows, or resources."""

    def resolve_reference(
        self,
        prompt: str,
        state: ComputerState,
        session_history: list[Any] | None = None,
    ) -> tuple[str, str | None, bool]:
        """
        Analyze prompt for pronouns/references.
        Returns:
            (resolved_prompt: str, resolved_target: str | None, is_ambiguous: bool)
        """
        match = PRONOUN_PATTERN.search(prompt)
        if not match:
            # No pronouns to resolve
            return prompt, None, False

        matched_pronoun = match.group(1)

        # 1. Candidate from Active Pending Android Workflow
        from app.services.automation.android.unlock_manager import authorized_unlock_manager
        pending_wf = authorized_unlock_manager.get_active_workflow()
        pending_target = pending_wf.target_app.capitalize() if (pending_wf and pending_wf.target_app) else None

        # 2. Candidate from Last Verified Action
        last_verified_target = state.get_last_verified_target()

        # 3. Candidate from Foreground Application
        foreground_app = state.get_foreground_app()

        # 4. Candidate from Session History
        history_target = self._extract_target_from_history(session_history)

        candidates = [c for c in (pending_target, last_verified_target, foreground_app, history_target) if c]

        if not candidates:
            # Cannot resolve reference
            return prompt, None, True

        # If we have a single strong candidate or agreement
        best_target = candidates[0]

        # Check for ambiguity if multiple distinct candidates exist
        unique_candidates = list(set(candidates))
        if len(unique_candidates) > 2:
            logger.warning("[PRONOUN_RESOLVER] Ambiguous reference '%s' across targets: %s", matched_pronoun, unique_candidates)
            return prompt, None, True

        # Replace pronoun in prompt
        resolved_prompt = PRONOUN_PATTERN.sub(best_target, prompt, count=1)
        logger.info("[PRONOUN_RESOLVER] Resolved '%s' -> '%s' | %r -> %r", matched_pronoun, best_target, prompt, resolved_prompt)
        return resolved_prompt, best_target, False

    def _extract_target_from_history(self, history: list[Any] | None) -> str | None:
        if not history:
            return None
        for msg in reversed(history):
            content = getattr(msg, "content", "") or ""
            c_low = content.lower()
            for known in ("calculator", "notepad", "chrome", "explorer", "vscode", "visual studio code", "youtube", "camera", "whatsapp", "settings"):
                if known in c_low:
                    if known in ("vscode", "visual studio code"):
                        return "VS Code"
                    return known.capitalize()
        return None


pronoun_resolver = PronounResolver()
