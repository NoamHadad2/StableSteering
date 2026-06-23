from __future__ import annotations

from app.core.schema import Candidate, FeedbackEvent, Session
from app.samplers.base import clamp_vector


# Structured reason tags grouped by valence. Positive tags pull the steering
# vector toward a candidate; negative tags push it away. Tags outside these sets
# are treated as neutral (weight contribution of zero).
POSITIVE_TAGS = frozenset(
    {
        "good_composition",
        "good_color",
        "good_detail",
    }
)
NEGATIVE_TAGS = frozenset(
    {
        "too_dark",
        "too_bright",
        "wrong_style",
        "wrong_composition",
        "too_busy",
        "too_simple",
        "wrong_subject",
    }
)

# Ordered list of all selectable tags, used to render the critique UI. Positive
# tags first, then negative, so the frontend can group them by valence.
CRITIQUE_TAGS: tuple[str, ...] = (
    "good_composition",
    "good_color",
    "good_detail",
    "too_dark",
    "too_bright",
    "wrong_style",
    "wrong_composition",
    "too_busy",
    "too_simple",
    "wrong_subject",
)


class CritiqueWeightedPreferenceUpdater:
    """Updater that turns structured critique tags into a weighted steering move.

    Each candidate earns a weight from its critique tags: positive tags raise the
    weight (a direction to move toward), negative tags lower it (a direction to
    move away from). The steering vector then moves along the difference between
    the positively-weighted centroid and the negatively-weighted centroid.

    When no critique tags are present, this falls back to moving toward the rated
    winner, so the updater is safe to pair with any feedback mode.
    """

    name = "critique_weighted_preference"

    def update(self, session: Session, candidates: list[Candidate], feedback: FeedbackEvent) -> tuple[list[float], dict]:
        """Move the steering vector using per-candidate critique weights."""

        dimensions = len(session.current_z)
        candidate_map = {candidate.id: candidate for candidate in candidates}
        critique_tags = feedback.normalized_payload.get("critique_tags", {})

        positive_terms: list[tuple[float, Candidate]] = []
        negative_terms: list[tuple[float, Candidate]] = []
        positive_tag_count = 0
        negative_tag_count = 0
        for candidate_id, tags in critique_tags.items():
            candidate = candidate_map.get(candidate_id)
            if candidate is None:
                continue
            positives = sum(1 for tag in tags if tag in POSITIVE_TAGS)
            negatives = sum(1 for tag in tags if tag in NEGATIVE_TAGS)
            positive_tag_count += positives
            negative_tag_count += negatives
            weight = positives - negatives
            if weight > 0:
                positive_terms.append((float(weight), candidate))
            elif weight < 0:
                negative_terms.append((float(-weight), candidate))

        # Fall back to the rated winner so the move is never a no-op when tags
        # are absent (or all-neutral) — keeps this updater usable everywhere.
        if not positive_terms:
            winner_id = feedback.normalized_payload["winner_candidate_id"]
            winner = candidate_map.get(winner_id)
            if winner is not None:
                positive_terms.append((1.0, winner))

        positive_center = self._weighted_centroid(positive_terms, dimensions)
        negative_center = self._weighted_centroid(negative_terms, dimensions)
        direction = [pos - neg for pos, neg in zip(positive_center, negative_center, strict=False)]

        # A stronger step when explicit positive and negative evidence disagree,
        # a gentler step when only one side is present.
        alpha = 0.55 if negative_terms and positive_tag_count else 0.4
        updated = clamp_vector(
            [
                round(current + (alpha * delta), 6)
                for current, delta in zip(session.current_z, direction, strict=False)
            ],
            session.config.trust_radius,
        )
        return updated, {
            "updater": self.name,
            "winner_candidate_id": feedback.normalized_payload["winner_candidate_id"],
            "method": "critique_weighted_move",
            "positive_tag_count": positive_tag_count,
            "negative_tag_count": negative_tag_count,
        }

    @staticmethod
    def _weighted_centroid(terms: list[tuple[float, Candidate]], dimensions: int) -> list[float]:
        if not terms:
            return [0.0 for _ in range(dimensions)]
        total_weight = sum(weight for weight, _ in terms)
        if total_weight <= 0:
            return [0.0 for _ in range(dimensions)]
        values = [0.0 for _ in range(dimensions)]
        for weight, candidate in terms:
            for index, value in enumerate(candidate.z):
                if index < dimensions:
                    values[index] += weight * value
        return [value / total_weight for value in values]
