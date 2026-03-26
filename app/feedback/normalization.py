from __future__ import annotations

from app.core.schema import FeedbackEvent, FeedbackRequest, FeedbackType


def normalize_feedback(round_id: str, request: FeedbackRequest) -> FeedbackEvent:
    """Normalize multiple UI feedback shapes into one internal event format.

    The current MVP supports scalar ratings, pairwise selection, and top-k
    ranking. All three forms are reduced to a winner-centric structure so the
    updater layer can remain small and strategy-oriented.
    """

    payload = request.payload
    if request.feedback_type == FeedbackType.scalar_rating:
        ratings = payload.get("ratings", {})
        if not ratings:
            raise ValueError("scalar_rating feedback requires at least one rating")
        winner_candidate_id = max(ratings, key=ratings.get)
        normalized = {"winner_candidate_id": winner_candidate_id, "ratings": ratings}
    elif request.feedback_type == FeedbackType.pairwise:
        if not payload.get("winner_candidate_id"):
            raise ValueError("pairwise feedback requires winner_candidate_id")
        normalized = {
            "winner_candidate_id": payload["winner_candidate_id"],
            "loser_candidate_id": payload.get("loser_candidate_id"),
        }
    elif request.feedback_type == FeedbackType.winner_only:
        winner_candidate_id = payload.get("winner_candidate_id")
        if not winner_candidate_id:
            raise ValueError("winner_only feedback requires winner_candidate_id")
        normalized = {"winner_candidate_id": winner_candidate_id}
    elif request.feedback_type == FeedbackType.approve_reject:
        approvals = payload.get("approvals", {})
        if not approvals:
            raise ValueError("approve_reject feedback requires at least one approval decision")
        approved_candidate_ids = [candidate_id for candidate_id, approved in approvals.items() if approved]
        if not approved_candidate_ids:
            raise ValueError("approve_reject feedback requires at least one approved candidate")
        winner_candidate_id = payload.get("winner_candidate_id") or approved_candidate_ids[0]
        normalized = {
            "winner_candidate_id": winner_candidate_id,
            "approved_candidate_ids": approved_candidate_ids,
            "rejected_candidate_ids": [candidate_id for candidate_id, approved in approvals.items() if not approved],
            "approvals": approvals,
        }
    else:
        ranking = payload.get("ranking", [])
        if not ranking:
            raise ValueError("ranking feedback requires a non-empty ranking list")
        normalized = {"winner_candidate_id": ranking[0], "ranking": ranking}

    return FeedbackEvent(
        round_id=round_id,
        type=request.feedback_type,
        payload=payload,
        normalized_payload=normalized,
        critique_text=request.critique_text,
    )
