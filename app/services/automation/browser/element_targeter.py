"""
Semantic Element Targeter for FALSO (FALSO 4.6 & 4.7).

Resolves interactive elements by accessible role, label, name, placeholder, ID, or text.
"""

from __future__ import annotations

import logging
from typing import List, Optional
from app.services.automation.browser.page_observation import ElementRole, ElementSnapshot, PageSnapshot

logger = logging.getLogger(__name__)


class SemanticElementTargeter:
    """Targeter resolving natural language targets to structured ElementSnapshots."""

    def find_target_element(
        self,
        snapshot: PageSnapshot,
        target_description: str,
        expected_role: Optional[ElementRole] = None,
    ) -> Optional[ElementSnapshot]:
        """Find best matching element using semantic attributes."""
        if not snapshot.interactive_elements:
            return None

        desc_clean = target_description.lower().strip()
        candidates: List[tuple[int, ElementSnapshot]] = []

        for elem in snapshot.interactive_elements:
            score = 0
            if expected_role and elem.role != expected_role:
                continue

            name_lower = elem.name.lower()
            label_lower = elem.label.lower()
            place_lower = elem.placeholder.lower()
            id_lower = elem.element_id.lower()

            # Exact match (score=100)
            if desc_clean in (name_lower, label_lower, place_lower, id_lower):
                score += 100

            # Substring match (score=50)
            elif any(desc_clean in item for item in (name_lower, label_lower, place_lower, id_lower) if item):
                score += 50

            # Inverse match
            elif any(item in desc_clean for item in (name_lower, label_lower, place_lower, id_lower) if item):
                score += 30

            if score > 0:
                candidates.append((score, elem))

        if not candidates:
            logger.debug("[TARGETER] No semantic element found for target: %r", target_description)
            return None

        candidates.sort(key=lambda x: x[0], reverse=True)
        best = candidates[0][1]
        logger.info("[TARGETER] Resolved target %r -> element role=%s name=%r", target_description, best.role.value, best.name or best.label)
        return best


element_targeter = SemanticElementTargeter()
