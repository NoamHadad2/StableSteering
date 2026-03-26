from __future__ import annotations

import asyncio
from datetime import datetime
from enum import Enum
from threading import Lock, Thread
from typing import Any, Callable
from uuid import uuid4

from pydantic import BaseModel, Field

from app.core.schema import utc_now


class JobState(str, Enum):
    queued = "queued"
    running = "running"
    succeeded = "succeeded"
    failed = "failed"


class JobRecord(BaseModel):
    """Serializable status snapshot for one asynchronous job."""

    id: str = Field(default_factory=lambda: f"job_{uuid4().hex[:12]}")
    operation: str
    state: JobState = JobState.queued
    progress: int = 0
    status_message: str = "Queued"
    result: dict[str, Any] | None = None
    error: str | None = None
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)


class AsyncJobManager:
    """Small in-memory async job manager for long-running user operations."""

    def __init__(self) -> None:
        self._jobs: dict[str, JobRecord] = {}
        self._lock = Lock()

    async def submit(self, operation: str, fn: Callable[[], Any]) -> JobRecord:
        """Create a job record and execute the callable in a worker thread."""

        job = JobRecord(operation=operation)
        with self._lock:
            self._jobs[job.id] = job
        Thread(target=self._run_sync, args=(job.id, fn), daemon=True).start()
        return job.model_copy(deep=True)

    async def get(self, job_id: str) -> JobRecord | None:
        """Return the current job snapshot if it exists."""

        with self._lock:
            job = self._jobs.get(job_id)
            return job.model_copy(deep=True) if job else None

    def _run_sync(self, job_id: str, fn: Callable[[], Any]) -> None:
        """Execute one submitted job and persist its status transitions."""

        self._update(job_id, state=JobState.running, progress=15, status_message="Running")
        try:
            result = fn()
        except Exception as exc:
            self._update(
                job_id,
                state=JobState.failed,
                progress=100,
                status_message="Failed",
                error=str(exc),
            )
            return

        payload = result.model_dump(mode="json") if hasattr(result, "model_dump") else result
        self._update(
            job_id,
            state=JobState.succeeded,
            progress=100,
            status_message="Completed",
            result=payload,
            error=None,
        )

    def _update(self, job_id: str, **changes: Any) -> None:
        """Mutate one job record in place under the manager lock."""

        with self._lock:
            job = self._jobs[job_id]
            for key, value in changes.items():
                setattr(job, key, value)
            job.updated_at = utc_now()
