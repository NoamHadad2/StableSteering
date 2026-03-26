from __future__ import annotations

from app.core.schema import Candidate, Session
from app.samplers.base import clamp_vector, make_rng


class RandomLocalSampler:
    """Baseline sampler that explores uniformly around the current state."""

    name = "random_local"

    def propose(self, session: Session, seed: int) -> list[Candidate]:
        """Create one batch of local candidates inside the trust radius."""

        rng = make_rng(seed)
        candidates = []
        for index in range(session.config.candidate_count):
            offset = [rng.uniform(-0.35, 0.35) for _ in session.current_z]
            z = clamp_vector(
                [current + delta for current, delta in zip(session.current_z, offset, strict=False)],
                session.config.trust_radius,
            )
            candidates.append(
                Candidate(
                    round_id="",
                    candidate_index=index,
                    z=z,
                    sampler_role="explore" if index else "exploit",
                    predicted_score=sum(z),
                    predicted_uncertainty=max(0.05, 0.3 - (0.03 * index)),
                    seed=seed,
                    generation_params={"image_size": session.config.image_size},
                )
            )
        return candidates
