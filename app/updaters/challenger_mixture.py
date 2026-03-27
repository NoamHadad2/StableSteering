from __future__ import annotations

import math

from app.core.schema import Candidate, FeedbackEvent, Session
from app.samplers.base import clamp_vector


class ChallengerMixturePreferenceUpdater:
    """Updater that lets near-miss challengers pull the state even when the incumbent wins."""

    name = "challenger_mixture_preference"

    def update(self, session: Session, candidates: list[Candidate], feedback: FeedbackEvent) -> tuple[list[float], dict]:
        candidate_map = {candidate.id: candidate for candidate in candidates}
        scores = self._scores_from_feedback(feedback, candidate_map)
        winner_id = feedback.normalized_payload["winner_candidate_id"]
        winner_score = float(scores.get(winner_id, 1.0))
        winner_candidate = candidate_map[winner_id]
        incumbent_candidate = next((candidate for candidate in candidates if candidate.generation_params.get("carried_forward")), None)
        incumbent_score = float(scores.get(incumbent_candidate.id, winner_score)) if incumbent_candidate is not None else winner_score

        challenger_scores = {
            candidate_id: float(score)
            for candidate_id, score in scores.items()
            if candidate_id != winner_id and candidate_id in candidate_map
        }
        if not challenger_scores:
            challenger_scores = {candidate_id: 0.0 for candidate_id in candidate_map if candidate_id != winner_id}

        challenger_weights = self._margin_softmax(challenger_scores, incumbent_score)
        challenger_delta = self._weighted_delta(candidate_map, challenger_weights, session.current_z)
        winner_delta = [winner - current for winner, current in zip(winner_candidate.z, session.current_z, strict=False)]
        updated = clamp_vector(
            [
                round(
                    current
                    + (0.42 * winner_component)
                    + (0.36 * challenger_component)
                    + (0.06 * (winner_score - incumbent_score)),
                    6,
                )
                for current, winner_component, challenger_component in zip(
                    session.current_z,
                    winner_delta,
                    challenger_delta,
                    strict=False,
                )
            ],
            session.config.trust_radius,
        )
        return updated, {
            "updater": self.name,
            "winner_candidate_id": winner_id,
            "method": "winner_plus_challenger_margin_mixture",
            "incumbent_score": round(incumbent_score, 4),
            "winner_score": round(winner_score, 4),
            "challenger_weights": {candidate_id: round(weight, 4) for candidate_id, weight in challenger_weights.items()},
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
    def _margin_softmax(scores: dict[str, float], incumbent_score: float) -> dict[str, float]:
        if not scores:
            return {}
        margin_bias = 0.24
        temperature = 0.22
        logits = {
            candidate_id: (score - incumbent_score + margin_bias) / temperature
            for candidate_id, score in scores.items()
        }
        max_logit = max(logits.values())
        exp_values = {candidate_id: math.exp(value - max_logit) for candidate_id, value in logits.items()}
        total = sum(exp_values.values()) or 1.0
        return {candidate_id: value / total for candidate_id, value in exp_values.items()}

    @staticmethod
    def _weighted_delta(
        candidate_map: dict[str, Candidate],
        weights: dict[str, float],
        current_z: list[float],
    ) -> list[float]:
        dimensions = len(current_z)
        if not weights:
            return [0.0 for _ in range(dimensions)]
        delta = [0.0 for _ in range(dimensions)]
        for candidate_id, weight in weights.items():
            candidate = candidate_map[candidate_id]
            for index, value in enumerate(candidate.z):
                delta[index] += weight * (value - current_z[index])
        return delta
