from __future__ import annotations

from app.core.schema import Candidate, FeedbackEvent, Session


class WinnerCopyUpdater:
    """Simplest updater: replace the incumbent with the winner exactly."""

    name = "winner_copy"

    def update(self, session: Session, candidates: list[Candidate], feedback: FeedbackEvent) -> tuple[list[float], dict]:
        """Return the winning candidate's steering vector unchanged."""

        winner_id = feedback.normalized_payload["winner_candidate_id"]
        winner = next(candidate for candidate in candidates if candidate.id == winner_id)
        return winner.z, {"updater": self.name, "winner_candidate_id": winner.id, "method": "copy"}
