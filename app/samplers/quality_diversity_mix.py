from __future__ import annotations

import math

from app.core.schema import Candidate, Session
from app.samplers.base import clamp_vector, make_rng


class QualityDiversityMixSampler:
    """Sampler inspired by quality-diversity search with several complementary emitters."""

    name = "quality_diversity_mix"

    def propose(self, session: Session, seed: int) -> list[Candidate]:
        rng = make_rng(seed + 991)
        dimensions = max(1, len(session.current_z))
        base_direction = self._base_direction(session.current_z, dimensions)
        lateral_direction = self._orthogonal_direction(base_direction)
        cover_pool = [self._unit_vector([rng.uniform(-1.0, 1.0) for _ in range(dimensions)]) for _ in range(28)]
        far_directions = self._greedy_cover(cover_pool, max(2, session.config.candidate_count // 2))

        medium = min(max(session.config.trust_radius * 0.42, 0.16), session.config.trust_radius)
        far = min(max(session.config.trust_radius * 0.82, 0.28), session.config.trust_radius)
        counter = min(max(session.config.trust_radius * 0.3, 0.12), session.config.trust_radius)

        patterns: list[tuple[str, list[float], float]] = [
            ("qd_refine", base_direction, medium * 0.62),
            ("qd_forward", base_direction, medium),
            ("qd_lateral_plus", lateral_direction, medium),
            ("qd_far_cover_1", far_directions[0], far),
            ("qd_lateral_minus", [-value for value in lateral_direction], medium),
            ("qd_counter", [-value for value in base_direction], counter),
        ]
        for index, direction in enumerate(far_directions[1:], start=2):
            patterns.append((f"qd_far_cover_{index + 1}", direction, far))

        candidates: list[Candidate] = []
        for index in range(session.config.candidate_count):
            role, direction, radius = patterns[index % len(patterns)]
            jitter_scale = 0.014 if "refine" in role else 0.024 if "far_cover" not in role else 0.03
            jitter = [rng.uniform(-jitter_scale, jitter_scale) for _ in range(dimensions)]
            z = clamp_vector(
                [
                    current + (axis * radius) + noise
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
                    predicted_score=sum(z) + (0.01 if "far_cover" in role else 0.0),
                    predicted_uncertainty=0.16 + (0.02 * index),
                    seed=seed,
                    generation_params={
                        "image_size": session.config.image_size,
                        "qd_radius": round(radius, 4),
                        "qd_direction": [round(value, 4) for value in direction],
                        "qd_emitter_role": role,
                    },
                )
            )
        return candidates

    @staticmethod
    def _base_direction(current_z: list[float], dimensions: int) -> list[float]:
        length = math.sqrt(sum(value * value for value in current_z))
        if length > 1e-8:
            return [value / length for value in current_z]
        direction = [0.0 for _ in range(dimensions)]
        direction[0] = 1.0
        if dimensions > 1:
            direction[1] = 0.35
        norm = math.sqrt(sum(value * value for value in direction))
        return [value / norm for value in direction]

    @staticmethod
    def _orthogonal_direction(base_direction: list[float]) -> list[float]:
        dimensions = len(base_direction)
        if dimensions == 1:
            return [1.0]
        lateral = [0.0 for _ in range(dimensions)]
        lateral[0] = -base_direction[1]
        lateral[1] = base_direction[0]
        for index in range(2, dimensions):
            lateral[index] = base_direction[index] * (-0.45 if index % 2 == 0 else 0.45)
        length = math.sqrt(sum(value * value for value in lateral))
        if length == 0.0:
            lateral[1] = 1.0
            return lateral
        return [value / length for value in lateral]

    @classmethod
    def _greedy_cover(cls, pool: list[list[float]], count: int) -> list[list[float]]:
        if not pool:
            return []
        selected = [pool[0]]
        remaining = pool[1:]
        while remaining and len(selected) < count:
            best_direction = max(
                remaining,
                key=lambda candidate: min(cls._angular_distance(candidate, prior) for prior in selected),
            )
            selected.append(best_direction)
            remaining = [candidate for candidate in remaining if candidate is not best_direction]
        return selected[:count]

    @staticmethod
    def _angular_distance(left: list[float], right: list[float]) -> float:
        cosine = sum(a * b for a, b in zip(left, right, strict=False))
        cosine = max(-1.0, min(1.0, cosine))
        return math.acos(cosine)

    @staticmethod
    def _unit_vector(values: list[float]) -> list[float]:
        norm = math.sqrt(sum(value * value for value in values))
        if norm == 0.0:
            fallback = [0.0 for _ in values]
            fallback[0] = 1.0
            return fallback
        return [value / norm for value in values]
