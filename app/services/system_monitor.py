from __future__ import annotations

import asyncio
import copy
import logging
import subprocess
import time
from concurrent.futures import ThreadPoolExecutor
from typing import Any

import psutil

from config.settings import settings

logger = logging.getLogger(__name__)

_SMI_QUERY = "--query-gpu=utilization.gpu,memory.used,memory.total,temperature.gpu"
_SMI_FORMAT = "--format=csv,noheader,nounits"
_SMI_TIMEOUT = 3.0
# One-time blocking sample at startup so the first CPU figure is real; every
# later tick uses the non-blocking psutil delta (cpu_percent(None)).
_CPU_FIRST_SAMPLE = 0.1
# The sampler uses its own single-worker executor: nothing else in the app can
# delay a stats refresh, and the monitor never consumes default-pool threads.
_SAMPLER_WORKERS = 1


class SystemMonitor:
    """Background sampler for every metric served by /api/v1/system/stats.

    All blocking probes (nvidia-smi subprocess, psutil syscalls, one-time CPU
    sample) run in a single dedicated worker thread per refresh interval; the
    event loop only reads the cached snapshot — an O(1) dict copy. /stats
    requests therefore cost zero threads and zero blocking time regardless of
    the frontend poll rate.

    Failure semantics: a failed GPU probe keeps the last successful GPU
    snapshot (dashboard continuity); other probes degrade per-field to None,
    which the frontend renders as N/A. Before the first sample completes, the
    cache holds zero values for the numeric fields and None for availability
    fields, matching what the old per-request path returned on its first call.
    """

    def __init__(self, interval: float | None = None) -> None:
        self.interval = (
            settings.gpu_refresh_interval_seconds
            if interval is None
            else float(interval)
        )
        if self.interval <= 0:
            raise ValueError("gpu_refresh_interval_seconds must be > 0")
        self._stats: dict[str, Any] = self._empty_stats()
        self._task: asyncio.Task | None = None
        self._executor: ThreadPoolExecutor | None = None
        self._net_last: tuple[int, int, float] | None = None
        self._gpu_last: dict[str, Any] | None = None
        self._cpu_warmed = False
        self._gpu_available: bool | None = None  # None = not yet tested

    def start(self) -> None:
        if self._task is not None:
            return
        if self._executor is None:
            self._executor = ThreadPoolExecutor(
                max_workers=_SAMPLER_WORKERS,
                thread_name_prefix="falso-monitor",
            )
        self._task = asyncio.create_task(self._run())
        logger.info("System stats monitor started (interval=%.1fs)", self.interval)

    async def stop(self) -> None:
        if self._task is not None:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None
            if self._executor is not None:
                self._executor.shutdown(wait=False, cancel_futures=True)
                self._executor = None
            logger.info("System stats monitor stopped")

    @property
    def stats(self) -> dict[str, Any]:
        # Deep copy: the nested dicts are owned by the sampler thread; callers
        # (and tests) may mutate the returned structure freely.
        return copy.deepcopy(self._stats)

    async def _run(self) -> None:
        loop = asyncio.get_running_loop()
        while True:
            try:
                self._stats = await loop.run_in_executor(
                    self._executor, self._sample
                )
            except asyncio.CancelledError:
                raise
            except Exception:  # sampler must never kill the monitor loop
                logger.exception("System stats sampler failed")
            await asyncio.sleep(self.interval)

    def _sample(self) -> dict[str, Any]:
        """Blocking sampling pass; runs in the monitor's worker thread."""
        if self._cpu_warmed:
            cpu = psutil.cpu_percent(None)
        else:
            cpu = psutil.cpu_percent(_CPU_FIRST_SAMPLE)
            self._cpu_warmed = True
        mem = psutil.virtual_memory()
        disk = psutil.disk_usage("/")
        net = self._sample_network()
        temps = self._sample_temperatures()
        battery = self._sample_battery()
        gpu = self._probe_gpu()
        if gpu is not None:
            self._gpu_available = True
            self._gpu_last = gpu
        elif self._gpu_available is None:
            # First probe failed — mark GPU as unavailable so we skip
            # subprocess spawning on all future samples.
            self._gpu_available = False
            gpu = {"gpu_util": None, "vram_used": None, "vram_total": None, "gpu_temp": None}
        else:
            gpu = self._gpu_last
        if gpu is None:
            gpu = {"gpu_util": None, "vram_used": None, "vram_total": None, "gpu_temp": None}

        # Sensors' GPU temp wins over nvidia-smi when both are available.
        if temps["gpu_temp"] is None and gpu.get("gpu_temp") is not None:
            temps["gpu_temp"] = gpu["gpu_temp"]

        return {
            "cpu": {
                "percent": round(cpu, 1),
                "temp": temps.get("cpu_temp"),
            },
            "ram": {
                "used": mem.used,
                "total": mem.total,
                "percent": mem.percent,
            },
            "disk": {
                "used": disk.used,
                "total": disk.total,
                "percent": disk.percent,
            },
            "gpu": {
                "util": gpu.get("gpu_util"),
                "vram_used": gpu.get("vram_used"),
                "vram_total": gpu.get("vram_total"),
                "temp": temps.get("gpu_temp"),
            },
            "battery": battery,
            "network": net,
        }

    def _sample_battery(self) -> dict[str, float | None]:
        result: dict[str, float | None] = {"percent": None, "charging": None}
        try:
            battery = psutil.sensors_battery()
        except Exception as e:  # noqa: BLE001 — not implemented on this platform
            logger.debug("Battery sensor unavailable: %s", e)
            return result
        if battery is not None:
            result["percent"] = round(battery.percent, 1)
            result["charging"] = battery.power_plugged
        return result

    def _sample_network(self) -> dict[str, float]:
        counters = psutil.net_io_counters()
        now = time.monotonic()
        sent = counters.bytes_sent
        recv = counters.bytes_recv

        upload = 0.0
        download = 0.0
        if self._net_last is not None:
            last_sent, last_recv, last_time = self._net_last
            dt = now - last_time
            if dt > 0:
                upload = max(0, (sent - last_sent) / dt)
                download = max(0, (recv - last_recv) / dt)

        self._net_last = (sent, recv, now)
        return {
            "upload_bps": round(upload, 1),
            "download_bps": round(download, 1),
        }

    def _sample_temperatures(self) -> dict[str, float | None]:
        result: dict[str, float | None] = {"cpu_temp": None, "gpu_temp": None}
        try:
            temps = psutil.sensors_temperatures()
            for name, entries in temps.items():
                for entry in entries:
                    label = entry.label or name
                    if "cpu" in label.lower() and result["cpu_temp"] is None:
                        result["cpu_temp"] = round(entry.current, 1)
                    if "gpu" in label.lower() and result["gpu_temp"] is None:
                        result["gpu_temp"] = round(entry.current, 1)
        except Exception as e:  # noqa: BLE001 — hardware probing; failure means "unavailable"
            logger.debug("Temperature sensors unavailable: %s", e)
        return result

    def _probe_gpu(self) -> dict[str, Any] | None:
        """Blocking nvidia-smi query; may take up to _SMI_TIMEOUT seconds.
        Returns None if no NVIDIA GPU is available."""
        # Skip subprocess entirely if we already know there's no GPU.
        if self._gpu_available is False:
            return None
        try:
            proc = subprocess.run(
                ["nvidia-smi", _SMI_QUERY, _SMI_FORMAT],
                capture_output=True, text=True, timeout=_SMI_TIMEOUT, check=False,
            )
        except Exception as e:  # noqa: BLE001 — binary missing or driver error
            logger.debug("GPU probe unavailable: %s", e)
            return None
        if proc.returncode != 0 or not proc.stdout.strip():
            return None
        parts = proc.stdout.strip().split(", ")
        if len(parts) < 4:
            return None
        return {
            "gpu_util": float(parts[0]) if parts[0] else None,
            "vram_used": float(parts[1]) if parts[1] else None,
            "vram_total": float(parts[2]) if parts[2] else None,
            "gpu_temp": float(parts[3]) if parts[3] else None,
        }

    @staticmethod
    def _empty_stats() -> dict[str, Any]:
        return {
            "cpu": {"percent": 0.0, "temp": None},
            "ram": {"used": 0, "total": 0, "percent": 0.0},
            "disk": {"used": 0, "total": 0, "percent": 0.0},
            "gpu": {"util": None, "vram_used": None, "vram_total": None, "temp": None},
            "battery": {"percent": None, "charging": None},
            "network": {"upload_bps": 0.0, "download_bps": 0.0},
        }


system_monitor = SystemMonitor()
