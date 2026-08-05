import asyncio
import subprocess
import time
from types import SimpleNamespace

from fastapi.testclient import TestClient

import app.main as main_module
import app.routes.system as system_module
from app.services.system_monitor import SystemMonitor

FAKE_GPU = {
    "gpu_util": 50.0,
    "vram_used": 100.0,
    "vram_total": 8192.0,
    "gpu_temp": 60.0,
}

FAKE_STATS = {
    "cpu": {"percent": 42.0, "temp": None},
    "ram": {"used": 100, "total": 200, "percent": 50.0},
    "disk": {"used": 300, "total": 400, "percent": 75.0},
    "gpu": {
        "util": 50.0,
        "vram_used": 100.0,
        "vram_total": 8192.0,
        "temp": 60.0,
    },
    "battery": {"percent": None, "charging": None},
    "network": {"upload_bps": 0.0, "download_bps": 0.0},
}


def stub_psutil(monkeypatch, cpu=42.0) -> list:
    """Route every psutil entry point _sample touches to stubs so tests never
    probe real hardware. Returns the list of cpu_percent call args."""
    import psutil

    cpu_calls: list = []

    def fake_cpu_percent(*args, **kwargs):
        cpu_calls.append(args)
        return cpu

    monkeypatch.setattr("psutil.cpu_percent", fake_cpu_percent)
    monkeypatch.setattr(
        "psutil.virtual_memory",
        lambda: SimpleNamespace(used=100, total=200, percent=50.0),
    )
    monkeypatch.setattr(
        "psutil.disk_usage",
        lambda p: SimpleNamespace(used=300, total=400, percent=75.0),
    )
    monkeypatch.setattr(
        "psutil.net_io_counters",
        lambda: SimpleNamespace(bytes_sent=10, bytes_recv=20),
    )
    # sensors_* are not defined on every platform (e.g. sensors_temperatures
    # is absent on Windows); patch only what exists.
    if hasattr(psutil, "sensors_battery"):
        monkeypatch.setattr("psutil.sensors_battery", lambda: None)
    if hasattr(psutil, "sensors_temperatures"):
        monkeypatch.setattr("psutil.sensors_temperatures", dict)
    return cpu_calls


class TestSystemMonitor:
    async def test_background_refresh_updates_stats(self, monkeypatch) -> None:
        stub_psutil(monkeypatch)
        monkeypatch.setattr(SystemMonitor, "_probe_gpu", staticmethod(lambda: dict(FAKE_GPU)))
        monitor = SystemMonitor(interval=0.02)
        monitor.start()
        try:
            await asyncio.sleep(0.08)
            assert monitor.stats == FAKE_STATS
        finally:
            await monitor.stop()

    async def test_failed_gpu_probe_keeps_last_good(self, monkeypatch) -> None:
        stub_psutil(monkeypatch)
        results = iter([dict(FAKE_GPU), None, None])

        monkeypatch.setattr(SystemMonitor, "_probe_gpu", staticmethod(lambda: next(results)))
        monitor = SystemMonitor(interval=0.02)
        monitor.start()
        try:
            await asyncio.sleep(0.05)
            assert monitor.stats["gpu"] == {
                "util": 50.0,
                "vram_used": 100.0,
                "vram_total": 8192.0,
                "temp": 60.0,
            }
            await asyncio.sleep(0.05)
            assert monitor.stats["gpu"]["util"] == 50.0
        finally:
            await monitor.stop()

    async def test_stats_is_a_copy(self) -> None:
        monitor = SystemMonitor(interval=60.0)
        snap = monitor.stats
        snap["cpu"]["percent"] = 99.0
        assert monitor.stats["cpu"]["percent"] == 0.0

    async def test_interval_must_be_positive(self) -> None:
        import pytest

        with pytest.raises(ValueError):
            SystemMonitor(interval=0)
        with pytest.raises(ValueError):
            SystemMonitor(interval=-1.0)

    async def test_start_idempotent_stop_twice_restart(self, monkeypatch) -> None:
        stub_psutil(monkeypatch)
        monkeypatch.setattr(SystemMonitor, "_probe_gpu", staticmethod(lambda: None))
        monitor = SystemMonitor(interval=60.0)
        monitor.start()
        monitor.start()  # idempotent
        await monitor.stop()
        await monitor.stop()  # double stop must not raise
        monitor.start()  # restart after shutdown must work
        await monitor.stop()

    async def test_probe_handles_missing_binary(self, monkeypatch) -> None:
        def raise_filenotfound(*args, **kwargs):
            raise FileNotFoundError("nvidia-smi not found")

        monkeypatch.setattr(subprocess, "run", raise_filenotfound)
        monitor = SystemMonitor(interval=60.0)
        assert monitor._probe_gpu() is None

    async def test_battery_unavailable_degrades_per_field(self, monkeypatch) -> None:
        stub_psutil(monkeypatch)

        def raise_not_implemented():
            raise NotImplementedError("not implemented")

        monkeypatch.setattr("psutil.sensors_battery", raise_not_implemented)
        monitor = SystemMonitor(interval=60.0)
        stats = await asyncio.to_thread(monitor._sample)
        assert stats["battery"] == {"percent": None, "charging": None}
        assert stats["cpu"]["percent"] == 42.0  # rest of the sample still produced

    async def test_cpu_first_sample_warms_then_delta(self, monkeypatch) -> None:
        cpu_calls = stub_psutil(monkeypatch)
        monkeypatch.setattr(SystemMonitor, "_probe_gpu", staticmethod(lambda: None))
        monitor = SystemMonitor(interval=60.0)
        await asyncio.to_thread(monitor._sample)
        await asyncio.to_thread(monitor._sample)
        assert cpu_calls[0][0] == 0.1  # one-time blocking warm-up
        assert cpu_calls[1][0] is None  # non-blocking delta afterwards


class TestStatsRouteCache:
    class FakeMonitor:
        def __init__(self, stats: dict) -> None:
            self.stats = stats

    def test_stats_served_from_cache_full_shape(self, monkeypatch) -> None:
        monkeypatch.setattr(
            system_module, "system_monitor", self.FakeMonitor(dict(FAKE_STATS))
        )
        with TestClient(main_module.app) as client:
            r = client.get("/api/v1/system/stats")
        assert r.status_code == 200
        assert r.json() == FAKE_STATS

    def test_stats_na_fields_when_empty(self, monkeypatch) -> None:
        monkeypatch.setattr(
            system_module,
            "system_monitor",
            self.FakeMonitor(SystemMonitor._empty_stats()),
        )
        with TestClient(main_module.app) as client:
            r = client.get("/api/v1/system/stats")
        assert r.status_code == 200
        data = r.json()
        assert data["gpu"]["util"] is None
        assert data["battery"]["percent"] is None
        assert data["cpu"]["percent"] == 0.0

    def test_stats_never_probes_in_request_path(self, monkeypatch) -> None:
        """No subprocess, no psutil sampling may run inside /stats — the route
        is a single O(1) snapshot read; the background monitor owns probing."""

        def bomb(*args, **kwargs):
            raise AssertionError("subprocess launched during /stats request")

        monkeypatch.setattr(subprocess, "run", bomb)
        monkeypatch.setattr(
            system_module, "system_monitor", self.FakeMonitor(dict(FAKE_STATS))
        )
        start = time.perf_counter()
        with TestClient(main_module.app) as client:
            for _ in range(5):
                assert client.get("/api/v1/system/stats").status_code == 200
        elapsed = time.perf_counter() - start
        assert elapsed < 2.0  # per-request probing (>=100ms each) would blow this
