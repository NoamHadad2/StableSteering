from __future__ import annotations

from app.core.schema import Candidate, FeedbackEvent, Session
from app.samplers.base import clamp_vector


class ContrastivePreferenceUpdater:
    """Updater that moves toward positives and away from negatives when available."""

    name = "contrastive_preference"

    def update(self, session: Session, candidates: list[Candidate], feedback: FeedbackEvent) -> tuple[list[float], dict]:
        """Use positive-versus-negative structure from the normalized feedback payload."""

        candidate_map = {candidate.id: candidate for candidate in candidates}
        positives, negatives = self._positive_negative_sets(feedback, candidate_map)
        if not positives:
            winner_id = feedback.normalized_payload["winner_candidate_id"]
            positives = [candidate_map[winner_id]]

        positive_center = self._centroid(positives, len(session.current_z))
        negative_center = self._centroid(negatives, len(session.current_z)) if negatives else [0.0 for _ in session.current_z]
        direction = [positive - negative for positive, negative in zip(positive_center, negative_center, strict=False)]
        alpha = 0.55 if negatives else 0.38
        updated = clamp_vector(
            [
                round(current + (alpha * delta), 6)
                for current, delta in zip(session.current_z, direction, strict=False)
            ],
            session.config.trust_radius,
        )
        winner_id = feedback.normalized_payload["winner_candidate_id"]
        return updated, {
            "updater": self.name,
            "winner_candidate_id": winner_id,
            "method": "contrastive_move",
            "positive_count": len(positives),
            "negative_count": len(negatives),
        }

    @staticmethod
    def _positive_negative_sets(feedback: FeedbackEvent, candidate_map: dict[str, Candidate]) -> tuple[list[Candidate], list[Candidate]]:
        normalized = feedback.normalized_payload
        positives: list[Candidate] = []
        negatives: list[Candidate] = []

        ranking = normalized.get("ranking")
        if ranking:
            positives = [candidate_map[candidate_id] for candidate_id in ranking[: max(1, len(ranking) // 2)] if candidate_id in candidate_map]
            negatives = [candidate_map[candidate_id] for candidate_id in ranking[max(1, len(ranking) // 2) :] if candidate_id in candidate_map]
            return positives, negatives

        approved = normalized.get("approved_candidate_ids", [])
        rejected = normalized.get("rejected_candidate_ids", [])
        if approved or rejected:
            positives = [candidate_map[candidate_id] for candidate_id in approved if candidate_id in candidate_map]
            negatives = [candidate_map[candidate_id] for candidate_id in rejected if candidate_id in candidate_map]
            return positives, negatives

        winner_id = normalized.get("winner_candidate_id")
        loser_id = normalized.get("loser_candidate_id")
        if winner_id and winner_id in candidate_map:
            positives = [candidate_map[winner_id]]
        if loser_id and loser_id in candidate_map:
            negatives = [candidate_map[loser_id]]
        return positives, negatives

    @staticmethod
    def _centroid(candidates: list[Candidate], dimensions: int) -> list[float]:
        if not candidates:
            return [0.0 for _ in range(dimensions)]
        values = [0.0 for _ in range(dimensions)]
        for candidate in candidates:
            for index, value in enumerate(candidate.z):
                values[index] += value
        return [value / len(candidates) for value in values]
