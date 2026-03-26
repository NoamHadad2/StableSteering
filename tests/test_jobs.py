from __future__ import annotations

import asyncio

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
