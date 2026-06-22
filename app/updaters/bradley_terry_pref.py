from __future__ import annotations

import math

from app.core.schema import Candidate, FeedbackEvent, Session
from app.samplers.base import clamp_vector


class BradleyTerryPreferenceUpdater:
    """Updater that fits simple latent utilities from pairwise preference relations."""

    name = "bradley_terry_preference"

    def update(self, session: Session, candidates: list[Candidate], feedback: FeedbackEvent) -> tuple[list[float], dict]:
        candidate_map = {candidate.id: candidate for candidate in candidates}
        pairwise_edges = self._pairwise_edges(feedback, candidate_map)
        winner_id = feedback.normalized_payload["winner_candidate_id"]
        if not pairwise_edges:
            loser_id = feedback.normalized_payload.get("loser_candidate_id")
            if loser_id and loser_id in candidate_map:
                pairwise_edges = [(winner_id, loser_id, 1.0)]
            else:
                pairwise_edges = [(winner_id, candidate_id, 1.0) for candidate_id in candidate_map if candidate_id != winner_id]

        logits = {candidate_id: 0.0 for candidate_id in candidate_map}
        for _ in range(12):
            gradients = {candidate_id: 0.0 for candidate_id in candidate_map}
            for winner_candidate_id, loser_candidate_id, weight in pairwise_edges:
                margin = logits[winner_candidate_id] - logits[loser_candidate_id]
                probability = 1.0 / (1.0 + math.exp(-margin))
                error = weight * (1.0 - probability)
                gradients[winner_candidate_id] += error
                gradients[loser_candidate_id] -= error
            for candidate_id in logits:
                logits[candidate_id] += 0.22 * gradients[candidate_id]

        weights = self._softmax(logits)
        center = self._weighted_center(candidate_map, weights, len(session.current_z))
        winner_vector = list(candidate_map[winner_id].z)
        updated = clamp_vector(
            [
                round(current + (0.5 * (target - current)) + (0.1 * (winner - current)), 6)
                for current, target, winner in zip(session.current_z, center, winner_vector, strict=False)
            ],
            session.config.trust_radius,
        )
        return updated, {
            "updater": self.name,
            "winner_candidate_id": winner_id,
            "method": "bradley_terry_softmax_center",
            "pair_count": len(pairwise_edges),
            "weights": {candidate_id: round(weight, 4) for candidate_id, weight in weights.items()},
        }

    @staticmethod
    def _pairwise_edges(feedback: FeedbackEvent, candidate_map: dict[str, Candidate]) -> list[tuple[str, str, float]]:
        normalized = feedback.normalized_payload
        edges: list[tuple[str, str, float]] = []
        ranking = normalized.get("ranking")
        if ranking:
            filtered = [candidate_id for candidate_id in ranking if candidate_id in candidate_map]
            for left_index, winner_id in enumerate(filtered):
                for right_index in range(left_index + 1, len(filtered)):
                    loser_id = filtered[right_index]
                    weight = 1.0 / float(right_index - left_index)
                    edges.append((winner_id, loser_id, weight))
            return edges
        if "ratings" in normalized:
            ratings = {
                candidate_id: float(score)
                for candidate_id, score in normalized["ratings"].items()
                if candidate_id in candidate_map
            }
            ordered = sorted(ratings.items(), key=lambda item: (-item[1], item[0]))
            for left_index, (winner_id, winner_score) in enumerate(ordered):
                for loser_id, loser_score in ordered[left_index + 1 :]:
                    if winner_score <= loser_score:
                        continue
                    edges.append((winner_id, loser_id, max(0.25, winner_score - loser_score)))
            return edges
        approved = [candidate_id for candidate_id in normalized.get("approved_candidate_ids", []) if candidate_id in candidate_map]
        rejected = [candidate_id for candidate_id in normalized.get("rejected_candidate_ids", []) if candidate_id in candidate_map]
        for winner_id in approved:
            for loser_id in rejected:
                edges.append((winner_id, loser_id, 1.0))
        winner_id = normalized.get("winner_candidate_id")
        loser_id = normalized.get("loser_candidate_id")
        if winner_id and loser_id and winner_id in candidate_map and loser_id in candidate_map:
            edges.append((winner_id, loser_id, 1.0))
        return edges

    @staticmethod
    def _softmax(logits: dict[str, float]) -> dict[str, float]:
        max_logit = max(logits.values()) if logits else 0.0
        exp_values = {candidate_id: math.exp(value - max_logit) for candidate_id, value in logits.items()}
        total = sum(exp_values.values()) or 1.0
        return {candidate_id: value / total for candidate_id, value in exp_values.items()}

    @staticmethod
    def _weighted_center(candidate_map: dict[str, Candidate], weights: dict[str, float], dimensions: int) -> list[float]:
        center = [0.0 for _ in range(dimensions)]
        for candidate_id, weight in weights.items():
            candidate = candidate_map[candidate_id]
            for index, value in enumerate(candidate.z):
                center[index] += weight * value
        return center
