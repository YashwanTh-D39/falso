from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable
from typing import Any

from automation.base import AutomationJob, JobResult
from automation.scheduler import AutomationScheduler

logger = logging.getLogger(__name__)


class AutomationEngine:
    """High-level entry point for task automation in Falso."""

    def __init__(self, scheduler: AutomationScheduler | None = None) -> None:
        self.scheduler = scheduler or AutomationScheduler()

    def schedule_task(
        self,
        name: str,
        action: Callable[..., Awaitable[Any]] | str,
        interval_seconds: float,
        max_runs: int | None = None,
        **kwargs: Any,
    ) -> AutomationJob:
        job = AutomationJob(
            name=name,
            action=action,
            interval_seconds=interval_seconds,
            max_runs=max_runs,
            kwargs=kwargs,
        )
        self.scheduler.add_job(job)
        return job

    def cancel_task(self, task_id: str) -> bool:
        return self.scheduler.remove_job(task_id)

    def list_tasks(self) -> list[AutomationJob]:
        return self.scheduler.list_jobs()

    async def run_task_now(self, task_id: str) -> JobResult:
        return await self.scheduler.execute_job_now(task_id)

    def start(self) -> None:
        self.scheduler.start()

    async def stop(self) -> None:
        await self.scheduler.stop()
