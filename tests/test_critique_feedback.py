from __future__ import annotations

from app.core.schema import Candidate, FeedbackEvent, FeedbackRequest, Session, StrategyConfig
from app.feedback.normalization import _normalize_critique_rating, normalize_feedback
from app.updaters.critique_weighted_pref import CritiqueWeightedPreferenceUpdater
from app.updaters.winner_average import WinnerAverageUpdater


# ----------------------------------------------------------------------------
# Unit tests for the critique-rating normalizer.
# ----------------------------------------------------------------------------


def test_normalize_critique_rating_picks_top_rated_winner_and_keeps_tags() -> None:
    payload = {
        "ratings": {"c1": 2.0, "c2": 5.0},
        "critique_tags": {"c1": ["too_dark"], "c2": ["good_color", "good_detail"]},
    }
    normalized = _normalize_critique_rating(payload)

    assert normalized["winner_candidate_id"] == "c2"
    assert normalized["ratings"] == {"c1": 2.0, "c2": 5.0}
    assert normalized["critique_tags"] == {"c1": ["too_dark"], "c2": ["good_color", "good_detail"]}


def test_normalize_critique_rating_drops_empty_tag_lists() -> None:
    payload = {"ratings": {"c1": 4.0}, "critique_tags": {"c1": [], "c2": ["", "  "]}}
    normalized = _normalize_critique_rating(payload)

    assert normalized["critique_tags"] == {}


def test_normalize_feedback_routes_critique_rating_and_sets_event_tags() -> None:
    request = FeedbackRequest(
        feedback_type="critique_rating",
        payload={"ratings": {"c1": 5.0}, "critique_tags": {"c1": ["good_composition"]}},
    )
    event = normalize_feedback("rnd_unit", request)

    assert event.type.value == "critique_rating"
    assert event.normalized_payload["winner_candidate_id"] == "c1"
    assert event.critique_tags == {"c1": ["good_composition"]}


# ----------------------------------------------------------------------------
# Unit tests for the critique-weighted updater (the math that uses tags).
# ----------------------------------------------------------------------------


def _session(current_z: list[float]) -> Session:
    config = StrategyConfig(updater="critique_weighted_preference", trust_radius=0.55)
    return Session(
        experiment_id="exp_unit",
        prompt="unit prompt",
        model_name=config.model_name,
        config=config,
        current_z=current_z,
    )


def _candidate(z: list[float]) -> Candidate:
    return Candidate(
        round_id="rnd_unit",
        candidate_index=0,
        z=z,
        sampler_role="incumbent",
        seed=1,
        generation_params={},
    )


def _event(winner_id: str, ratings: dict, tags: dict) -> FeedbackEvent:
    return FeedbackEvent(
        round_id="rnd_unit",
        type="critique_rating",
        payload={},
        normalized_payload={"winner_candidate_id": winner_id, "ratings": ratings, "critique_tags": tags},
        critique_tags=tags,
    )


def test_critique_updater_moves_toward_positive_and_away_from_negative() -> None:
    positive = _candidate([0.5, 0.0])
    negative = _candidate([-0.5, 0.0])
    event = _event(
        positive.id,
        {positive.id: 5.0, negative.id: 1.0},
        {positive.id: ["good_color", "good_detail"], negative.id: ["too_dark"]},
    )
    updated, summary = CritiqueWeightedPreferenceUpdater().update(_session([0.0, 0.0]), [positive, negative], event)

    # Direction is (positive_center - negative_center) = (+x), so z moves +x.
    assert updated[0] > 0.0
    assert summary["positive_tag_count"] == 2
    assert summary["negative_tag_count"] == 1
    assert summary["method"] == "critique_weighted_move"


def test_critique_updater_differs_from_winner_average_on_same_ratings() -> None:
    """The tags must change the trajectory, otherwise the comparison study is meaningless."""

    winner = _candidate([0.5, 0.0])
    other = _candidate([-0.5, 0.0])
    ratings = {winner.id: 5.0, other.id: 1.0}
    tags = {winner.id: ["good_color"], other.id: ["too_dark", "wrong_style"]}

    critique_event = _event(winner.id, ratings, tags)
    plain_event = _event(winner.id, ratings, {})  # same ratings, no tags

    critique_z, _ = CritiqueWeightedPreferenceUpdater().update(_session([0.0, 0.0]), [winner, other], critique_event)
    winner_avg_z, _ = WinnerAverageUpdater().update(_session([0.0, 0.0]), [winner, other], plain_event)

    # With explicit negative evidence the critique updater takes a different step
    # than the tag-blind winner_average updater on identical ratings.
    assert critique_z != winner_avg_z


def test_critique_updater_falls_back_to_winner_without_tags() -> None:
    winner = _candidate([0.4, 0.0])
    other = _candidate([-0.4, 0.0])
    event = _event(winner.id, {winner.id: 5.0, other.id: 1.0}, {})
    updated, summary = CritiqueWeightedPreferenceUpdater().update(_session([0.0, 0.0]), [winner, other], event)

    # No tags -> still moves toward the rated winner (never a no-op).
    assert updated[0] > 0.0
    assert summary["positive_tag_count"] == 0
    assert summary["negative_tag_count"] == 0


# ----------------------------------------------------------------------------
# Backward compatibility: existing updaters accept a critique_rating payload.
# ----------------------------------------------------------------------------


def test_winner_average_works_with_critique_rating_payload() -> None:
    winner = _candidate([0.6, 0.0])
    other = _candidate([-0.2, 0.0])
    event = _event(winner.id, {winner.id: 5.0, other.id: 2.0}, {winner.id: ["good_color"]})
    updated, summary = WinnerAverageUpdater().update(_session([0.0, 0.0]), [winner, other], event)

    assert summary["winner_candidate_id"] == winner.id
    assert updated == [0.3, 0.0]  # halfway to the winner, tags ignored as expected


# ----------------------------------------------------------------------------
# End-to-end through the API with the mock backend (no GPU).
# ----------------------------------------------------------------------------


def test_critique_session_stores_tags_and_moves_steering_vector(client) -> None:
    experiment = client.post(
        "/experiments",
        json={
            "name": "Critique flow",
            "description": "Critique-assisted steering",
            "config": {
                "sampler": "random_local",
                "updater": "critique_weighted_preference",
                "feedback_mode": "critique_rating",
                "candidate_count": 4,
            },
        },
    )
    assert experiment.status_code == 200
    session = client.post(
        "/sessions",
        json={"experiment_id": experiment.json()["id"], "prompt": "A calm critique scene", "negative_prompt": ""},
    )
    assert session.status_code == 200
    session_id = session.json()["id"]

    round_one = client.post(f"/sessions/{session_id}/rounds/next").json()
    candidates = round_one["candidate_metadata"]
    ratings = {candidates[0]["id"]: 5.0, candidates[1]["id"]: 1.0}
    tags = {candidates[0]["id"]: ["good_composition"], candidates[1]["id"]: ["too_dark"]}

    feedback = client.post(
        f"/rounds/{round_one['round_id']}/feedback",
        json={"feedback_type": "critique_rating", "payload": {"ratings": ratings, "critique_tags": tags}},
    )
    assert feedback.status_code == 200

    replay = client.get(f"/sessions/{session_id}/replay").json()
    first_round = replay["rounds"][0]
    stored_event = first_round["feedback_events"][0]
    assert stored_event["normalized_payload"]["critique_tags"] == tags
    assert first_round["update_summary"]["method"] == "critique_weighted_move"
