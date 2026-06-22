from __future__ import annotations

import math

from app.core.schema import Candidate, Session
from app.samplers.base import clamp_vector, make_rng


class AnnealedShellSampler:
    """Sampler that shrinks from broad shell exploration toward local refinement over rounds."""

    name = "annealed_shell"

    def propose(self, session: Session, seed: int) -> list[Candidate]:
        """Generate shell probes whose radius anneals with session progress."""

        rng = make_rng(seed + 613)
        dimensions = max(1, len(session.current_z))
        progress = min(max(session.current_round, 0), 8) / 8.0
        shell_fraction = 0.95 - (0.42 * progress)
        shell_radius = min(max(session.config.trust_radius * shell_fraction, 0.2), session.config.trust_radius)
        jitter_scale = 0.04 - (0.018 * progress)
        candidates: list[Candidate] = []

        for index in range(session.config.candidate_count):
            direction = self._spread_direction(index, dimensions)
            jitter = [rng.uniform(-jitter_scale, jitter_scale) for _ in range(dimensions)]
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
                    sampler_role="annealed_probe" if index % 2 == 0 else "annealed_counterprobe",
                    predicted_score=sum(z) - (0.008 * index),
                    predicted_uncertainty=max(0.05, 0.2 - (0.08 * progress) + (0.01 * index)),
                    seed=seed,
                    generation_params={
                        "image_size": session.config.image_size,
                        "annealed_progress": round(progress, 4),
                        "shell_radius": round(shell_radius, 4),
                        "jitter_scale": round(jitter_scale, 4),
                        "spread_direction": [round(value, 4) for value in direction],
                    },
                )
            )
        return candidates

    @staticmethod
    def _spread_direction(index: int, dimensions: int) -> list[float]:
        vector = [0.0 for _ in range(dimensions)]
        primary_axis = index % dimensions
        secondary_axis = (index + 1) % dimensions
        tertiary_axis = (index + 2) % dimensions

        vector[primary_axis] = 1.0 if index % 2 == 0 else -1.0
        if dimensions > 1:
            vector[secondary_axis] += 0.58 if index % 3 != 1 else -0.58
        if dimensions > 2:
            vector[tertiary_axis] += 0.26 if index % 4 < 2 else -0.26
        if dimensions > 3:
            vector[(index + 3) % dimensions] += 0.15 if index % 2 == 0 else -0.15

        norm = math.sqrt(sum(value * value for value in vector))
        if norm == 0.0:
            vector[0] = 1.0
            return vector
        return [value / norm for value in vector]
