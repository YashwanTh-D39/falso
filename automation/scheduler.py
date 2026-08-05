from __future__ import annotations

import asyncio
import inspect
import logging
import time
from datetime import UTC, datetime

from automation.base import AutomationJob, JobResult

logger = logging.getLogger(__name__)


class AutomationScheduler:
    """Async background task scheduler for recurring automation jobs."""

    def __init__(self) -> None:
        self._jobs: dict[str, AutomationJob] = {}
        self._task: asyncio.Task | None = None
        self._running = False
        self._history: list[JobResult] = []

    def add_job(self, job: AutomationJob) -> str:
        self._jobs[job.id] = job
        logger.info("Automation job added: %s (id=%s, interval=%.1fs)", job.name, job.id, job.interval_seconds)
        return job.id

    def remove_job(self, job_id: str) -> bool:
        if job_id in self._jobs:
            del self._jobs[job_id]
            logger.info("Automation job removed: %s", job_id)
            return True
        return False

    def get_job(self, job_id: str) -> AutomationJob | None:
        return self._jobs.get(job_id)

    def list_jobs(self) -> list[AutomationJob]:
        return list(self._jobs.values())

    def get_history(self, limit: int = 50) -> list[JobResult]:
        return self._history[-limit:]

    async def execute_job_now(self, job_id: str) -> JobResult:
        job = self._jobs.get(job_id)
        if not job:
            return JobResult(
                job_id=job_id,
                success=False,
                error=f"Job not found: {job_id}",
            )
        return await self._run_single_job(job)

    async def _run_single_job(self, job: AutomationJob) -> JobResult:
        job.last_run = datetime.now(UTC).isoformat()
        job.run_count += 1

        try:
            if callable(job.action):
                if inspect.iscoroutinefunction(job.action):
                    res = await job.action(**job.kwargs)
                else:
                    res = job.action(**job.kwargs)
            else:
                res = f"Executed action: {job.action}"

            result = JobResult(job_id=job.id, success=True, output=res)
            logger.info("Automation job '%s' (%s) succeeded", job.name, job.id)
        except Exception as e:
            result = JobResult(job_id=job.id, success=False, error=str(e))
            logger.exception("Automation job '%s' (%s) failed", job.name, job.id)

        self._history.append(result)

        if job.max_runs is not None and job.run_count >= job.max_runs:
            job.enabled = False
            logger.info("Automation job '%s' reached max_runs (%d), disabling", job.name, job.max_runs)

        return result

    def start(self) -> None:
        if self._running or self._task is not None:
            return
        self._running = True
        self._task = asyncio.create_task(self._loop())
        logger.info("AutomationScheduler started")

    async def stop(self) -> None:
        self._running = False
        if self._task is not None:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None
        logger.info("AutomationScheduler stopped")

    async def _loop(self) -> None:
        last_checks: dict[str, float] = {}
        while self._running:
            now = time.monotonic()
            for job in list(self._jobs.values()):
                if not job.enabled:
                    continue
                last_time = last_checks.get(job.id, 0.0)
                if now - last_time >= job.interval_seconds:
                    last_checks[job.id] = now
                    asyncio.create_task(self._run_single_job(job))
            await asyncio.sleep(1.0)
