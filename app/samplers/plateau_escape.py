from __future__ import annotations

import math

from app.core.schema import Candidate, Session
from app.samplers.base import clamp_vector, make_rng


class PlateauEscapeSampler:
    """Sampler that keeps proposing wider challenger moves as rounds progress."""

    name = "plateau_escape"

    def propose(self, session: Session, seed: int) -> list[Candidate]:
        """Generate a mix of forward, lateral, and counterfactual challenger directions."""

        rng = make_rng(seed + 907)
        dimensions = max(1, len(session.current_z))
        base_direction = self._base_direction(session.current_z, dimensions)
        lateral_direction = self._lateral_direction(base_direction)
        round_factor = min(max(session.current_round, 0), 8)
        trust_radius = session.config.trust_radius
        escape_radius = min(trust_radius, max(0.34, trust_radius * (0.62 + (0.08 * round_factor))))
        forward_radius = min(trust_radius, max(0.22, trust_radius * (0.38 + (0.04 * round_factor))))
        counter_radius = min(trust_radius * 0.78, max(0.24, trust_radius * (0.44 + (0.03 * round_factor))))

        patterns = [
            ("forward_escape", escape_radius, base_direction),
            ("lateral_plus", escape_radius, lateral_direction),
            ("lateral_minus", escape_radius, [-value for value in lateral_direction]),
            ("counter_probe", counter_radius, [-value for value in base_direction]),
            ("forward_refine", forward_radius, base_direction),
        ]

        candidates: list[Candidate] = []
        for index in range(session.config.candidate_count):
            role, radius, direction = patterns[index % len(patterns)]
            jitter_scale = 0.02 if "refine" in role else 0.028
            jitter = [rng.uniform(-jitter_scale, jitter_scale) for _ in range(dimensions)]
            z = clamp_vector(
                [
                    current + (axis * radius) + noise
                    for current, axis, noise in zip(session.current_z, direction, jitter, strict=False)
                ],
                trust_radius,
            )
            candidates.append(
                Candidate(
                    round_id="",
                    candidate_index=index,
                    z=z,
                    sampler_role=role,
                    predicted_score=sum(z) - (0.015 * index),
                    predicted_uncertainty=0.14 + (0.025 * index),
                    seed=seed,
                    generation_params={
                        "image_size": session.config.image_size,
                        "escape_radius": round(radius, 4),
                        "round_factor": round_factor,
                        "direction": [round(value, 4) for value in direction],
                    },
                )
            )
        return candidates

    @staticmethod
    def _base_direction(current_z: list[float], dimensions: int) -> list[float]:
        length = math.sqrt(sum(value * value for value in current_z))
        if length > 1e-6:
            return [value / length for value in current_z]
        direction = [0.0 for _ in range(dimensions)]
        direction[0] = 1.0
        if dimensions > 1:
            direction[1] = 0.45
        if dimensions > 2:
            direction[2] = -0.2
        norm = math.sqrt(sum(value * value for value in direction))
        return [value / norm for value in direction]

    @staticmethod
    def _lateral_direction(base_direction: list[float]) -> list[float]:
        dimensions = len(base_direction)
        if dimensions == 1:
            return [1.0]
        lateral = [0.0 for _ in range(dimensions)]
        lateral[0] = -base_direction[1]
        lateral[1] = base_direction[0]
        for index in range(2, dimensions):
            lateral[index] = base_direction[index] * (0.55 if index % 2 == 0 else -0.55)
        norm = math.sqrt(sum(value * value for value in lateral))
        if norm == 0.0:
            lateral[1] = 1.0
            return lateral
        return [value / norm for value in lateral]
