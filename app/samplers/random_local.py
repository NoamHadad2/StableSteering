from __future__ import annotations

import math

from app.core.schema import Candidate, Session
from app.samplers.base import clamp_vector, make_rng


class RandomLocalSampler:
    """Baseline sampler that explores uniformly around the current state."""

    name = "random_local"

    def propose(self, session: Session, seed: int) -> list[Candidate]:
        """Create one batch of local candidates inside the trust radius."""

        rng = make_rng(seed)
        candidates = []
        dimensions = max(1, len(session.current_z))
        exploit_radius = min(session.config.trust_radius * 0.28, 0.18)
        explore_radius = min(max(session.config.trust_radius * 0.9, 0.28), session.config.trust_radius)
        for index in range(session.config.candidate_count):
            if index == 0:
                role = "exploit"
                offset = [rng.uniform(-0.12, 0.12) for _ in session.current_z]
                z = clamp_vector(
                    [current + delta for current, delta in zip(session.current_z, offset, strict=False)],
                    exploit_radius,
                )
            else:
                role = "explore"
                direction = self._explore_direction(index - 1, dimensions)
                jitter = [rng.uniform(-0.08, 0.08) for _ in session.current_z]
                target_radius = min(explore_radius, max(explore_radius * (0.82 + (0.06 * ((index - 1) % 3))), 0.24))
                z = clamp_vector(
                    [
                        current + (axis * target_radius) + noise
                        for current, axis, noise in zip(session.current_z, direction, jitter, strict=False)
                    ],
                    session.config.trust_radius,
                )
                length = math.sqrt(sum(value * value for value in z))
                minimum_radius = min(max(session.config.trust_radius * 0.58, 0.22), session.config.trust_radius)
                if 0.0 < length < minimum_radius:
                    z = clamp_vector([value * (minimum_radius / length) for value in z], session.config.trust_radius)

            candidates.append(
                Candidate(
                    round_id="",
                    candidate_index=index,
                    z=z,
                    sampler_role=role,
                    predicted_score=sum(z),
                    predicted_uncertainty=max(0.05, 0.3 - (0.03 * index)),
                    seed=seed,
                    generation_params={
                        "image_size": session.config.image_size,
                        "proposal_role_radius": exploit_radius if role == "exploit" else explore_radius,
                    },
                )
            )
        return candidates

    @staticmethod
    def _explore_direction(index: int, dimensions: int) -> list[float]:
        """Return a separated exploratory direction for one candidate slot."""

        vector = [0.0 for _ in range(dimensions)]
        primary_axis = index % dimensions
        secondary_axis = (index + 1) % dimensions
        tertiary_axis = (index + 2) % dimensions
        primary_sign = 1.0 if index % 2 == 0 else -1.0
        secondary_sign = -1.0 if index % 3 == 1 else 1.0
        tertiary_sign = -1.0 if index % 4 >= 2 else 1.0

        vector[primary_axis] = 1.0 * primary_sign
        if dimensions > 1:
            vector[secondary_axis] += 0.45 * secondary_sign
        if dimensions > 2:
            vector[tertiary_axis] += 0.22 * tertiary_sign
        if dimensions > 3:
            extra_axis = (index + 3) % dimensions
            vector[extra_axis] += 0.16 if index % 2 == 0 else -0.16

        length = math.sqrt(sum(value * value for value in vector))
        if length == 0.0:
            vector[0] = 1.0
            return vector
        return [value / length for value in vector]
