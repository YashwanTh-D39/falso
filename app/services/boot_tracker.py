"""BootTracker Service for FALSO.

Instruments and logs the 10 startup stages with precise timing,
2-second threshold warnings, fail-safe timeouts, and non-blocking background initialization.
"""

from __future__ import annotations

import logging
import time
from typing import Any, Dict, Optional

logger = logging.getLogger("falso.boot")

STAGE_NAMES = [
    "Configuration",       # Stage 1
    "Database",            # Stage 2
    "Ollama",              # Stage 3
    "Voice",               # Stage 4
    "Web Intelligence",    # Stage 5
    "Filesystem Indexer",  # Stage 6
    "Spatial Service",     # Stage 7
    "WebSocket",           # Stage 8
    "Living Orb",          # Stage 9
    "Frontend Ready"       # Stage 10
]


class BootTracker:
    """Manages system boot stage instrumentation, performance timing, and fail-safes."""

    def __init__(self) -> None:
        self.stage_results: Dict[int, Dict[str, Any]] = {}
        self.current_stage: int = 0
        self.boot_start_time: float = time.time()
        self.stage_start_times: Dict[int, float] = {}
        self.is_complete: bool = False

    def start_stage(self, stage_num: int) -> float:
        """Marks the start of a startup stage."""
        self.current_stage = stage_num
        t_start = time.time()
        self.stage_start_times[stage_num] = t_start
        name = STAGE_NAMES[stage_num - 1]
        logger.info("START: [%d] %s", stage_num, name)
        return t_start

    def end_stage(self, stage_num: int, details: Optional[str] = None) -> float:
        """Marks the completion of a startup stage with duration calculation and >2s warning."""
        t_end = time.time()
        t_start = self.stage_start_times.get(stage_num, t_end)
        duration = t_end - t_start
        name = STAGE_NAMES[stage_num - 1]

        self.stage_results[stage_num] = {
            "stage": stage_num,
            "name": name,
            "duration_sec": round(duration, 3),
            "details": details or "OK",
            "timestamp": t_end,
        }

        logger.info("END: [%d] %s | Duration: %.2fs", stage_num, name, duration)

        if duration > 2.0:
            logger.warning(
                "[STARTUP WARNING] Stage [%d] %s took %.2fs (exceeds 2.0s limit)",
                stage_num,
                name,
                duration,
            )

        if stage_num == 10:
            self.is_complete = True
            total_duration = t_end - self.boot_start_time
            logger.info("FALSO Core Boot Complete in %.2fs total", total_duration)

        return duration

    def fail_stage(self, stage_num: int, error_msg: str) -> None:
        """Handles graceful failure of an optional startup stage without hanging UI."""
        t_end = time.time()
        t_start = self.stage_start_times.get(stage_num, t_end)
        duration = t_end - t_start
        name = STAGE_NAMES[stage_num - 1]

        self.stage_results[stage_num] = {
            "stage": stage_num,
            "name": name,
            "duration_sec": round(duration, 3),
            "details": f"FAILED: {error_msg}",
            "timestamp": t_end,
        }

        logger.error(
            "END: [%d] %s (FAILED) | Duration: %.2fs | Error: %s",
            stage_num,
            name,
            duration,
            error_msg,
        )

    def get_boot_status(self) -> Dict[str, Any]:
        """Returns aggregated boot diagnostics."""
        return {
            "is_complete": self.is_complete,
            "current_stage": self.current_stage,
            "total_elapsed_sec": round(time.time() - self.boot_start_time, 2),
            "stages": [
                {
                    "stage": i,
                    "name": STAGE_NAMES[i - 1],
                    "status": self.stage_results.get(i, {}).get("details", "PENDING"),
                    "duration_sec": self.stage_results.get(i, {}).get("duration_sec", None),
                }
                for i in range(1, 11)
            ],
        }


boot_tracker = BootTracker()
