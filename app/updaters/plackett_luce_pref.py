from __future__ import annotations

import math

from app.core.schema import Candidate, FeedbackEvent, Session
from app.samplers.base import clamp_vector


class PlackettLucePreferenceUpdater:
    """Updater that fits listwise worth parameters from ranking-style preference signals."""

    name = "plackett_luce_preference"

    def update(self, session: Session, candidates: list[Candidate], feedback: FeedbackEvent) -> tuple[list[float], dict]:
        candidate_map = {candidate.id: candidate for candidate in candidates}
        ranking = self._ordered_candidates(feedback, candidate_map)
        winner_id = feedback.normalized_payload["winner_candidate_id"]
        if not ranking:
            ranking = [winner_id]

        logits = {candidate_id: 0.0 for candidate_id in candidate_map}
        for _ in range(16):
            gradients = {candidate_id: -0.015 * logits[candidate_id] for candidate_id in candidate_map}
            for prefix_index, winner_candidate_id in enumerate(ranking):
                remaining = [candidate_id for candidate_id in ranking[prefix_index:] if candidate_id in candidate_map]
                if not remaining:
                    continue
                exp_values = {candidate_id: math.exp(logits[candidate_id]) for candidate_id in remaining}
                total = sum(exp_values.values()) or 1.0
                gradients[winner_candidate_id] += 1.0
                for candidate_id, value in exp_values.items():
                    gradients[candidate_id] -= value / total
            for candidate_id in candidate_map:
                logits[candidate_id] += 0.2 * gradients[candidate_id]

        weights = self._softmax_with_floor(logits, floor=0.04)
        center = self._weighted_center(candidate_map, weights, len(session.current_z))
        winner_vector = list(candidate_map[winner_id].z)
        updated = clamp_vector(
            [
                round(current + (0.48 * (target - current)) + (0.12 * (winner - current)), 6)
                for current, target, winner in zip(session.current_z, center, winner_vector, strict=False)
            ],
            session.config.trust_radius,
        )
        return updated, {
            "updater": self.name,
            "winner_candidate_id": winner_id,
            "method": "plackett_luce_listwise_center",
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
        if ordered:
            trailing = [candidate_id for candidate_id in candidate_map if candidate_id not in ordered]
            return ordered + trailing
        return []

    @staticmethod
    def _softmax_with_floor(logits: dict[str, float], floor: float) -> dict[str, float]:
        max_logit = max(logits.values()) if logits else 0.0
        exp_values = {candidate_id: math.exp(value - max_logit) for candidate_id, value in logits.items()}
        total = sum(exp_values.values()) or 1.0
        raw = {candidate_id: value / total for candidate_id, value in exp_values.items()}
        candidate_count = max(1, len(raw))
        floor = min(floor, 1.0 / candidate_count)
        adjusted = {candidate_id: floor + ((1.0 - (floor * candidate_count)) * weight) for candidate_id, weight in raw.items()}
        adjusted_total = sum(adjusted.values()) or 1.0
        return {candidate_id: weight / adjusted_total for candidate_id, weight in adjusted.items()}

    @staticmethod
    def _weighted_center(candidate_map: dict[str, Candidate], weights: dict[str, float], dimensions: int) -> list[float]:
        center = [0.0 for _ in range(dimensions)]
        for candidate_id, weight in weights.items():
            candidate = candidate_map[candidate_id]
            for index, value in enumerate(candidate.z):
                center[index] += weight * value
        return center
