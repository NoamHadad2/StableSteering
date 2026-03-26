from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.core.config import settings


def utc_timestamp() -> str:
    """Return an ISO-8601 UTC timestamp for trace events."""

    return datetime.now(timezone.utc).isoformat()


class TraceRecorder:
    """Persist lightweight backend and frontend trace events as JSON lines."""

    def __init__(self, trace_dir: Path | None = None) -> None:
        self.trace_dir = trace_dir or settings.traces_dir
        self.trace_dir.mkdir(parents=True, exist_ok=True)
        self.backend_path = self.trace_dir / "backend-events.jsonl"
        self.frontend_path = self.trace_dir / "frontend-events.jsonl"

    def append_backend(self, event: str, payload: dict[str, Any]) -> None:
        """Append one backend event to the shared backend trace stream."""

        self._append(self.backend_path, event, payload)

    def append_frontend(self, event: str, payload: dict[str, Any]) -> None:
        """Append one frontend event to the shared frontend trace stream."""

        self._append(self.frontend_path, event, payload)

    def _append(self, path: Path, event: str, payload: dict[str, Any]) -> None:
        record = {"timestamp": utc_timestamp(), "event": event, "payload": payload}
        with path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record) + "\n")
