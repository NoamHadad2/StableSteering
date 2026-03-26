from __future__ import annotations

from app.core.schema import Candidate, Session
from app.samplers.base import clamp_vector, make_rng


class IncumbentMixSampler:
    """Sampler that mixes conservative refinements with broader challenger proposals."""

    name = "incumbent_mix"

    def propose(self, session: Session, seed: int) -> list[Candidate]:
        """Generate a batch with near-incumbent refinements and one broader challenger."""

        rng = make_rng(seed + 307)
        base = session.current_z
        candidates: list[Candidate] = []
        for index in range(session.config.candidate_count):
            if index == 0:
                span = 0.08
                role = "refine"
            elif index == session.config.candidate_count - 1:
                span = 0.28
                role = "challenger"
            else:
                span = 0.14 + (0.03 * index)
                role = "mix"
            offset = [rng.uniform(-span, span) for _ in base]
            z = clamp_vector(
                [current + delta for current, delta in zip(base, offset, strict=False)],
                session.config.trust_radius,
            )
            candidates.append(
                Candidate(
                    round_id="",
                    candidate_index=index,
                    z=z,
                    sampler_role=role,
                    predicted_score=sum(z) + (0.03 if role == "refine" else 0.0),
                    predicted_uncertainty=0.08 if role == "refine" else 0.16 + (0.02 * index),
                    seed=seed,
                    generation_params={"image_size": session.config.image_size, "mix_span": span},
                )
            )
        return candidates
