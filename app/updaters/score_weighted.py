from __future__ import annotations

from app.core.schema import Candidate, FeedbackEvent, Session
from app.samplers.base import clamp_vector


class ScoreWeightedPreferenceUpdater:
    """Updater that uses richer score-like feedback to compute a weighted target state."""

    name = "score_weighted_preference"

    def update(self, session: Session, candidates: list[Candidate], feedback: FeedbackEvent) -> tuple[list[float], dict]:
        """Move toward a weighted centroid derived from ratings, rankings, or approvals."""

        candidate_map = {candidate.id: candidate for candidate in candidates}
        weights = self._weights_from_feedback(feedback, candidate_map)
        if not weights:
            winner_id = feedback.normalized_payload["winner_candidate_id"]
            weights = {winner_id: 1.0}

        total_weight = sum(weights.values())
        target = [0.0 for _ in session.current_z]
        for candidate_id, weight in weights.items():
            candidate = candidate_map[candidate_id]
            for index, value in enumerate(candidate.z):
                target[index] += (weight / total_weight) * value

        alpha = 0.68
        updated = clamp_vector(
            [
                round(((1 - alpha) * current) + (alpha * target_value), 6)
                for current, target_value in zip(session.current_z, target, strict=False)
            ],
            session.config.trust_radius,
        )
        winner_id = feedback.normalized_payload["winner_candidate_id"]
        return updated, {
            "updater": self.name,
            "winner_candidate_id": winner_id,
            "method": "score_weighted_centroid",
            "weight_count": len(weights),
            "weights": {candidate_id: round(weight, 4) for candidate_id, weight in weights.items()},
        }

    @staticmethod
    def _weights_from_feedback(feedback: FeedbackEvent, candidate_map: dict[str, Candidate]) -> dict[str, float]:
        normalized = feedback.normalized_payload
        if "ratings" in normalized:
            ratings = normalized["ratings"]
            min_rating = min(float(value) for value in ratings.values())
            return {
                candidate_id: max(float(score) - min_rating + 1.0, 0.05)
                for candidate_id, score in ratings.items()
                if candidate_id in candidate_map
            }
        if "ranking" in normalized:
            ranking = normalized["ranking"]
            count = len(ranking)
            return {
                candidate_id: float(count - index)
                for index, candidate_id in enumerate(ranking)
                if candidate_id in candidate_map
            }
        if "approved_candidate_ids" in normalized:
            approved = normalized["approved_candidate_ids"]
            return {candidate_id: 1.0 for candidate_id in approved if candidate_id in candidate_map}
        winner_id = normalized.get("winner_candidate_id")
        if winner_id and winner_id in candidate_map:
            return {winner_id: 1.0}
        return {}
