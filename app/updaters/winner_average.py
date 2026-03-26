from __future__ import annotations

from app.core.schema import Candidate, FeedbackEvent, Session


class WinnerAverageUpdater:
    """Smooth updater that moves halfway toward the winning candidate."""

    name = "winner_average"

    def update(self, session: Session, candidates: list[Candidate], feedback: FeedbackEvent) -> tuple[list[float], dict]:
        """Blend incumbent and winning vectors to reduce abrupt jumps."""

        winner_id = feedback.normalized_payload["winner_candidate_id"]
        winner = next(candidate for candidate in candidates if candidate.id == winner_id)
        updated = [
            round((current * 0.5) + (target * 0.5), 6)
            for current, target in zip(session.current_z, winner.z, strict=False)
        ]
        return updated, {"updater": self.name, "winner_candidate_id": winner.id, "method": "average"}
