from __future__ import annotations

import asyncio
import time

from app.core.jobs import AsyncJobManager


def test_job_manager_prunes_old_completed_jobs() -> None:
    manager = AsyncJobManager(max_workers=1, max_jobs=2)

    async def exercise() -> None:
        first = await manager.submit("job:first", lambda: {"ok": 1})
        second = await manager.submit("job:second", lambda: {"ok": 2})
        third = await manager.submit("job:third", lambda: {"ok": 3})

        await asyncio.sleep(0.1)

        assert await manager.get(first.id) is None
        assert (await manager.get(second.id)).state.value == "succeeded"
        assert (await manager.get(third.id)).state.value == "succeeded"

    asyncio.run(exercise())


def test_job_manager_supports_phase_progress_updates() -> None:
    manager = AsyncJobManager(max_workers=1, max_jobs=5)

    async def exercise() -> None:
        def phased_job(progress) -> dict[str, int]:
            progress(20, "Sampling candidate directions")
            time.sleep(0.02)
            progress(60, "Rendering candidate images on the model backend")
            time.sleep(0.02)
            progress(90, "Refreshing trace report and replay data")
            time.sleep(0.02)
            return {"ok": 1}

        job = await manager.submit("job:phased", phased_job)

        seen_messages: set[str] = set()
        for _ in range(30):
            snapshot = await manager.get(job.id)
            if snapshot is not None:
                seen_messages.add(snapshot.status_message)
                if snapshot.state.value == "succeeded":
                    break
            await asyncio.sleep(0.01)

        assert "Sampling candidate directions" in seen_messages
        assert "Rendering candidate images on the model backend" in seen_messages
        assert "Refreshing trace report and replay data" in seen_messages
        assert (await manager.get(job.id)).state.value == "succeeded"

    asyncio.run(exercise())
