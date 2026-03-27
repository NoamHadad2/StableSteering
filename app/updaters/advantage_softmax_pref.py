from __future__ import annotations

import math

from app.core.schema import Candidate, FeedbackEvent, Session
from app.samplers.base import clamp_vector


class AdvantageSoftmaxPreferenceUpdater:
    """Updater that weights candidates by advantage over the carried-forward incumbent."""

    name = "advantage_softmax_preference"

    def update(self, session: Session, candidates: list[Candidate], feedback: FeedbackEvent) -> tuple[list[float], dict]:
        candidate_map = {candidate.id: candidate for candidate in candidates}
        scores = self._scores_from_feedback(feedback, candidate_map)
        winner_id = feedback.normalized_payload["winner_candidate_id"]
        incumbent_candidate = next((candidate for candidate in candidates if candidate.generation_params.get("carried_forward")), None)
        incumbent_score = float(scores.get(incumbent_candidate.id, scores.get(winner_id, 1.0))) if incumbent_candidate is not None else float(scores.get(winner_id, 1.0))

        logits: dict[str, float] = {}
        any_positive_advantage = False
        for candidate in candidates:
            raw_score = float(scores.get(candidate.id, 0.0))
            advantage = raw_score - incumbent_score
            if advantage > 1e-8:
                any_positive_advantage = True
            logits[candidate.id] = advantage / 0.22
            if candidate.generation_params.get("carried_forward"):
                logits[candidate.id] -= 0.12

        if not any_positive_advantage and incumbent_candidate is not None:
            logits = {candidate.id: (-0.35 if candidate.id == incumbent_candidate.id else -0.65) for candidate in candidates}
            logits[winner_id] += 0.18

        weights = self._softmax_with_floor(logits, floor=0.035)
        center = self._weighted_center(candidate_map, weights, len(session.current_z))
        winner_vector = list(candidate_map[winner_id].z)
        updated = clamp_vector(
            [
                round(current + (0.46 * (target - current)) + (0.1 * (winner - current)), 6)
                for current, target, winner in zip(session.current_z, center, winner_vector, strict=False)
            ],
            session.config.trust_radius,
        )
        return updated, {
            "updater": self.name,
            "winner_candidate_id": winner_id,
            "method": "incumbent_advantage_softmax",
            "incumbent_score": round(incumbent_score, 4),
            "weights": {candidate_id: round(weight, 4) for candidate_id, weight in weights.items()},
            "positive_advantage_present": any_positive_advantage,
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
            filtered = [candidate_id for candidate_id in ranking if candidate_id in candidate_map]
            count = len(filtered)
            return {candidate_id: float(count - index) for index, candidate_id in enumerate(filtered)}
        approved = [candidate_id for candidate_id in normalized.get("approved_candidate_ids", []) if candidate_id in candidate_map]
        rejected = [candidate_id for candidate_id in normalized.get("rejected_candidate_ids", []) if candidate_id in candidate_map]
        if approved or rejected:
            scores: dict[str, float] = {}
            for candidate_id in approved:
                scores[candidate_id] = 1.0
            for candidate_id in rejected:
                if candidate_id not in scores:
                    scores[candidate_id] = 0.0
            return scores
        winner_id = normalized.get("winner_candidate_id")
        loser_id = normalized.get("loser_candidate_id")
        scores: dict[str, float] = {}
        if winner_id and winner_id in candidate_map:
            scores[winner_id] = 1.0
        if loser_id and loser_id in candidate_map:
            scores[loser_id] = 0.0
        return scores

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
