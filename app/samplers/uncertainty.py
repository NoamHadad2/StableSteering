from __future__ import annotations

from app.core.schema import Candidate, Session
from app.samplers.base import clamp_vector, make_rng


class UncertaintyGuidedSampler:
    """Sampler that increases search span across the batch for exploration."""

    name = "uncertainty_guided"

    def propose(self, session: Session, seed: int) -> list[Candidate]:
        """Generate candidates that become progressively more exploratory."""

        rng = make_rng(seed + 101)
        candidates = []
        for index in range(session.config.candidate_count):
            span = 0.1 + (0.08 * index)
            offset = [rng.uniform(-span, span) for _ in session.current_z]
            z = clamp_vector(
                [current + delta for current, delta in zip(session.current_z, offset, strict=False)],
                session.config.trust_radius,
            )
            candidates.append(
                Candidate(
                    round_id="",
                    candidate_index=index,
                    z=z,
                    sampler_role="validation" if index == session.config.candidate_count - 1 else "explore",
                    predicted_score=sum(z) - 0.02 * index,
                    predicted_uncertainty=0.15 + (0.06 * index),
                    seed=seed,
                    generation_params={"image_size": session.config.image_size},
                )
            )
        return candidates
