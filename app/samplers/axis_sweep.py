from __future__ import annotations

from app.core.schema import Candidate, Session
from app.samplers.base import clamp_vector, make_rng


class AxisSweepSampler:
    """Sampler that probes positive and negative movement along steering axes."""

    name = "axis_sweep"

    def propose(self, session: Session, seed: int) -> list[Candidate]:
        """Generate a batch that systematically sweeps the steering basis directions."""

        rng = make_rng(seed + 211)
        base = session.current_z
        dimensions = max(1, len(base))
        candidates: list[Candidate] = []
        for index in range(session.config.candidate_count):
            axis = index % dimensions
            direction = 1.0 if (index // dimensions) % 2 == 0 else -1.0
            magnitude = 0.18 + (0.04 * (index // (dimensions * 2)))
            offset = [0.0 for _ in base]
            offset[axis] = direction * magnitude
            jitter = [rng.uniform(-0.025, 0.025) for _ in base]
            z = clamp_vector(
                [current + delta + noise for current, delta, noise in zip(base, offset, jitter, strict=False)],
                session.config.trust_radius,
            )
            role = "axis_positive" if direction > 0 else "axis_negative"
            candidates.append(
                Candidate(
                    round_id="",
                    candidate_index=index,
                    z=z,
                    sampler_role=role,
                    predicted_score=sum(z),
                    predicted_uncertainty=0.1 + (0.02 * index),
                    seed=seed,
                    generation_params={"image_size": session.config.image_size, "axis_index": axis},
                )
            )
        return candidates
