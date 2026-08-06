"""System monitor service for FALSO Spatial OS.

Provides real-time system metrics (CPU, RAM, Disks, Network, GPU)
and non-blocking process polling using psutil and nvidia-ml-py.
"""

import asyncio
import logging
import time
from typing import Any, Dict, List, Optional, Tuple

import psutil

logger = logging.getLogger(__name__)

# Check NVIDIA GPU availability gracefully
HAS_NVIDIA = False
try:
    import pynvml
    pynvml.nvmlInit()
    HAS_NVIDIA = True
    logger.info("NVIDIA NVML initialized successfully.")
except Exception as e:
    logger.info(f"NVIDIA NVML not available or error: {e}")
    HAS_NVIDIA = False


class SystemMonitorService:
    """Service to poll system resource metrics and process data efficiently."""

    def __init__(self, sample_interval: float = 1.0):
        self.sample_interval = sample_interval
        # Cache for PID -> (cpu_time_total, timestamp)
        self._last_proc_cpu_times: Dict[int, Tuple[float, float]] = {}
        self._last_net_io = psutil.net_io_counters()
        self._last_net_time = time.time()

        # Cached hardware flags to avoid repetitive exception logging
        self._has_wmi: Optional[bool] = None
        self._wmi_client = None
        self._has_nvidia: bool = HAS_NVIDIA
        
        # Cache for process list to prevent CPU thrashing (1.5s cache)
        self._proc_cache: List[Dict[str, Any]] = []
        self._proc_cache_time: float = 0.0

    def get_system_stats(self) -> Dict[str, Any]:
        """Retrieves aggregated system metrics efficiently."""
        now = time.time()
        time_delta = max(now - self._last_net_time, 0.001)

        # 1. CPU
        try:
            cpu_total = psutil.cpu_percent(interval=None)
            cpu_per_core = psutil.cpu_percent(interval=None, percpu=True)
            cpu_freq = psutil.cpu_freq()
            freq_mhz = cpu_freq.current if cpu_freq else None
        except Exception as e:
            cpu_total = 0.0
            cpu_per_core = []
            freq_mhz = None

        # 2. Memory
        try:
            mem = psutil.virtual_memory()
            swap = psutil.swap_memory()
            ram_stats = {
                "total": mem.total,
                "available": mem.available,
                "used": mem.used,
                "percent": mem.percent,
                "swap_percent": swap.percent
            }
        except Exception:
            ram_stats = {"total": 0, "available": 0, "used": 0, "percent": 0.0, "swap_percent": 0.0}

        # 3. Disks
        partitions = []
        try:
            for part in psutil.disk_partitions(all=False):
                try:
                    usage = psutil.disk_usage(part.mountpoint)
                    partitions.append({
                        "device": part.device,
                        "mountpoint": part.mountpoint,
                        "fstype": part.fstype,
                        "total_bytes": usage.total,
                        "used_bytes": usage.used,
                        "free_bytes": usage.free,
                        "percent": usage.percent
                    })
                except (PermissionError, OSError):
                    continue
        except Exception:
            pass

        # 4. Network Rate
        try:
            net_io = psutil.net_io_counters()
            bytes_sent_sec = (net_io.bytes_sent - self._last_net_io.bytes_sent) / time_delta
            bytes_recv_sec = (net_io.bytes_recv - self._last_net_io.bytes_recv) / time_delta
            self._last_net_io = net_io
            self._last_net_time = now
            net_stats = {
                "upload_bytes_sec": round(bytes_sent_sec, 2),
                "download_bytes_sec": round(bytes_recv_sec, 2),
                "total_bytes_sent": net_io.bytes_sent,
                "total_bytes_recv": net_io.bytes_recv
            }
        except Exception:
            net_stats = {"upload_bytes_sec": 0, "download_bytes_sec": 0, "total_bytes_sent": 0, "total_bytes_recv": 0}

        # 5. GPU (Cached NVML check)
        gpu_stats = []
        if self._has_nvidia:
            try:
                device_count = pynvml.nvmlDeviceGetCount()
                for i in range(device_count):
                    handle = pynvml.nvmlDeviceGetHandleByIndex(i)
                    name = pynvml.nvmlDeviceGetName(handle)
                    if isinstance(name, bytes):
                        name = name.decode("utf-8")
                    util = pynvml.nvmlDeviceGetUtilizationRates(handle)
                    mem_info = pynvml.nvmlDeviceGetMemoryInfo(handle)
                    temp = pynvml.nvmlDeviceGetTemperature(handle, pynvml.NVML_TEMPERATURE_GPU)
                    gpu_stats.append({
                        "index": i,
                        "name": name,
                        "gpu_utilization": util.gpu,
                        "memory_utilization": util.memory,
                        "vram_total": mem_info.total,
                        "vram_used": mem_info.used,
                        "vram_free": mem_info.free,
                        "temperature_c": temp
                    })
            except Exception:
                self._has_nvidia = False  # Disable subsequent checks if NVML unsupported

        # 6. Battery
        battery_stats = None
        try:
            bat = psutil.sensors_battery()
            if bat:
                battery_stats = {
                    "percent": bat.percent,
                    "power_plugged": bat.power_plugged,
                    "secs_left": bat.secsleft if bat.secsleft != psutil.POWER_TIME_UNLIMITED else -1
                }
        except Exception:
            battery_stats = None

        # 7. System Environment Context
        active_window = "Project-Falso"
        try:
            import win32gui
            hwnd = win32gui.GetForegroundWindow()
            title = win32gui.GetWindowText(hwnd)
            if title.strip():
                active_window = title.strip()
        except Exception:
            pass

        import getpass
        import os
        from datetime import datetime

        user_info = {
            "current_user": getpass.getuser(),
            "cwd": os.getcwd(),
            "project_folder": "c:/Users/Admin/Project-Falso",
            "active_window": active_window,
            "datetime": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }

        return {
            "timestamp": now,
            "cpu": {
                "total_percent": cpu_total,
                "per_core_percent": cpu_per_core,
                "frequency_mhz": freq_mhz,
                "logical_cores": psutil.cpu_count(logical=True) or 1,
                "physical_cores": psutil.cpu_count(logical=False) or 1,
            },
            "ram": ram_stats,
            "disks": partitions,
            "network": net_stats,
            "gpus": gpu_stats,
            "battery": battery_stats,
            "user_context": user_info
        }

    def get_running_processes(self, limit: int = 30) -> List[Dict[str, Any]]:
        """Non-blocking process iteration with 1.5s result caching."""
        now = time.time()
        if self._proc_cache and (now - self._proc_cache_time) < 1.5:
            return self._proc_cache[:limit]

        num_cpus = psutil.cpu_count(logical=True) or 1
        proc_list = []
        current_pids = set()

        for proc in psutil.process_iter(['pid', 'name', 'memory_info']):
            try:
                info = proc.info
                pid = info['pid']
                if pid <= 4:  # Skip System / Idle PIDs
                    continue
                current_pids.add(pid)

                name = info['name'] or "Unknown"
                name_lower = name.lower()
                if name_lower in ("system idle process", "idle", "system", "registry", "smss.exe", "csrss.exe", "wininit.exe", "svchost.exe", "lsass.exe", "services.exe"):
                    continue

                # Friendly name and icon mapping for user apps
                friendly_name = name
                icon_type = "app"
                if "chrome" in name_lower:
                    friendly_name = "Chrome"
                    icon_type = "browser"
                elif "explorer" in name_lower:
                    friendly_name = "Explorer"
                    icon_type = "folder"
                elif "code" in name_lower:
                    friendly_name = "VS Code"
                    icon_type = "editor"
                elif "python" in name_lower:
                    friendly_name = "Python"
                    icon_type = "code"
                elif "cmd" in name_lower or "powershell" in name_lower or "terminal" in name_lower:
                    friendly_name = "Terminal"
                    icon_type = "terminal"

                proc_times = proc.cpu_times()
                cpu_time_total = proc_times.user + proc_times.system

                cpu_percent = 0.0
                if pid in self._last_proc_cpu_times:
                    prev_time, prev_stamp = self._last_proc_cpu_times[pid]
                    time_diff = now - prev_stamp
                    if time_diff > 0:
                        cpu_percent = ((cpu_time_total - prev_time) / time_diff) * 100.0 / num_cpus
                        cpu_percent = round(max(0.0, cpu_percent), 1)

                self._last_proc_cpu_times[pid] = (cpu_time_total, now)

                mem_bytes = info['memory_info'].rss if info.get('memory_info') else 0
                proc_list.append({
                    "pid": pid,
                    "name": friendly_name,
                    "raw_name": name,
                    "icon_type": icon_type,
                    "username": "",
                    "cpu_percent": cpu_percent,
                    "memory_bytes": mem_bytes,
                    "memory_percent": 0.0,
                    "status": f"CPU {cpu_percent}% | RAM {round(mem_bytes / (1024*1024), 1)} MB"
                })
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                continue

        # Clean stale PIDs
        self._last_proc_cpu_times = {
            k: v for k, v in self._last_proc_cpu_times.items() if k in current_pids
        }

        # Filter out System Idle Process
        proc_list = [p for p in proc_list if p["name"].lower() not in ("system idle process", "idle")]
        proc_list.sort(key=lambda p: (p['cpu_percent'], p['memory_bytes']), reverse=True)

        self._proc_cache = proc_list
        self._proc_cache_time = now
        return self._proc_cache[:limit]

    def get_browser_tabs(self) -> List[Dict[str, str]]:
        """Extracts open browser window & tab titles for Chrome and Edge."""
        tabs = []
        try:
            import win32gui
            def enum_windows_callback(hwnd, extra):
                if win32gui.IsWindowVisible(hwnd):
                    title = win32gui.GetWindowText(hwnd).strip()
                    if title and len(title) > 3:
                        if " - Google Chrome" in title or " - Chrome" in title:
                            clean_title = title.replace(" - Google Chrome", "").replace(" - Chrome", "").strip()
                            if clean_title and clean_title != "New Tab":
                                tabs.append({"browser": "Chrome", "title": clean_title, "id": f"tab_chrome_{len(tabs)}"})
                        elif " - Microsoft Edge" in title or " - Edge" in title:
                            clean_title = title.replace(" - Microsoft Edge", "").replace(" - Edge", "").strip()
                            if clean_title and clean_title != "New Tab":
                                tabs.append({"browser": "Edge", "title": clean_title, "id": f"tab_edge_{len(tabs)}"})
            win32gui.EnumWindows(enum_windows_callback, None)
        except Exception:
            pass
        return tabs[:10]

    def get_usb_devices(self) -> List[Dict[str, Any]]:
        """Enumerates USB devices using cached WMI check."""
        if self._has_wmi is False:
            return []
        
        devices = []
        try:
            if hasattr(psutil, 'WINDOWS') and psutil.WINDOWS:
                if self._has_wmi is None:
                    try:
                        import wmi
                        self._wmi_client = wmi.WMI()
                        self._has_wmi = True
                    except Exception:
                        self._has_wmi = False
                        return []

                if self._wmi_client:
                    for dev in self._wmi_client.Win32_PnPEntity(ConfigManagerErrorCode=0):
                        if dev.PNPDeviceID and dev.PNPDeviceID.startswith("USB"):
                            devices.append({
                                "device_id": dev.PNPDeviceID,
                                "name": dev.Name or dev.Description or "USB Device",
                                "status": dev.Status or "OK"
                            })
        except Exception:
            self._has_wmi = False
        return devices


# Global singleton instance
system_monitor = SystemMonitorService()
