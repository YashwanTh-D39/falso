"""
FALSO 4.11 Cybersecurity Intelligence & Investigation Engine Tests.

Tests:
1. SecurityState evidence classification (OBSERVED, INFERRED, UNKNOWN) & unknowns tracking
2. Asset inventory generation & correlation
3. SecurityBaseline versioned snapshots & history
4. Baseline comparison & ChangeDetector diff calculation
5. False-positive controls (allowlisting, known_expected, expiration)
6. SecurityEvidenceGraph node-edge relationships & lineage
7. DetectionEngine rules & multi-signal severity correlation
8. ConfidenceEngine scoring based on sources and verification
9. Defensive MITRE ATT&CK analytical mapping & grounding labels
10. SecurityTimeline event recording & retrieval
11. SecurityInvestigationEngine answering defensive security inquiries:
    - What is listening?
    - What is running?
    - What changed?
    - Is anything unusual?
    - Timeline inquiries
12. Stop conditions & DiagnosticBudget enforcement
13. ActionSelector routing for security intelligence intents
14. OperatorEngine concise reporting
"""

from __future__ import annotations

import time
from unittest.mock import MagicMock, patch
import pytest

from app.services.automation.operator.action_selector import ControlMethod, action_selector
from app.services.automation.operator.computer_state import ComputerState, EvidenceType, StateValue
from app.services.automation.operator.operator_engine import operator_engine
from app.services.automation.operator.security.baseline import (
    BaselineDiff,
    BaselineEntry,
    BaselineStatus,
    ChangeDetector,
    SecurityBaseline,
)
from app.services.automation.operator.security.confidence import ConfidenceEngine, ConfidenceScore
from app.services.automation.operator.security.detection_engine import (
    DetectionEngine,
    SecurityFinding,
    detection_engine,
)
from app.services.automation.operator.security.evidence import (
    DiagnosticBudget,
    EvidenceProvenance,
    FindingSeverity,
    SecurityEvidence,
    SecurityScope,
)
from app.services.automation.operator.security.evidence_graph import SecurityEvidenceGraph
from app.services.automation.operator.security.investigation_engine import (
    SecurityInvestigationEngine,
    security_investigation_engine,
)
from app.services.automation.operator.security.mitre_mapping import (
    MitreEvidenceGrounding,
    MitreMapper,
)
from app.services.automation.operator.security.security_state import (
    SecurityAsset,
    SecurityState,
)
from app.services.automation.operator.security.timeline import SecurityTimeline


class TestFalso411SecurityIntelligence:
    # ── 1. SecurityState & Evidence Classification ──
    def test_01_security_state_evidence_and_unknowns(self):
        state = SecurityState()
        # Default unobserved categories must be UNKNOWN
        unknowns = state.get_unknowns()
        assert "listening_ports" in unknowns
        assert "processes" in unknowns
        assert "network_interfaces" in unknowns

        # Set OBSERVED value
        state.listening_ports = StateValue(
            value=[{"port": 8000, "pid": 1234, "process_name": "uvicorn"}],
            evidence=EvidenceType.OBSERVED,
        )
        assert state.listening_ports.is_observed()
        assert "listening_ports" not in state.get_unknowns()

    # ── 2. Asset Inventory ──
    def test_02_asset_inventory_generation(self):
        state = SecurityState()
        state.listening_ports = StateValue(
            value=[{"port": 8000, "pid": 1234, "process_name": "uvicorn", "ip": "127.0.0.1"}],
            evidence=EvidenceType.OBSERVED,
        )
        state.processes = StateValue(
            value=[{"pid": 1234, "name": "uvicorn.exe", "exe": "C:\\Python\\uvicorn.exe"}],
            evidence=EvidenceType.OBSERVED,
        )
        assets = state.build_asset_inventory()
        assert len(assets) == 2
        port_asset = next(a for a in assets if a.asset_type == "listening_port")
        assert port_asset.port == 8000
        assert port_asset.pid == 1234

    # ── 3. SecurityBaseline Versioning ──
    def test_03_security_baseline_versioned_snapshots(self):
        baseline = SecurityBaseline()
        state = SecurityState()
        state.listening_ports = StateValue(
            value=[{"port": 8000, "pid": 1234, "process_name": "uvicorn"}],
            evidence=EvidenceType.OBSERVED,
        )
        v1 = baseline.create_baseline(state, label="Initial dev state")
        assert v1 == "v1"

        history = baseline.get_baseline_history()
        assert len(history) == 1
        assert history[0]["version_id"] == "v1"
        assert history[0]["asset_count"] >= 1

    # ── 4. Baseline Comparison & Change Detection ──
    def test_04_baseline_comparison_detects_new_port(self):
        baseline = SecurityBaseline()
        state_v1 = SecurityState()
        state_v1.listening_ports = StateValue(
            value=[{"port": 8000, "pid": 1234, "process_name": "uvicorn"}],
            evidence=EvidenceType.OBSERVED,
        )
        baseline.create_baseline(state_v1)

        # State v2 introduces new listening port 9000
        state_v2 = SecurityState()
        state_v2.listening_ports = StateValue(
            value=[
                {"port": 8000, "pid": 1234, "process_name": "uvicorn"},
                {"port": 9000, "pid": 5678, "process_name": "test_service.exe"},
            ],
            evidence=EvidenceType.OBSERVED,
        )
        diffs = baseline.compare_baseline(state_v2)
        assert len(diffs) == 1
        assert diffs[0].asset_id == "port_9000"
        assert diffs[0].status == BaselineStatus.NEW

    # ── 5. False-Positive Controls ──
    def test_05_baseline_allowlist_exceptions_and_expiration(self):
        baseline = SecurityBaseline()
        # Add temporary exception for port 9000
        baseline.add_allowlist_exception("port_9000", reason="Temporary test service", expires_in_sec=10.0)

        state = SecurityState()
        state.listening_ports = StateValue(
            value=[{"port": 9000, "pid": 5678, "process_name": "test_service.exe"}],
            evidence=EvidenceType.OBSERVED,
        )
        # Port 9000 is suppressed because of active exception
        diffs = baseline.compare_baseline(state)
        assert len(diffs) == 0

        # Now test with expired exception
        baseline.add_allowlist_exception("port_9000", reason="Expired test", expires_in_sec=-1.0)
        diffs_expired = baseline.compare_baseline(state)
        assert len(diffs_expired) == 1

    # ── 6. SecurityEvidenceGraph ──
    def test_06_security_evidence_graph_lineage(self):
        graph = SecurityEvidenceGraph()
        graph.add_node("host_local", "host", {"name": "localhost"})
        graph.add_node("proc_100", "process", {"pid": 100, "name": "python.exe"})
        graph.add_node("sock_100", "socket", {"laddr": "127.0.0.1:8000"})
        graph.add_node("port_8000", "port", {"port": 8000})

        graph.add_edge("host_local", "proc_100", "hosts")
        graph.add_edge("proc_100", "sock_100", "owns")
        graph.add_edge("sock_100", "port_8000", "binds")

        correlation = graph.correlate_port_to_process(8000)
        assert correlation is not None
        assert correlation["process"]["pid"] == 100
        assert correlation["process"]["name"] == "python.exe"

    # ── 7. DetectionEngine Multi-Signal Severity ──
    def test_07_detection_engine_evaluates_changes(self):
        state = SecurityState()
        diff = BaselineDiff(
            what_changed="new_listening_port_detected",
            asset_id="port_4450",
            asset_type="listening_port",
            status=BaselineStatus.NEW,
            before=None,
            after={"port": 4450, "pid": 4120, "process_name": "unusual_srv.exe", "ip": "127.0.0.1"},
        )
        findings = detection_engine.evaluate_state_and_changes(state, [diff])
        assert len(findings) == 1
        f = findings[0]
        assert f.rule_id == "DET-01"
        assert f.severity == FindingSeverity.LOW  # Localhost process -> LOW
        assert f.confidence == ConfidenceScore.HIGH

    # ── 8. ConfidenceEngine ──
    def test_08_confidence_engine_scoring(self):
        # 1 unverified source -> LOW
        score_low = ConfidenceEngine.calculate_confidence(evidence_sources_count=1, is_verified=False)
        assert score_low in (ConfidenceScore.LOW, ConfidenceScore.VERY_LOW)

        # 2 verified correlated sources + baseline history -> VERY_HIGH / HIGH
        score_high = ConfidenceEngine.calculate_confidence(
            evidence_sources_count=2,
            is_verified=True,
            correlation_depth=2,
            has_baseline_history=True,
        )
        assert score_high in (ConfidenceScore.HIGH, ConfidenceScore.VERY_HIGH)

    # ── 9. MITRE ATT&CK Mapping ──
    def test_09_mitre_mapper_defensive_mapping(self):
        mapping = MitreMapper.map_finding("port_discovery", {"port": 8000})
        assert mapping is not None
        assert mapping.technique_id == "T1049"
        assert mapping.tactic == "Discovery"
        assert mapping.grounding == MitreEvidenceGrounding.SUPPORTED

    # ── 10. SecurityTimeline ──
    def test_10_security_timeline_event_recording(self):
        timeline = SecurityTimeline(max_events=10)
        timeline.record_event("port_opened", "Port 8000", {"pid": 1234})
        timeline.record_event("process_started", "uvicorn.exe", {"pid": 1234})

        events = timeline.get_recent_events(5)
        assert len(events) == 2
        assert events[0]["event_type"] == "port_opened"
        assert events[1]["event_type"] == "process_started"

    # ── 11. SecurityInvestigationEngine Inquiries ──
    def test_11_investigation_what_is_listening(self):
        engine = SecurityInvestigationEngine()
        mock_state = SecurityState()
        mock_state.listening_ports = StateValue(
            value=[{"port": 8000, "pid": 15568, "process_name": "uvicorn"}],
            evidence=EvidenceType.OBSERVED,
        )
        with patch.object(engine, "_observe_current_security_state", return_value=mock_state):
            ok, summary, findings = engine.investigate("What is listening on my machine?")
            assert ok is True
            assert "8000" in summary
            assert "uvicorn" in summary

    def test_12_investigation_what_changed(self):
        engine = SecurityInvestigationEngine()
        mock_state = SecurityState()
        mock_state.listening_ports = StateValue(
            value=[{"port": 8000, "pid": 15568, "process_name": "uvicorn"}],
            evidence=EvidenceType.OBSERVED,
        )
        # Compare against clean baseline (which expects 8000)
        with patch.object(engine, "_observe_current_security_state", return_value=mock_state):
            ok, summary, findings = engine.investigate("What changed since my last baseline?")
            assert ok is True
            assert "No security-relevant deviations" in summary

    def test_13_investigation_is_anything_unusual(self):
        engine = SecurityInvestigationEngine()
        mock_state = SecurityState()
        mock_state.listening_ports = StateValue(
            value=[{"port": 8000, "pid": 15568, "process_name": "uvicorn"}],
            evidence=EvidenceType.OBSERVED,
        )
        with patch.object(engine, "_observe_current_security_state", return_value=mock_state):
            ok, summary, findings = engine.investigate("Is anything unusual?")
            assert ok is True
            assert "Nothing suspicious" in summary or "No anomalous" in summary

    # ── 12. Stop Conditions & Diagnostic Budget ──
    def test_14_investigation_stop_condition_on_budget_exhaustion(self):
        engine = SecurityInvestigationEngine()
        budget = DiagnosticBudget(max_steps=0)
        ok, summary, findings = engine.investigate("Check local security", budget=budget)
        assert ok is False
        assert "budget exceeded" in summary

    # ── 13. ActionSelector Intent Routing ──
    def test_15_action_selector_routes_security_intelligence_queries(self):
        state = ComputerState()
        res_running = action_selector.select_action("What is running?", state)
        assert res_running.method == ControlMethod.APPLICATION_SKILL
        assert res_running.target_app == "security"

        res_changed = action_selector.select_action("What changed since baseline?", state)
        assert res_changed.method == ControlMethod.APPLICATION_SKILL
        assert res_changed.target_app == "security"

    # ── 14. OperatorEngine Integration ──
    @pytest.mark.asyncio
    async def test_16_operator_engine_security_intelligence_execution(self):
        with patch.object(security_investigation_engine, "investigate", return_value=(
            True,
            "Port 8000 is your FALSO development server and is only listening on localhost. Nothing suspicious found.",
            [],
        )):
            resp = await operator_engine.run_operation("Is anything unusual on my machine?")
            assert "Port 8000" in resp
            assert "Nothing suspicious" in resp
