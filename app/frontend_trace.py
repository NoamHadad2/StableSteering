from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class FrontendTraceEvent(BaseModel):
    """One browser-side trace event posted back to the server."""

    event: str
    page: str
    session_id: str | None = None
    round_id: str | None = None
    details: dict[str, Any] = Field(default_factory=dict)
