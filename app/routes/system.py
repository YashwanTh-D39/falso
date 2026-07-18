import logging
import time
from functools import lru_cache

import psutil
from fastapi import APIRouter

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/system", tags=["System"])

# Network tracking
_net_last: tuple[int, int, float] | None = None


def _get_network_speed() -> dict:
    global _net_last
    counters = psutil.net_io_counters()
    now = time.time()
    sent = counters.bytes_sent
    recv = counters.bytes_recv

    if _net_last is not None:
        last_sent, last_recv, last_time = _net_last
        dt = now - last_time
        if dt > 0:
            upload = max(0, (sent - last_sent) / dt)
            download = max(0, (recv - last_recv) / dt)
        else:
            upload = 0
            download = 0
    else:
        upload = 0
        download = 0

    _net_last = (sent, recv, now)
    return {
        "upload_bps": round(upload, 1),
        "download_bps": round(download, 1),
    }


def _get_gpu_info() -> dict:
    result = {
        "gpu_util": None,
        "vram_used": None,
        "vram_total": None,
        "gpu_temp": None,
    }
    try:
        import subprocess
        proc = subprocess.run(
            [
                "nvidia-smi",
                "--query-gpu=utilization.gpu,memory.used,memory.total,temperature.gpu",
                "--format=csv,noheader,nounits",
            ],
            capture_output=True, text=True, timeout=3,
        )
        if proc.returncode == 0 and proc.stdout.strip():
            parts = proc.stdout.strip().split(", ")
            if len(parts) >= 4:
                result["gpu_util"] = float(parts[0]) if parts[0] else None
                result["vram_used"] = float(parts[1]) if parts[1] else None
                result["vram_total"] = float(parts[2]) if parts[2] else None
                result["gpu_temp"] = float(parts[3]) if parts[3] else None
    except Exception:
        pass
    return result


def _get_temperatures() -> dict:
    result = {"cpu_temp": None, "gpu_temp": None}
    try:
        temps = psutil.sensors_temperatures()
        for name, entries in temps.items():
            for entry in entries:
                label = entry.label or name
                if "cpu" in label.lower() and result["cpu_temp"] is None:
                    result["cpu_temp"] = round(entry.current, 1)
                if "gpu" in label.lower() and result["gpu_temp"] is None:
                    result["gpu_temp"] = round(entry.current, 1)
    except Exception:
        pass
    return result


@router.get("/stats")
async def get_system_stats():
    # CPU
    cpu_percent = psutil.cpu_percent(interval=0.1)

    # RAM
    mem = psutil.virtual_memory()
    ram_used = mem.used
    ram_total = mem.total
    ram_percent = mem.percent

    # Disk
    disk = psutil.disk_usage("/")
    disk_used = disk.used
    disk_total = disk.total
    disk_percent = disk.percent

    # Battery
    battery_info = {"percent": None, "charging": None}
    try:
        bat = psutil.sensors_battery()
        if bat is not None:
            battery_info["percent"] = round(bat.percent, 1)
            battery_info["charging"] = bat.power_plugged
    except Exception:
        pass

    # Network
    net = _get_network_speed()

    # GPU
    gpu = _get_gpu_info()

    # Temperatures
    temps = _get_temperatures()
    # Merge GPU temp from nvidia-smi result if not found via sensors
    if temps["gpu_temp"] is None and gpu["gpu_temp"] is not None:
        temps["gpu_temp"] = gpu["gpu_temp"]

    return {
        "cpu": {
            "percent": round(cpu_percent, 1),
            "temp": temps.get("cpu_temp"),
        },
        "ram": {
            "used": ram_used,
            "total": ram_total,
            "percent": ram_percent,
        },
        "disk": {
            "used": disk_used,
            "total": disk_total,
            "percent": disk_percent,
        },
        "gpu": {
            "util": gpu.get("gpu_util"),
            "vram_used": gpu.get("vram_used"),
            "vram_total": gpu.get("vram_total"),
            "temp": temps.get("gpu_temp"),
        },
        "battery": battery_info,
        "network": net,
    }
