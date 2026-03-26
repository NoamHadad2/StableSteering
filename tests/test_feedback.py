from __future__ import annotations

from app.core.schema import FeedbackRequest, FeedbackType
from app.feedback.normalization import normalize_feedback


def test_scalar_rating_normalization_chooses_highest_score() -> None:
    event = normalize_feedback(
        "round_1",
        FeedbackRequest(
            feedback_type=FeedbackType.scalar_rating,
            payload={"ratings": {"a": 2, "b": 5, "c": 4}},
        ),
    )
    assert event.normalized_payload["winner_candidate_id"] == "b"


def test_top_k_requires_ranking() -> None:
    request = FeedbackRequest(feedback_type=FeedbackType.top_k, payload={"ranking": ["c1", "c2"]})
    event = normalize_feedback("round_2", request)
    assert event.normalized_payload["winner_candidate_id"] == "c1"
    assert event.normalized_payload["ranking"] == ["c1", "c2"]


def test_winner_only_requires_explicit_winner() -> None:
    event = normalize_feedback(
        "round_2b",
        FeedbackRequest(feedback_type=FeedbackType.winner_only, payload={"winner_candidate_id": "c2"}),
    )
    assert event.normalized_payload["winner_candidate_id"] == "c2"


def test_approve_reject_normalization_collects_approved_and_rejected() -> None:
    event = normalize_feedback(
        "round_2c",
        FeedbackRequest(
            feedback_type=FeedbackType.approve_reject,
            payload={"winner_candidate_id": "c3", "approvals": {"c1": False, "c2": True, "c3": True}},
        ),
    )
    assert event.normalized_payload["winner_candidate_id"] == "c3"
    assert event.normalized_payload["approved_candidate_ids"] == ["c2", "c3"]
    assert event.normalized_payload["rejected_candidate_ids"] == ["c1"]


def test_scalar_rating_requires_non_empty_ratings() -> None:
    request = FeedbackRequest(feedback_type=FeedbackType.scalar_rating, payload={"ratings": {}})
    try:
        normalize_feedback("round_3", request)
    except ValueError as exc:
        assert "at least one rating" in str(exc)
    else:
        raise AssertionError("Expected scalar rating validation to fail")


def test_approve_reject_requires_one_approved_candidate() -> None:
    request = FeedbackRequest(
        feedback_type=FeedbackType.approve_reject,
        payload={"approvals": {"c1": False, "c2": False}},
    )
    try:
        normalize_feedback("round_4", request)
    except ValueError as exc:
        assert "at least one approved candidate" in str(exc)
    else:
        raise AssertionError("Expected approve/reject validation to fail")
