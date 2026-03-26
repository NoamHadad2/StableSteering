from __future__ import annotations

from app.core.schema import Candidate, FeedbackEvent, Session


class LinearPreferenceUpdater:
    """Approximate gradient-style move toward the winning candidate."""

    name = "linear_preference"

    def update(self, session: Session, candidates: list[Candidate], feedback: FeedbackEvent) -> tuple[list[float], dict]:
        """Apply a stronger weighted move toward the selected winner."""

        winner_id = feedback.normalized_payload["winner_candidate_id"]
        winner = next(candidate for candidate in candidates if candidate.id == winner_id)
        alpha = 0.65
        updated = [
            round((1 - alpha) * current + alpha * target, 6)
            for current, target in zip(session.current_z, winner.z, strict=False)
        ]
        return updated, {"updater": self.name, "winner_candidate_id": winner.id, "method": "linear_move"}
