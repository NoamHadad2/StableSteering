from __future__ import annotations

import math

from app.core.schema import Candidate, Session
from app.samplers.base import clamp_vector, make_rng


class LineSearchSampler:
    """Sampler that probes forward, backward, and lateral moves around the incumbent direction."""

    name = "line_search"

    def propose(self, session: Session, seed: int) -> list[Candidate]:
        """Generate candidates along the incumbent direction and nearby lateral alternatives."""

        rng = make_rng(seed + 509)
        dimensions = max(1, len(session.current_z))
        base_direction = self._incumbent_direction(session.current_z, dimensions)
        lateral_direction = self._lateral_direction(base_direction)
        candidates: list[Candidate] = []

        for index in range(session.config.candidate_count):
            scale, role = self._pattern(index)
            if role == "lateral_probe":
                direction = lateral_direction
            elif role == "counter_lateral":
                direction = [-value for value in lateral_direction]
            else:
                direction = base_direction
            jitter = [rng.uniform(-0.025, 0.025) for _ in range(dimensions)]
            z = clamp_vector(
                [
                    current + (axis * scale) + noise
                    for current, axis, noise in zip(session.current_z, direction, jitter, strict=False)
                ],
                session.config.trust_radius,
            )
            candidates.append(
                Candidate(
                    round_id="",
                    candidate_index=index,
                    z=z,
                    sampler_role=role,
                    predicted_score=sum(z),
                    predicted_uncertainty=0.1 + (0.025 * index),
                    seed=seed,
                    generation_params={
                        "image_size": session.config.image_size,
                        "line_scale": round(scale, 4),
                    },
                )
            )
        return candidates

    @staticmethod
    def _pattern(index: int) -> tuple[float, str]:
        patterns = [
            (0.16, "forward_probe"),
            (0.3, "far_forward"),
            (-0.14, "backtrack"),
            (0.22, "lateral_probe"),
            (0.22, "counter_lateral"),
        ]
        return patterns[index % len(patterns)]

    @staticmethod
    def _incumbent_direction(current_z: list[float], dimensions: int) -> list[float]:
        length = math.sqrt(sum(value * value for value in current_z))
        if length > 1e-6:
            return [value / length for value in current_z]
        direction = [0.0 for _ in range(dimensions)]
        direction[0] = 1.0
        if dimensions > 1:
            direction[1] = 0.35
        norm = math.sqrt(sum(value * value for value in direction))
        return [value / norm for value in direction]

    @staticmethod
    def _lateral_direction(base_direction: list[float]) -> list[float]:
        dimensions = len(base_direction)
        lateral = [0.0 for _ in range(dimensions)]
        if dimensions == 1:
            return [1.0]
        lateral[0] = -base_direction[1]
        lateral[1] = base_direction[0]
        for index in range(2, dimensions):
            lateral[index] = base_direction[index] * (-0.4 if index % 2 == 0 else 0.4)
        length = math.sqrt(sum(value * value for value in lateral))
        if length == 0.0:
            lateral[1] = 1.0
            return lateral
        return [value / length for value in lateral]
