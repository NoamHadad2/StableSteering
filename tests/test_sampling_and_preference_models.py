from __future__ import annotations

import math
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from app.core.schema import Candidate, FeedbackRequest, FeedbackType, Session, StrategyConfig
from app.feedback.normalization import normalize_feedback
from app.samplers.annealed_shell import AnnealedShellSampler
from app.samplers.diversity_shell import DiversityShellSampler
from app.samplers.line_search import LineSearchSampler
from app.samplers.plateau_escape import PlateauEscapeSampler
from app.samplers.quality_diversity_mix import QualityDiversityMixSampler
from app.samplers.spherical_cover import SphericalCoverSampler
from app.samplers.two_scale_cover import TwoScaleCoverSampler
from app.updaters.borda_pref import BordaPreferenceUpdater
from app.updaters.bradley_terry_pref import BradleyTerryPreferenceUpdater
from app.updaters.challenger_mixture import ChallengerMixturePreferenceUpdater
from app.updaters.contrastive_pref import ContrastivePreferenceUpdater
from app.updaters.plackett_luce_pref import PlackettLucePreferenceUpdater
from app.updaters.score_weighted import ScoreWeightedPreferenceUpdater
from app.updaters.softmax_pref import SoftmaxPreferenceUpdater
from run_paper_method_extension_comparison import _apply_oracle_policy
from run_paper_oracle_progress_diagnosis import PolicySpec, _oracle_score_candidates
from run_paper_oracle_multimetric_repeated import _eligible_oracle_candidates, _oracle_feedback_request


def _session(*, trust_radius: float = 0.6, candidate_count: int = 5, current_z: list[float] | None = None) -> Session:
    config = StrategyConfig(
        candidate_count=candidate_count,
        trust_radius=trust_radius,
        steering_dimension=len(current_z or [0.0, 0.0, 0.0]),
    )
    return Session(
        experiment_id="exp_test",
        prompt="test prompt",
        model_name=config.model_name,
        config=config,
        current_z=list(current_z or [0.0, 0.0, 0.0]),
    )


def _candidate(candidate_id: str, z: list[float]) -> Candidate:
    return Candidate(
        id=candidate_id,
        round_id="rnd_test",
        candidate_index=0,
        z=z,
        sampler_role="test",
        seed=1,
        generation_params={},
    )


def test_diversity_shell_sampler_spreads_candidates_on_outer_shell() -> None:
    session = _session(trust_radius=0.6, candidate_count=5, current_z=[0.0, 0.0, 0.0, 0.0, 0.0])
    sampler = DiversityShellSampler()

    candidates = sampler.propose(session, seed=7)
    distances = [math.sqrt(sum(value * value for value in candidate.z)) for candidate in candidates]

    assert len(candidates) == 5
    assert all(distance > 0.35 for distance in distances)
    for left_index in range(len(candidates)):
        for right_index in range(left_index + 1, len(candidates)):
            pair_distance = math.sqrt(
                sum(
                    (left - right) ** 2
                    for left, right in zip(candidates[left_index].z, candidates[right_index].z, strict=False)
                )
            )
            assert pair_distance > 0.22


def test_line_search_sampler_has_forward_backward_and_lateral_roles() -> None:
    session = _session(trust_radius=0.6, candidate_count=5, current_z=[0.24, 0.08, 0.0, 0.0, 0.0])
    sampler = LineSearchSampler()

    candidates = sampler.propose(session, seed=11)
    roles = {candidate.sampler_role for candidate in candidates}

    assert {"forward_probe", "far_forward", "backtrack", "lateral_probe", "counter_lateral"} <= roles
    forward = next(candidate for candidate in candidates if candidate.sampler_role == "forward_probe")
    backtrack = next(candidate for candidate in candidates if candidate.sampler_role == "backtrack")
    assert forward.z[0] > session.current_z[0]
    assert backtrack.z[0] < session.current_z[0]


def test_plateau_escape_sampler_keeps_wide_challengers_as_rounds_progress() -> None:
    session = _session(trust_radius=0.75, candidate_count=5, current_z=[0.28, 0.09, 0.0, 0.0, 0.0])
    session.current_round = 6
    sampler = PlateauEscapeSampler()

    candidates = sampler.propose(session, seed=19)
    roles = [candidate.sampler_role for candidate in candidates]
    distances = [
        math.sqrt(sum((value - current) ** 2 for value, current in zip(candidate.z, session.current_z, strict=False)))
        for candidate in candidates
    ]

    assert roles[:4] == ["forward_escape", "lateral_plus", "lateral_minus", "counter_probe"]
    assert max(distances) > 0.42
    assert sum(1 for distance in distances if distance > 0.3) >= 3


def test_annealed_shell_sampler_shrinks_radius_over_rounds() -> None:
    early = _session(trust_radius=0.7, candidate_count=5, current_z=[0.15, 0.05, 0.0, 0.0, 0.0])
    late = _session(trust_radius=0.7, candidate_count=5, current_z=[0.15, 0.05, 0.0, 0.0, 0.0])
    early.current_round = 0
    late.current_round = 8
    sampler = AnnealedShellSampler()

    early_candidates = sampler.propose(early, seed=23)
    late_candidates = sampler.propose(late, seed=23)
    early_distance = _mean_distance(early_candidates, early.current_z)
    late_distance = _mean_distance(late_candidates, late.current_z)

    assert early_distance > late_distance
    assert early_candidates[0].generation_params["annealed_progress"] == 0.0
    assert late_candidates[0].generation_params["annealed_progress"] == 1.0


def test_spherical_cover_sampler_generates_angularly_separated_probes() -> None:
    session = _session(trust_radius=0.65, candidate_count=5, current_z=[0.0, 0.0, 0.0, 0.0, 0.0])
    sampler = SphericalCoverSampler()

    candidates = sampler.propose(session, seed=31)
    directions = [_unit_from(candidate.z) for candidate in candidates]
    min_dot = 1.0
    for left_index in range(len(directions)):
        for right_index in range(left_index + 1, len(directions)):
            dot = sum(left * right for left, right in zip(directions[left_index], directions[right_index], strict=False))
            min_dot = min(min_dot, dot)

    assert len(candidates) == 5
    assert all(candidate.sampler_role == "cover_probe" for candidate in candidates)
    assert min_dot < 0.35


def test_two_scale_cover_sampler_mixes_near_and_far_radii() -> None:
    session = _session(trust_radius=0.7, candidate_count=5, current_z=[0.12, 0.04, 0.0, 0.0, 0.0])
    sampler = TwoScaleCoverSampler()

    candidates = sampler.propose(session, seed=41)
    deltas = [
        math.sqrt(sum((value - current) ** 2 for value, current in zip(candidate.z, session.current_z, strict=False)))
        for candidate in candidates
    ]
    near = [distance for candidate, distance in zip(candidates, deltas, strict=True) if candidate.sampler_role == "near_cover_probe"]
    far = [distance for candidate, distance in zip(candidates, deltas, strict=True) if candidate.sampler_role == "far_cover_probe"]

    assert near and far
    assert max(near) < min(far)
    assert len(candidates) == 5


def test_quality_diversity_mix_sampler_covers_multiple_emitter_roles() -> None:
    session = _session(trust_radius=0.7, candidate_count=5, current_z=[0.16, 0.03, 0.0, 0.0, 0.0])
    sampler = QualityDiversityMixSampler()

    candidates = sampler.propose(session, seed=43)
    roles = {candidate.sampler_role for candidate in candidates}
    distances = [
        math.sqrt(sum((value - current) ** 2 for value, current in zip(candidate.z, session.current_z, strict=False)))
        for candidate in candidates
    ]

    assert "qd_refine" in roles
    assert "qd_forward" in roles
    assert any(role.startswith("qd_far_cover") for role in roles)
    assert max(distances) - min(distances) > 0.15


def test_score_weighted_preference_uses_ratings_to_form_weighted_centroid() -> None:
    session = _session(trust_radius=0.7, current_z=[0.0, 0.0])
    candidates = [
        _candidate("c1", [0.6, 0.0]),
        _candidate("c2", [0.0, 0.6]),
        _candidate("c3", [-0.5, 0.0]),
    ]
    feedback = normalize_feedback(
        "rnd_test",
        FeedbackRequest(
            feedback_type=FeedbackType.scalar_rating,
            payload={"ratings": {"c1": 5, "c2": 3, "c3": 1}},
        ),
    )

    updated, summary = ScoreWeightedPreferenceUpdater().update(session, candidates, feedback)

    assert summary["updater"] == "score_weighted_preference"
    assert summary["weight_count"] == 3
    assert updated[0] > 0.0
    assert updated[1] > 0.0
    assert updated[0] > updated[1]


def test_score_weighted_preference_uses_approved_centroid() -> None:
    session = _session(trust_radius=0.7, current_z=[0.0, 0.0])
    candidates = [
        _candidate("c1", [0.5, 0.1]),
        _candidate("c2", [0.1, 0.5]),
        _candidate("c3", [-0.4, -0.1]),
    ]
    feedback = normalize_feedback(
        "rnd_test",
        FeedbackRequest(
            feedback_type=FeedbackType.approve_reject,
            payload={"winner_candidate_id": "c1", "approvals": {"c1": True, "c2": True, "c3": False}},
        ),
    )

    updated, _ = ScoreWeightedPreferenceUpdater().update(session, candidates, feedback)

    assert updated[0] > 0.0
    assert updated[1] > 0.0


def test_contrastive_preference_moves_toward_winner_and_away_from_loser() -> None:
    session = _session(trust_radius=0.7, current_z=[0.0, 0.0])
    candidates = [
        _candidate("winner", [0.55, 0.1]),
        _candidate("loser", [-0.45, -0.1]),
    ]
    feedback = normalize_feedback(
        "rnd_test",
        FeedbackRequest(
            feedback_type=FeedbackType.pairwise,
            payload={"winner_candidate_id": "winner", "loser_candidate_id": "loser"},
        ),
    )

    updated, summary = ContrastivePreferenceUpdater().update(session, candidates, feedback)

    assert summary["updater"] == "contrastive_preference"
    assert summary["positive_count"] == 1
    assert summary["negative_count"] == 1
    assert updated[0] > 0.0
    assert math.sqrt(sum(value * value for value in updated)) <= session.config.trust_radius + 1e-6


def test_contrastive_preference_uses_top_k_split() -> None:
    session = _session(trust_radius=0.8, current_z=[0.0, 0.0])
    candidates = [
        _candidate("c1", [0.6, 0.0]),
        _candidate("c2", [0.2, 0.5]),
        _candidate("c3", [-0.4, 0.1]),
        _candidate("c4", [-0.5, -0.2]),
    ]
    feedback = normalize_feedback(
        "rnd_test",
        FeedbackRequest(
            feedback_type=FeedbackType.top_k,
            payload={"ranking": ["c2", "c1", "c3", "c4"]},
        ),
    )

    updated, summary = ContrastivePreferenceUpdater().update(session, candidates, feedback)

    assert summary["positive_count"] == 2
    assert summary["negative_count"] == 2
    assert updated[0] > 0.0
    assert updated[1] > 0.0


def test_softmax_preference_uses_all_ratings_and_moves_away_from_low_scores() -> None:
    session = _session(trust_radius=0.8, current_z=[0.0, 0.0])
    candidates = [
        _candidate("c1", [0.65, 0.0]),
        _candidate("c2", [0.2, 0.55]),
        _candidate("c3", [-0.55, -0.2]),
    ]
    feedback = normalize_feedback(
        "rnd_test",
        FeedbackRequest(
            feedback_type=FeedbackType.scalar_rating,
            payload={"ratings": {"c1": 5.0, "c2": 4.0, "c3": 1.0}},
        ),
    )

    updated, summary = SoftmaxPreferenceUpdater().update(session, candidates, feedback)

    assert summary["updater"] == "softmax_preference"
    assert summary["weight_count"] == 3
    assert updated[0] > 0.0
    assert updated[1] > 0.0
    assert math.sqrt(sum(value * value for value in updated)) <= session.config.trust_radius + 1e-6


def test_softmax_preference_uses_rankings_when_ratings_are_unavailable() -> None:
    session = _session(trust_radius=0.8, current_z=[0.0, 0.0])
    candidates = [
        _candidate("c1", [0.6, 0.0]),
        _candidate("c2", [0.15, 0.5]),
        _candidate("c3", [-0.45, 0.05]),
        _candidate("c4", [-0.55, -0.25]),
    ]
    feedback = normalize_feedback(
        "rnd_test",
        FeedbackRequest(
            feedback_type=FeedbackType.top_k,
            payload={"ranking": ["c2", "c1", "c3", "c4"]},
        ),
    )

    updated, summary = SoftmaxPreferenceUpdater().update(session, candidates, feedback)

    assert summary["winner_candidate_id"] == "c2"
    assert updated[0] > -0.2
    assert updated[1] > 0.0


def test_borda_preference_uses_full_ranking_order() -> None:
    session = _session(trust_radius=0.8, current_z=[0.0, 0.0])
    candidates = [
        _candidate("c1", [0.62, 0.0]),
        _candidate("c2", [0.18, 0.5]),
        _candidate("c3", [-0.42, 0.12]),
        _candidate("c4", [-0.55, -0.22]),
    ]
    feedback = normalize_feedback(
        "rnd_test",
        FeedbackRequest(
            feedback_type=FeedbackType.top_k,
            payload={"ranking": ["c2", "c1", "c3", "c4"]},
        ),
    )

    updated, summary = BordaPreferenceUpdater().update(session, candidates, feedback)

    assert summary["updater"] == "borda_preference"
    assert summary["ranking_length"] == 4
    assert updated[0] > -0.1
    assert updated[1] > 0.0


def test_bradley_terry_preference_fits_pairwise_strengths_from_ratings() -> None:
    session = _session(trust_radius=0.8, current_z=[0.0, 0.0])
    candidates = [
        _candidate("c1", [0.6, 0.0]),
        _candidate("c2", [0.22, 0.48]),
        _candidate("c3", [-0.5, -0.1]),
    ]
    feedback = normalize_feedback(
        "rnd_test",
        FeedbackRequest(
            feedback_type=FeedbackType.scalar_rating,
            payload={"ratings": {"c1": 5.0, "c2": 4.0, "c3": 1.0}},
        ),
    )

    updated, summary = BradleyTerryPreferenceUpdater().update(session, candidates, feedback)

    assert summary["updater"] == "bradley_terry_preference"
    assert summary["pair_count"] >= 2
    assert updated[0] > 0.0
    assert updated[1] > -0.05


def test_challenger_mixture_preference_lets_near_tie_challenger_pull_state() -> None:
    session = _session(trust_radius=0.8, current_z=[0.35, 0.0])
    candidates = [
        Candidate(
            id="inc",
            round_id="rnd_test",
            candidate_index=0,
            z=[0.35, 0.0],
            sampler_role="incumbent",
            seed=1,
            generation_params={"carried_forward": True},
        ),
        _candidate("challenger_a", [0.44, 0.16]),
        _candidate("challenger_b", [0.18, 0.22]),
    ]
    feedback = normalize_feedback(
        "rnd_test",
        FeedbackRequest(
            feedback_type=FeedbackType.scalar_rating,
            payload={"ratings": {"inc": 5.0, "challenger_a": 4.8, "challenger_b": 3.5}},
        ),
    )

    updated, summary = ChallengerMixturePreferenceUpdater().update(session, candidates, feedback)

    assert summary["updater"] == "challenger_mixture_preference"
    assert updated[0] > session.current_z[0]
    assert updated[1] > 0.0


def test_plackett_luce_preference_uses_full_ranking_with_nonzero_tail_weights() -> None:
    session = _session(trust_radius=0.8, current_z=[0.0, 0.0])
    candidates = [
        _candidate("c1", [0.62, 0.0]),
        _candidate("c2", [0.2, 0.48]),
        _candidate("c3", [-0.35, 0.16]),
        _candidate("c4", [-0.55, -0.2]),
    ]
    feedback = normalize_feedback(
        "rnd_test",
        FeedbackRequest(
            feedback_type=FeedbackType.top_k,
            payload={"ranking": ["c2", "c1", "c3", "c4"]},
        ),
    )

    updated, summary = PlackettLucePreferenceUpdater().update(session, candidates, feedback)

    assert summary["updater"] == "plackett_luce_preference"
    assert summary["ranking_length"] == 4
    assert summary["weights"]["c4"] > 0.0
    assert updated[0] > -0.1
    assert updated[1] > 0.0


def test_oracle_selection_penalty_reweights_carried_forward_incumbent() -> None:
    rows = [
        {
            "candidate_id": "inc",
            "clip_score": 0.91,
            "carried_forward": True,
            "oracle_feedback_mode": FeedbackType.scalar_rating.value,
        },
        {
            "candidate_id": "challenger",
            "clip_score": 0.90,
            "carried_forward": False,
            "oracle_feedback_mode": FeedbackType.scalar_rating.value,
        },
    ]

    eligible = _eligible_oracle_candidates(
        rows,
        repeated_selected_image_streak=2,
        cooldown_rounds=0,
        penalty_rounds=2,
        incumbent_selection_penalty=0.03,
    )

    assert eligible[0]["oracle_penalty_applied"] is True
    assert eligible[0]["oracle_score"] == 0.88
    winner = max(eligible, key=lambda row: float(row["oracle_score"]))
    assert winner["candidate_id"] == "challenger"


def test_oracle_feedback_request_uses_oracle_score_ordering() -> None:
    rows = [
        {
            "candidate_id": "inc",
            "clip_score": 0.91,
            "oracle_score": 0.88,
            "carried_forward": True,
            "oracle_feedback_mode": FeedbackType.scalar_rating.value,
        },
        {
            "candidate_id": "challenger",
            "clip_score": 0.90,
            "oracle_score": 0.90,
            "carried_forward": False,
            "oracle_feedback_mode": FeedbackType.scalar_rating.value,
        },
    ]

    request = _oracle_feedback_request(rows, critique_text="oracle")

    assert request.feedback_type == FeedbackType.scalar_rating
    assert request.payload["ratings"]["challenger"] > request.payload["ratings"]["inc"]


def test_clip_dino_ensemble_oracle_policy_uses_both_metrics() -> None:
    rows = [
        {"candidate_id": "clip_favored", "clip_score": 0.92, "dinov2_score": 0.41, "incumbent_novelty": 0.2},
        {"candidate_id": "balanced", "clip_score": 0.9, "dinov2_score": 0.61, "incumbent_novelty": 0.2},
    ]

    scored = _apply_oracle_policy(rows, oracle_policy="clip_dino_ensemble")

    winner = max(scored, key=lambda row: float(row["oracle_score"]))
    assert winner["candidate_id"] == "balanced"


def test_clip_novelty_bonus_can_favor_more_novel_candidate() -> None:
    rows = [
        {"candidate_id": "incumbent_like", "clip_score": 0.91, "dinov2_score": 0.5, "incumbent_novelty": 0.05},
        {"candidate_id": "challenger", "clip_score": 0.9, "dinov2_score": 0.48, "incumbent_novelty": 0.55},
    ]

    scored = _apply_oracle_policy(rows, oracle_policy="clip_novelty_bonus")

    winner = max(scored, key=lambda row: float(row["oracle_score"]))
    assert winner["candidate_id"] == "challenger"


def test_pareto_frontier_oracle_can_choose_balanced_candidate_over_clip_only() -> None:
    rows = [
        {
            "candidate_id": "clip_heavy",
            "clip_score": 0.93,
            "dinov2_score": 0.38,
            "novelty_to_incumbent": 0.02,
            "carried_forward": True,
        },
        {
            "candidate_id": "balanced",
            "clip_score": 0.9,
            "dinov2_score": 0.62,
            "novelty_to_incumbent": 0.28,
            "carried_forward": False,
        },
    ]
    policy = PolicySpec(
        id="pareto_listwise",
        label="Pareto listwise",
        sampler="quality_diversity_mix",
        updater="plackett_luce_preference",
        feedback_mode="top_k",
        oracle_policy="pareto_frontier_mix",
    )

    scored = _oracle_score_candidates(rows, policy=policy, margin_epsilon=0.015)

    winner = max(scored, key=lambda row: float(row["oracle_score"]))
    assert winner["candidate_id"] == "balanced"


def _mean_distance(candidates: list[Candidate], center: list[float]) -> float:
    return sum(
        math.sqrt(sum((value - current) ** 2 for value, current in zip(candidate.z, center, strict=False)))
        for candidate in candidates
    ) / len(candidates)


def _unit_from(values: list[float]) -> list[float]:
    norm = math.sqrt(sum(value * value for value in values))
    if norm == 0.0:
        return [0.0 for _ in values]
    return [value / norm for value in values]
