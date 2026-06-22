from __future__ import annotations

import math

from app.core.schema import Candidate, FeedbackEvent, Session
from app.samplers.base import clamp_vector


class SoftmaxPreferenceUpdater:
    """Updater that turns graded feedback into a soft target state with contrast against low-rated candidates."""

    name = "softmax_preference"

    def update(self, session: Session, candidates: list[Candidate], feedback: FeedbackEvent) -> tuple[list[float], dict]:
        candidate_map = {candidate.id: candidate for candidate in candidates}
        scores = self._scores_from_feedback(feedback, candidate_map)
        winner_id = feedback.normalized_payload["winner_candidate_id"]
        if not scores:
            scores = {winner_id: 1.0}

        positive_weights = self._softmax(scores, temperature=0.42)
        negative_scores = {candidate_id: max(scores.values()) - score for candidate_id, score in scores.items()}
        negative_weights = self._softmax(negative_scores, temperature=0.58)

        positive_center = self._weighted_center(candidate_map, positive_weights, len(session.current_z))
        negative_center = self._weighted_center(candidate_map, negative_weights, len(session.current_z))
        winner_vector = list(candidate_map[winner_id].z)

        updated = clamp_vector(
            [
                round(
                    current
                    + (0.58 * (positive - current))
                    + (0.18 * (winner - current))
                    - (0.12 * (negative - current)),
                    6,
                )
                for current, positive, negative, winner in zip(
                    session.current_z,
                    positive_center,
                    negative_center,
                    winner_vector,
                    strict=False,
                )
            ],
            session.config.trust_radius,
        )
        return updated, {
            "updater": self.name,
            "winner_candidate_id": winner_id,
            "method": "softmax_weighted_contrastive_centroid",
            "weight_count": len(positive_weights),
            "positive_weights": {candidate_id: round(weight, 4) for candidate_id, weight in positive_weights.items()},
        }

    @staticmethod
    def _scores_from_feedback(feedback: FeedbackEvent, candidate_map: dict[str, Candidate]) -> dict[str, float]:
        normalized = feedback.normalized_payload
        if "ratings" in normalized:
            return {
                candidate_id: float(score)
                for candidate_id, score in normalized["ratings"].items()
                if candidate_id in candidate_map
            }
        ranking = normalized.get("ranking")
        if ranking:
            count = len(ranking)
            return {
                candidate_id: float(count - index)
                for index, candidate_id in enumerate(ranking)
                if candidate_id in candidate_map
            }
        approved = normalized.get("approved_candidate_ids", [])
        rejected = normalized.get("rejected_candidate_ids", [])
        if approved or rejected:
            scores: dict[str, float] = {}
            for candidate_id in approved:
                if candidate_id in candidate_map:
                    scores[candidate_id] = 1.0
            for candidate_id in rejected:
                if candidate_id in candidate_map and candidate_id not in scores:
                    scores[candidate_id] = 0.0
            return scores
        winner_id = normalized.get("winner_candidate_id")
        loser_id = normalized.get("loser_candidate_id")
        scores = {}
        if winner_id and winner_id in candidate_map:
            scores[winner_id] = 1.0
        if loser_id and loser_id in candidate_map:
            scores[loser_id] = 0.0
        return scores

    @staticmethod
    def _softmax(scores: dict[str, float], temperature: float) -> dict[str, float]:
        if not scores:
            return {}
        scaled_values = {candidate_id: score / max(temperature, 1e-6) for candidate_id, score in scores.items()}
        max_value = max(scaled_values.values())
        exp_values = {candidate_id: math.exp(value - max_value) for candidate_id, value in scaled_values.items()}
        total = sum(exp_values.values())
        if total == 0.0:
            uniform = 1.0 / len(exp_values)
            return {candidate_id: uniform for candidate_id in exp_values}
        return {candidate_id: value / total for candidate_id, value in exp_values.items()}

    @staticmethod
    def _weighted_center(candidate_map: dict[str, Candidate], weights: dict[str, float], dimensions: int) -> list[float]:
        if not weights:
            return [0.0 for _ in range(dimensions)]
        center = [0.0 for _ in range(dimensions)]
        total = sum(weights.values())
        for candidate_id, weight in weights.items():
            candidate = candidate_map[candidate_id]
            for index, value in enumerate(candidate.z):
                center[index] += (weight / total) * value
        return center
