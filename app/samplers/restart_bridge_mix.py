from __future__ import annotations

import math

from app.core.schema import Candidate, Session
from app.samplers.base import clamp_vector, make_rng


class RestartBridgeMixSampler:
    """Sampler that mixes incumbent refinement with partial restarts toward fresh regions."""

    name = "restart_bridge_mix"

    def propose(self, session: Session, seed: int) -> list[Candidate]:
        rng = make_rng(seed + 1223)
        dimensions = max(1, len(session.current_z))
        trust_radius = session.config.trust_radius
        base_direction = self._base_direction(session.current_z, dimensions)
        lateral_direction = self._orthogonal_direction(base_direction)
        far_pool = [self._unit_vector([rng.uniform(-1.0, 1.0) for _ in range(dimensions)]) for _ in range(24)]
        far_cover = self._greedy_cover(far_pool, max(2, session.config.candidate_count // 2))

        refine_radius = min(max(trust_radius * 0.28, 0.12), trust_radius)
        bridge_radius = min(max(trust_radius * 0.56, 0.22), trust_radius)
        restart_radius = min(max(trust_radius * 0.82, 0.3), trust_radius)

        patterns: list[tuple[str, list[float], float, float]] = [
            ("bridge_refine", base_direction, refine_radius, 1.0),
            ("bridge_forward", base_direction, bridge_radius, 1.0),
            ("partial_restart", far_cover[0], restart_radius, 0.38),
            ("lateral_restart", lateral_direction, restart_radius, 0.46),
            ("counter_reset", [-value for value in base_direction], bridge_radius, 0.18),
        ]
        for index, direction in enumerate(far_cover[1:], start=2):
            patterns.append((f"restart_cover_{index + 1}", direction, restart_radius, 0.32))

        candidates: list[Candidate] = []
        for index in range(session.config.candidate_count):
            role, direction, radius, retain_fraction = patterns[index % len(patterns)]
            jitter_scale = 0.012 if "refine" in role else 0.022 if "bridge" in role else 0.03
            jitter = [rng.uniform(-jitter_scale, jitter_scale) for _ in range(dimensions)]
            z = clamp_vector(
                [
                    (current * retain_fraction) + (axis * radius) + noise
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
                    predicted_score=sum(z) + (0.012 if "restart" in role else 0.0),
                    predicted_uncertainty=0.18 + (0.024 * index),
                    seed=seed,
                    generation_params={
                        "image_size": session.config.image_size,
                        "bridge_radius": round(radius, 4),
                        "retain_fraction": round(retain_fraction, 4),
                        "bridge_direction": [round(value, 4) for value in direction],
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
            direction[1] = 0.3
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
            lateral[index] = base_direction[index] * (0.4 if index % 2 == 0 else -0.4)
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
