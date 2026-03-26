from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from enum import Enum
from inspect import signature
from threading import Lock
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

    def __init__(self, *, max_workers: int = 4, max_jobs: int = 200) -> None:
        self._jobs: dict[str, JobRecord] = {}
        self._lock = Lock()
        self._executor = ThreadPoolExecutor(max_workers=max_workers, thread_name_prefix="stable-steering-job")
        self._max_jobs = max_jobs

    async def submit(self, operation: str, fn: Callable[[], Any]) -> JobRecord:
        """Create a job record and execute the callable in a worker thread."""

        job = JobRecord(operation=operation)
        with self._lock:
            self._prune_locked()
            self._jobs[job.id] = job
        self._executor.submit(self._run_sync, job.id, fn)
        return job.model_copy(deep=True)

    async def get(self, job_id: str) -> JobRecord | None:
        """Return the current job snapshot if it exists."""

        with self._lock:
            job = self._jobs.get(job_id)
            return job.model_copy(deep=True) if job else None

    def _run_sync(self, job_id: str, fn: Callable[[], Any]) -> None:
        """Execute one submitted job and persist its status transitions."""

        self._update(job_id, state=JobState.running, progress=12, status_message="Starting work")
        try:
            try:
                arity = len(signature(fn).parameters)
            except (TypeError, ValueError):
                arity = 0
            if arity >= 1:
                result = fn(lambda progress, message: self.update_progress(job_id, progress, message))
            else:
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
            status_message="Completed successfully",
            result=payload,
            error=None,
        )

    def update_progress(self, job_id: str, progress: int, status_message: str) -> None:
        """Expose safe phase-level progress updates to long-running jobs."""

        self._update(job_id, state=JobState.running, progress=progress, status_message=status_message)

    def _update(self, job_id: str, **changes: Any) -> None:
        """Mutate one job record in place under the manager lock."""

        with self._lock:
            job = self._jobs[job_id]
            for key, value in changes.items():
                setattr(job, key, value)
            job.updated_at = utc_now()
            self._prune_locked()

    def _prune_locked(self) -> None:
        """Drop old completed jobs so the in-memory registry remains bounded."""

        overflow = len(self._jobs) - self._max_jobs
        if overflow <= 0:
            return
        completed_ids = [
            job.id
            for job in sorted(self._jobs.values(), key=lambda record: (record.updated_at, record.created_at))
            if job.state in {JobState.succeeded, JobState.failed}
        ]
        for job_id in completed_ids[:overflow]:
            self._jobs.pop(job_id, None)

    def close(self) -> None:
        """Shut down worker threads when the app exits."""

        self._executor.shutdown(wait=False, cancel_futures=False)
