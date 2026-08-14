"""
FALSO 4.11 Defensive MITRE ATT&CK Mapping Layer.

Provides analytical reference mapping for observed defensive security findings.
IMPORTANT: This layer is strictly analytical and NEVER triggers offensive operations.

Evidence Grounding Labels:
- SUPPORTED: Direct observed evidence confirms behavior
- POTENTIAL: Correlated signals suggest potential technique
- NOT ENOUGH EVIDENCE: Superficial or ambiguous match
"""

from __future__ import annotations

from dataclasses import dataclass
import enum
from typing import Any


class MitreEvidenceGrounding(enum.Enum):
    SUPPORTED = "SUPPORTED"
    POTENTIAL = "POTENTIAL"
    NOT_ENOUGH_EVIDENCE = "NOT ENOUGH EVIDENCE"


@dataclass
class MitreTechniqueMapping:
    technique_id: str
    technique_name: str
    tactic: str
    grounding: MitreEvidenceGrounding
    explanation: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "technique_id": self.technique_id,
            "technique_name": self.technique_name,
            "tactic": self.tactic,
            "grounding": self.grounding.value,
            "explanation": self.explanation,
        }


class MitreMapper:
    """Maps defensive findings to MITRE ATT&CK references."""

    @staticmethod
    def map_finding(category: str, evidence: dict[str, Any]) -> MitreTechniqueMapping | None:
        cat_low = category.lower()

        if "port" in cat_low or "socket" in cat_low:
            return MitreTechniqueMapping(
                technique_id="T1049",
                technique_name="System Network Connections Discovery",
                tactic="Discovery",
                grounding=MitreEvidenceGrounding.SUPPORTED,
                explanation="Local listening port inspection corresponds to network connection observation.",
            )

        if "process" in cat_low:
            return MitreTechniqueMapping(
                technique_id="T1057",
                technique_name="Process Discovery",
                tactic="Discovery",
                grounding=MitreEvidenceGrounding.SUPPORTED,
                explanation="Process enumeration corresponds to system process discovery.",
            )

        if "route" in cat_low or "interface" in cat_low:
            return MitreTechniqueMapping(
                technique_id="T1016",
                technique_name="System Network Configuration Discovery",
                tactic="Discovery",
                grounding=MitreEvidenceGrounding.SUPPORTED,
                explanation="Interface and routing enumeration corresponds to network configuration inspection.",
            )

        if "http" in cat_low:
            return MitreTechniqueMapping(
                technique_id="T1071.001",
                technique_name="Web Protocols",
                tactic="Command and Control",
                grounding=MitreEvidenceGrounding.POTENTIAL,
                explanation="HTTP/HTTPS communication analysis.",
            )

        return None


mitre_mapper = MitreMapper()
