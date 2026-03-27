from __future__ import annotations

import math

from app.core.schema import Candidate, Session
from app.samplers.base import clamp_vector, make_rng


class DiversityShellSampler:
    """Sampler that spreads challengers across a high-radius shell."""

    name = "diversity_shell"

    def propose(self, session: Session, seed: int) -> list[Candidate]:
        """Generate deliberately separated shell probes around the current state."""

        rng = make_rng(seed + 401)
        dimensions = max(1, len(session.current_z))
        shell_radius = min(max(session.config.trust_radius * 0.92, 0.28), session.config.trust_radius)
        candidates: list[Candidate] = []

        for index in range(session.config.candidate_count):
            direction = self._spread_direction(index, dimensions)
            jitter = [rng.uniform(-0.035, 0.035) for _ in range(dimensions)]
            z = clamp_vector(
                [
                    current + (axis * shell_radius) + noise
                    for current, axis, noise in zip(session.current_z, direction, jitter, strict=False)
                ],
                session.config.trust_radius,
            )
            candidates.append(
                Candidate(
                    round_id="",
                    candidate_index=index,
                    z=z,
                    sampler_role="shell_probe" if index % 2 == 0 else "shell_counterprobe",
                    predicted_score=sum(z) - (0.01 * index),
                    predicted_uncertainty=0.18 + (0.03 * index),
                    seed=seed,
                    generation_params={
                        "image_size": session.config.image_size,
                        "shell_radius": round(shell_radius, 4),
                        "spread_direction": [round(value, 4) for value in direction],
                    },
                )
            )
        return candidates

    @staticmethod
    def _spread_direction(index: int, dimensions: int) -> list[float]:
        """Return a deterministic spread direction for one shell position."""

        vector = [0.0 for _ in range(dimensions)]
        primary_axis = index % dimensions
        secondary_axis = (index + 1) % dimensions
        tertiary_axis = (index + 2) % dimensions

        primary_sign = 1.0 if index % 2 == 0 else -1.0
        secondary_sign = -1.0 if index % 4 in {1, 2} else 1.0
        tertiary_sign = -1.0 if index % 3 == 2 else 1.0

        vector[primary_axis] = 1.0 * primary_sign
        if dimensions > 1:
            vector[secondary_axis] += 0.62 * secondary_sign
        if dimensions > 2:
            vector[tertiary_axis] += 0.28 * tertiary_sign
        if dimensions > 3:
            extra_axis = (index + 3) % dimensions
            vector[extra_axis] += 0.18 if index % 2 == 0 else -0.18

        length = math.sqrt(sum(value * value for value in vector))
        if length == 0.0:
            vector[0] = 1.0
            return vector
        return [value / length for value in vector]
