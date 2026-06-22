from __future__ import annotations

from typing import Protocol

from app.core.schema import Candidate, FeedbackEvent, Session


class Updater(Protocol):
    """Protocol shared by all state update strategies."""

    def update(self, session: Session, candidates: list[Candidate], feedback: FeedbackEvent) -> tuple[list[float], dict]:
        ...
