"""BootTracker Service for FALSO.

Instruments and logs the 10 startup stages with duration tracking,
2-second threshold warnings, and non-blocking background initialization.
"""

import asyncio
import logging
import time
from typing import Any, Dict, List, Optional

logger = logging.getLogger("falso.boot")

STAGE_DESCRIPTIONS = [
    "Config loaded",                  # Stage 1
    "Database initialized",           # Stage 2
    "Ollama connection verified",     # Stage 3
    "Filesystem indexer started",     # Stage 4
    "Watchdog started",               # Stage 5
    "Spatial broadcaster started",    # Stage 6
    "WebSocket initialized",          # Stage 7
    "Voice services initialized",     # Stage 8
    "Frontend handshake completed",  # Stage 9
    "BOOT COMPLETE"                   # Stage 10
]


class BootTracker:
    """Manages system boot stage instrumentation and performance tracking."""

    def __init__(self):
        self.stage_results: Dict[int, Dict[str, Any]] = {}
        self.current_stage: int = 0
        self.boot_start_time: float = time.time()
        self.last_stage_time: float = time.time()
        self.is_complete: bool = False

    def log_stage(self, stage_num: int, duration_sec: float, details: Optional[str] = None):
        """Logs a completed startup stage with duration and 2s warning check."""
        self.current_stage = stage_num
        now = time.time()
        desc = STAGE_DESCRIPTIONS[stage_num - 1]
        
        self.stage_results[stage_num] = {
            "stage": stage_num,
            "description": desc,
            "duration_sec": round(duration_sec, 3),
            "details": details or "OK",
            "timestamp": now
        }
        self.last_stage_time = now

        # Exact required log format: [X/10] Stage description
        log_msg = f"[{stage_num}/10] {desc} ({duration_sec:.2f}s)"
        
        if duration_sec > 2.0:
            logger.warning("WARNING: Stage [%d/10] '%s' took %.2fs (exceeds 2s threshold)", stage_num, desc, duration_sec)
        else:
            logger.info("%s", log_msg)

        if stage_num == 10:
            self.is_complete = True
            total_time = now - self.boot_start_time
            logger.info("FALSO Spatial OS Boot Completed in %.2fs total", total_time)

    def get_boot_status(self) -> Dict[str, Any]:
        """Returns aggregated boot diagnostics."""
        return {
            "is_complete": self.is_complete,
            "current_stage": self.current_stage,
            "total_elapsed_sec": round(time.time() - self.boot_start_time, 2),
            "stages": [
                {
                    "stage": i,
                    "name": STAGE_DESCRIPTIONS[i - 1],
                    "status": self.stage_results.get(i, {}).get("details", "PENDING"),
                    "duration_sec": self.stage_results.get(i, {}).get("duration_sec", None)
                }
                for i in range(1, 11)
            ]
        }


# Global singleton boot tracker
boot_tracker = BootTracker()
