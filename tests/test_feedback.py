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


def test_scalar_rating_requires_non_empty_ratings() -> None:
    request = FeedbackRequest(feedback_type=FeedbackType.scalar_rating, payload={"ratings": {}})
    try:
        normalize_feedback("round_3", request)
    except ValueError as exc:
        assert "at least one rating" in str(exc)
    else:
        raise AssertionError("Expected scalar rating validation to fail")
