"""
FALSO 4.11 Confidence Engine.

Calculates confidence scores for security observations, detections, and findings:
- VERY_LOW
- LOW
- MEDIUM
- HIGH
- VERY_HIGH

Evaluates:
- Number of independent evidence sources
- Quality of observation (verified vs unverified)
- Correlation strength (e.g. Socket matched to PID and Process Name)
- Baseline consistency and observation history
"""

from __future__ import annotations

import enum
from typing import Any


class ConfidenceScore(enum.Enum):
    VERY_LOW = "VERY_LOW"
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    VERY_HIGH = "VERY_HIGH"

    @property
    def score_value(self) -> float:
        mapping = {
            "VERY_LOW": 0.2,
            "LOW": 0.4,
            "MEDIUM": 0.6,
            "HIGH": 0.8,
            "VERY_HIGH": 1.0,
        }
        return mapping.get(self.value, 0.5)


class ConfidenceEngine:
    """Computes evidence-backed confidence scores."""

    @staticmethod
    def calculate_confidence(
        evidence_sources_count: int,
        is_verified: bool,
        correlation_depth: int = 1,
        has_baseline_history: bool = False,
    ) -> ConfidenceScore:
        """
        Compute confidence score:
        - 1 source, unverified -> LOW / VERY_LOW
        - 1 source, verified -> MEDIUM
        - 2+ sources, verified, correlated -> HIGH
        - Multiple independent sources + baseline history -> VERY_HIGH
        """
        points = 0.0

        if is_verified:
            points += 0.4
        else:
            points += 0.1

        if evidence_sources_count >= 2:
            points += 0.3
        elif evidence_sources_count == 1:
            points += 0.1

        if correlation_depth >= 2:
            points += 0.2

        if has_baseline_history:
            points += 0.1

        if points >= 0.85:
            return ConfidenceScore.VERY_HIGH
        if points >= 0.65:
            return ConfidenceScore.HIGH
        if points >= 0.45:
            return ConfidenceScore.MEDIUM
        if points >= 0.25:
            return ConfidenceScore.LOW
        return ConfidenceScore.VERY_LOW


confidence_engine = ConfidenceEngine()
