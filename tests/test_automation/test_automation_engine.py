import asyncio

import pytest

from automation.base import AutomationJob
from automation.engine import AutomationEngine
from automation.scheduler import AutomationScheduler


@pytest.mark.asyncio
async def test_automation_job_creation_and_execution():
    engine = AutomationEngine()

    async def dummy_action(message: str):
        return f"Processed: {message}"

    job = engine.schedule_task(
        name="Test Task",
        action=dummy_action,
        interval_seconds=1.0,
        max_runs=1,
        message="Hello World",
    )

    assert job.name == "Test Task"
    assert job.enabled is True

    result = await engine.run_task_now(job.id)
    assert result.success is True
    assert result.output == "Processed: Hello World"
    assert job.run_count == 1
    assert job.enabled is False  # max_runs=1 reached


@pytest.mark.asyncio
async def test_scheduler_lifecycle():
    scheduler = AutomationScheduler()
    executed = False

    async def quick_task():
        nonlocal executed
        executed = True
        return "done"

    job = AutomationJob(
        name="Quick Task",
        action=quick_task,
        interval_seconds=0.1,
        max_runs=1,
    )
    scheduler.add_job(job)

    scheduler.start()
    await asyncio.sleep(0.3)
    await scheduler.stop()

    assert executed is True
    history = scheduler.get_history()
    assert len(history) >= 1
    assert history[0].success is True


@pytest.mark.asyncio
async def test_cancel_task():
    engine = AutomationEngine()
    job = engine.schedule_task("Task to Cancel", lambda: "ok", interval_seconds=10.0)

    assert len(engine.list_tasks()) == 1
    assert engine.cancel_task(job.id) is True
    assert len(engine.list_tasks()) == 0
