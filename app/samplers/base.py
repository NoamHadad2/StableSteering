from __future__ import annotations

import math
import random
from typing import Protocol

from app.core.schema import Candidate, Session


class Sampler(Protocol):
    """Protocol shared by all candidate samplers."""

    def propose(self, session: Session, seed: int) -> list[Candidate]:
        ...


def clamp_vector(values: list[float], radius: float) -> list[float]:
    """Clip a vector to a maximum L2 radius."""

    length = math.sqrt(sum(v * v for v in values))
    if length == 0 or length <= radius:
        return values
    scale = radius / length
    return [v * scale for v in values]


def make_rng(seed: int) -> random.Random:
    """Return a deterministic RNG for sampler-local use."""

    return random.Random(seed)
