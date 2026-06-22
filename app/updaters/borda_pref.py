from __future__ import annotations

from app.core.schema import Candidate, FeedbackEvent, Session
from app.samplers.base import clamp_vector


class BordaPreferenceUpdater:
    """Updater that converts ordinal preference information into Borda-style weights."""

    name = "borda_preference"

    def update(self, session: Session, candidates: list[Candidate], feedback: FeedbackEvent) -> tuple[list[float], dict]:
        candidate_map = {candidate.id: candidate for candidate in candidates}
        ranking = self._ordered_candidates(feedback, candidate_map)
        winner_id = feedback.normalized_payload["winner_candidate_id"]
        if not ranking:
            ranking = [winner_id]

        scores = {
            candidate_id: float(len(ranking) - index)
            for index, candidate_id in enumerate(ranking)
        }
        score_total = sum(scores.values()) or 1.0
        weights = {candidate_id: score / score_total for candidate_id, score in scores.items()}
        positive_center = self._weighted_center(candidate_map, weights, len(session.current_z))
        lower_half = ranking[max(1, len(ranking) // 2) :]
        negative_center = self._centroid([candidate_map[candidate_id] for candidate_id in lower_half if candidate_id in candidate_map], len(session.current_z))
        winner_vector = list(candidate_map[winner_id].z)

        updated = clamp_vector(
            [
                round(
                    current
                    + (0.46 * (positive - current))
                    + (0.14 * (winner - current))
                    - (0.07 * (negative - current)),
                    6,
                )
                for current, positive, winner, negative in zip(
                    session.current_z,
                    positive_center,
                    winner_vector,
                    negative_center,
                    strict=False,
                )
            ],
            session.config.trust_radius,
        )
        return updated, {
            "updater": self.name,
            "winner_candidate_id": winner_id,
            "method": "borda_weighted_centroid",
            "ranking_length": len(ranking),
            "weights": {candidate_id: round(weight, 4) for candidate_id, weight in weights.items()},
        }

    @staticmethod
    def _ordered_candidates(feedback: FeedbackEvent, candidate_map: dict[str, Candidate]) -> list[str]:
        normalized = feedback.normalized_payload
        if "ranking" in normalized and normalized["ranking"]:
            return [candidate_id for candidate_id in normalized["ranking"] if candidate_id in candidate_map]
        if "ratings" in normalized:
            return [
                candidate_id
                for candidate_id, _score in sorted(
                    normalized["ratings"].items(),
                    key=lambda item: (-float(item[1]), item[0]),
                )
                if candidate_id in candidate_map
            ]
        approved = [candidate_id for candidate_id in normalized.get("approved_candidate_ids", []) if candidate_id in candidate_map]
        rejected = [candidate_id for candidate_id in normalized.get("rejected_candidate_ids", []) if candidate_id in candidate_map]
        if approved or rejected:
            return approved + rejected
        winner_id = normalized.get("winner_candidate_id")
        loser_id = normalized.get("loser_candidate_id")
        ordered = [candidate_id for candidate_id in [winner_id, loser_id] if candidate_id in candidate_map]
        return ordered

    @staticmethod
    def _weighted_center(candidate_map: dict[str, Candidate], weights: dict[str, float], dimensions: int) -> list[float]:
        if not weights:
            return [0.0 for _ in range(dimensions)]
        center = [0.0 for _ in range(dimensions)]
        for candidate_id, weight in weights.items():
            candidate = candidate_map[candidate_id]
            for index, value in enumerate(candidate.z):
                center[index] += weight * value
        return center

    @staticmethod
    def _centroid(candidates: list[Candidate], dimensions: int) -> list[float]:
        if not candidates:
            return [0.0 for _ in range(dimensions)]
        values = [0.0 for _ in range(dimensions)]
        for candidate in candidates:
            for index, value in enumerate(candidate.z):
                values[index] += value
        return [value / len(candidates) for value in values]
