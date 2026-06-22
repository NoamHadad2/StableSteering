from __future__ import annotations

import math

from app.core.schema import Candidate, Session
from app.samplers.base import clamp_vector, make_rng


class TwoScaleCoverSampler:
    """Sampler that mixes short- and long-radius probes over separated directions."""

    name = "two_scale_cover"

    def propose(self, session: Session, seed: int) -> list[Candidate]:
        """Generate nearby and farther challengers so the round can both refine and escape."""

        rng = make_rng(seed + 883)
        dimensions = max(1, len(session.current_z))
        short_radius = min(max(session.config.trust_radius * 0.34, 0.12), session.config.trust_radius)
        long_radius = min(max(session.config.trust_radius * 0.78, 0.26), session.config.trust_radius)
        pool = [self._unit_vector([rng.uniform(-1.0, 1.0) for _ in range(dimensions)]) for _ in range(40)]
        selected = self._greedy_cover(pool, session.config.candidate_count)
        candidates: list[Candidate] = []

        for index, direction in enumerate(selected):
            use_short = index % 2 == 0
            radius = short_radius if use_short else long_radius
            role = "near_cover_probe" if use_short else "far_cover_probe"
            jitter = [rng.uniform(-0.016, 0.016) if use_short else rng.uniform(-0.028, 0.028) for _ in range(dimensions)]
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
                    predicted_score=sum(z) - (0.004 * index),
                    predicted_uncertainty=0.14 + (0.028 * index),
                    seed=seed,
                    generation_params={
                        "image_size": session.config.image_size,
                        "short_radius": round(short_radius, 4),
                        "long_radius": round(long_radius, 4),
                        "probe_radius": round(radius, 4),
                        "cover_direction": [round(value, 4) for value in direction],
                    },
                )
            )
        return candidates

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
