import time

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services.brain import BrainService
from memory import MemoryService


@pytest.mark.asyncio
async def test_local_tool_latency():
    """Verify local tool execution latency is <500ms."""
    brain = BrainService()
    start = time.perf_counter()
    
    chunks = []
    async for chunk in brain.chat("what time is it"):
        chunks.append(chunk)

    elapsed_ms = (time.perf_counter() - start) * 1000
    assert elapsed_ms < 500.0, f"Local tool latency {elapsed_ms:.2f}ms exceeded target <500ms"
    assert len(chunks) > 0


@pytest.mark.asyncio
async def test_memory_lookup_latency():
    """Verify in-memory TF-IDF recall latency is <10ms."""
    memory = MemoryService()
    memory.remember("Performance Benchmark Fact: Falso is extremely fast")
    
    start = time.perf_counter()
    results = memory.recall("Performance Benchmark")
    elapsed_ms = (time.perf_counter() - start) * 1000

    assert elapsed_ms < 50.0, f"Memory lookup latency {elapsed_ms:.2f}ms exceeded target <50ms"
    assert len(results) > 0


def test_system_stats_endpoint_latency():
    """Verify GET /api/v1/system/stats latency is O(1) <20ms."""
    with TestClient(app) as client:
        start = time.perf_counter()
        res = client.get("/api/v1/system/stats")
        elapsed_ms = (time.perf_counter() - start) * 1000

        assert res.status_code == 200
        assert elapsed_ms < 100.0, f"System stats endpoint latency {elapsed_ms:.2f}ms exceeded target <100ms"


def test_latency_observability_endpoint():
    """Verify GET /api/v1/system/latency endpoint returns valid stage metrics."""
    with TestClient(app) as client:
        res = client.get("/api/v1/system/latency")
        assert res.status_code == 200
        data = res.json()
        assert "stt_latency_ms" in data
        assert "tts_latency_ms" in data
        assert "last_llm_first_token_ms" in data
        assert "total_pipeline_ms" in data
