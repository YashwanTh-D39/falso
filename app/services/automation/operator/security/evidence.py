"""
FALSO 4.11 Cybersecurity Evidence & Scope Models.

Enforces:
- Explicit SecurityScope (LOCAL_MACHINE, LOCAL_NETWORK, AUTHORIZED_HOST, AUTHORIZED_LAB, AUTHORIZED_DOMAIN, USER_APPROVED_RESOURCE)
- Separate AuthorizationStatus (ALLOWED, DENIED, REQUIRES_AUTHORIZATION)
- EvidenceProvenance tracking source, collection method, timestamp, verification status, and evidence type
- Automatic SecretRedactor masking passwords, API keys, JWT tokens, Bearer headers, Cookies, and .env assignments
- DiagnosticBudget with strict resource and step limits to prevent runaway probing
"""

from __future__ import annotations

from dataclasses import dataclass, field
import enum
import re
import time
from typing import Any

from app.services.automation.operator.computer_state import EvidenceType
from app.services.automation.operator.security.confidence import ConfidenceScore


class SecurityScope(enum.Enum):
    LOCAL_MACHINE = "LOCAL_MACHINE"
    LOCAL_NETWORK = "LOCAL_NETWORK"
    AUTHORIZED_HOST = "AUTHORIZED_HOST"
    AUTHORIZED_LAB = "AUTHORIZED_LAB"
    AUTHORIZED_DOMAIN = "AUTHORIZED_DOMAIN"
    USER_APPROVED_RESOURCE = "USER_APPROVED_RESOURCE"


class AuthorizationStatus(enum.Enum):
    ALLOWED = "ALLOWED"
    DENIED = "DENIED"
    REQUIRES_AUTHORIZATION = "REQUIRES_AUTHORIZATION"


class FindingSeverity(enum.Enum):
    INFO = "INFO"
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


@dataclass
class EvidenceProvenance:
    source: str
    collection_method: str
    timestamp: float = field(default_factory=time.time)
    verification_status: bool = True
    evidence_type: EvidenceType = EvidenceType.OBSERVED
    confidence: ConfidenceScore = ConfidenceScore.HIGH

    def to_dict(self) -> dict[str, Any]:
        return {
            "source": self.source,
            "collection_method": self.collection_method,
            "timestamp": self.timestamp,
            "verification_status": self.verification_status,
            "evidence_type": self.evidence_type.value if hasattr(self.evidence_type, "value") else str(self.evidence_type),
            "confidence": self.confidence.value if hasattr(self.confidence, "value") else str(self.confidence),
        }


@dataclass
class DiagnosticBudget:
    max_steps: int = 10
    max_runtime: float = 30.0
    max_network_requests: int = 15
    max_log_bytes: int = 100_000
    max_output_bytes: int = 50_000
    steps_taken: int = 0
    start_time: float = field(default_factory=time.time)
    network_requests_made: int = 0
    log_bytes_read: int = 0
    output_bytes_generated: int = 0

    def can_step(self) -> bool:
        if self.steps_taken >= self.max_steps:
            return False
        if time.time() - self.start_time >= self.max_runtime:
            return False
        return True

    def can_make_network_request(self) -> bool:
        return self.can_step() and self.network_requests_made < self.max_network_requests

    def record_step(self) -> None:
        self.steps_taken += 1

    def record_network_request(self) -> None:
        self.network_requests_made += 1

    def record_log_bytes(self, byte_count: int) -> bool:
        self.log_bytes_read += byte_count
        return self.log_bytes_read <= self.max_log_bytes

    def record_output_bytes(self, byte_count: int) -> bool:
        self.output_bytes_generated += byte_count
        return self.output_bytes_generated <= self.max_output_bytes


SENSITIVE_HEADER_KEYS = {
    "authorization",
    "cookie",
    "set-cookie",
    "x-api-key",
    "x-auth-token",
    "api-key",
    "bearer",
    "proxy-authorization",
}


class SecretRedactor:
    """Sanitizes text, dictionaries, headers, and logs against credential leaks."""

    @staticmethod
    def redact_text(text: str) -> str:
        if not text or not isinstance(text, str):
            return text
        redacted = text
        # Key-value assignments (API_KEY=..., password: ...)
        redacted = re.sub(
            r"(?i)(api[_-]?key|secret|password|passwd|token|auth|bearer|private[_-]?key)\s*[:=]\s*['\"]?([^'\"\s\r\n]{4,})['\"]?",
            r"\1: [REDACTED_SECRET]",
            redacted,
        )
        # Bearer tokens in text
        redacted = re.sub(
            r"(?i)(authorization:\s*bearer\s+)([a-zA-Z0-9_\-\.]{8,})",
            r"\1[REDACTED_SECRET]",
            redacted,
        )
        # Cookies in text
        redacted = re.sub(
            r"(?i)(set-cookie|cookie):\s*([^;\r\n]+)",
            r"\1: [REDACTED_SECRET]",
            redacted,
        )
        # Private keys
        redacted = re.sub(
            r"(?i)-----BEGIN\s+(?:RSA\s+)?PRIVATE\s+KEY-----[\s\S]+?-----END\s+(?:RSA\s+)?PRIVATE\s+KEY-----",
            "[REDACTED_PRIVATE_KEY]",
            redacted,
        )
        # JWTs
        redacted = re.sub(
            r"(?i)(eyJ[a-zA-Z0-9_\-]{10,}\.[a-zA-Z0-9_\-]{10,}\.[a-zA-Z0-9_\-]{10,})",
            "[REDACTED_JWT]",
            redacted,
        )
        return redacted

    @classmethod
    def redact_dict(cls, data: dict[str, Any]) -> dict[str, Any]:
        if not isinstance(data, dict):
            return data
        clean: dict[str, Any] = {}
        for k, v in data.items():
            k_low = str(k).lower().strip()
            if any(s in k_low for s in ("password", "secret", "token", "key", "cookie", "auth", "credential", "private")):
                clean[k] = "[REDACTED_SECRET]"
            elif isinstance(v, dict):
                clean[k] = cls.redact_dict(v)
            elif isinstance(v, list):
                clean[k] = [cls.redact_dict(item) if isinstance(item, dict) else cls.redact_text(str(item)) for item in v]
            elif isinstance(v, str):
                clean[k] = cls.redact_text(v)
            else:
                clean[k] = v
        return clean

    @classmethod
    def redact_headers(cls, headers: dict[str, Any]) -> dict[str, str]:
        """Redact HTTP headers specifically, stripping authorization, cookies, and tokens."""
        if not isinstance(headers, dict):
            return {}
        clean_headers: dict[str, str] = {}
        for k, v in headers.items():
            k_str = str(k)
            if k_str.lower().strip() in SENSITIVE_HEADER_KEYS:
                clean_headers[k_str] = "[REDACTED_SECRET]"
            else:
                clean_headers[k_str] = cls.redact_text(str(v))
        return clean_headers


@dataclass
class SecurityEvidence:
    finding: str
    target: str
    source: str
    timestamp: float = field(default_factory=time.time)
    evidence: dict[str, Any] = field(default_factory=dict)
    process_info: dict[str, Any] | None = None
    confidence: str = "HIGH"
    severity: FindingSeverity = FindingSeverity.INFO
    verification_status: bool = True
    recommended_next_step: str = ""
    scope: SecurityScope = SecurityScope.LOCAL_MACHINE
    authorization: AuthorizationStatus = AuthorizationStatus.ALLOWED
    provenance: EvidenceProvenance | None = None

    def to_dict(self) -> dict[str, Any]:
        # Always run through SecretRedactor before serialization
        clean_ev = SecretRedactor.redact_dict(self.evidence)
        clean_proc = SecretRedactor.redact_dict(self.process_info) if self.process_info else None
        prov_dict = self.provenance.to_dict() if self.provenance else None
        return {
            "finding": SecretRedactor.redact_text(self.finding),
            "target": self.target,
            "source": self.source,
            "timestamp": self.timestamp,
            "evidence": clean_ev,
            "process_info": clean_proc,
            "confidence": self.confidence,
            "severity": self.severity.value,
            "verification_status": self.verification_status,
            "recommended_next_step": self.recommended_next_step,
            "scope": self.scope.value,
            "authorization": self.authorization.value,
            "provenance": prov_dict,
        }
