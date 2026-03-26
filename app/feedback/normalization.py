from __future__ import annotations

from app.core.schema import FeedbackEvent, FeedbackRequest, FeedbackType


def normalize_feedback(round_id: str, request: FeedbackRequest) -> FeedbackEvent:
    """Normalize multiple UI feedback shapes into one internal event format.

    The current MVP supports scalar ratings, pairwise selection, winner-only,
    approve/reject, and top-k ranking. All forms are reduced to a compact
    winner-centric structure so the updater layer can remain small and
    strategy-oriented.
    """

    payload = request.payload
    if request.feedback_type == FeedbackType.scalar_rating:
        ratings = payload.get("ratings", {})
        if not isinstance(ratings, dict):
            raise ValueError("scalar_rating feedback requires ratings to be a mapping")
        if not ratings:
            raise ValueError("scalar_rating feedback requires at least one rating")
        invalid_ratings = [candidate_id for candidate_id, score in ratings.items() if not isinstance(score, (int, float))]
        if invalid_ratings:
            raise ValueError("scalar_rating feedback requires numeric ratings")
        sorted_ratings = sorted(ratings.items(), key=lambda entry: (-entry[1], entry[0]))
        winner_candidate_id = sorted_ratings[0][0]
        normalized = {"winner_candidate_id": winner_candidate_id, "ratings": ratings}
    elif request.feedback_type == FeedbackType.pairwise:
        winner_candidate_id = payload.get("winner_candidate_id")
        loser_candidate_id = payload.get("loser_candidate_id")
        if not winner_candidate_id:
            raise ValueError("pairwise feedback requires winner_candidate_id")
        if not loser_candidate_id:
            raise ValueError("pairwise feedback requires loser_candidate_id")
        if winner_candidate_id == loser_candidate_id:
            raise ValueError("pairwise feedback requires different winner and loser candidates")
        normalized = {
            "winner_candidate_id": winner_candidate_id,
            "loser_candidate_id": loser_candidate_id,
        }
    elif request.feedback_type == FeedbackType.winner_only:
        winner_candidate_id = payload.get("winner_candidate_id")
        if not winner_candidate_id:
            raise ValueError("winner_only feedback requires winner_candidate_id")
        normalized = {"winner_candidate_id": winner_candidate_id}
    elif request.feedback_type == FeedbackType.approve_reject:
        approvals = payload.get("approvals", {})
        if not isinstance(approvals, dict):
            raise ValueError("approve_reject feedback requires approvals to be a mapping")
        if not approvals:
            raise ValueError("approve_reject feedback requires at least one approval decision")
        invalid_approvals = [candidate_id for candidate_id, approved in approvals.items() if not isinstance(approved, bool)]
        if invalid_approvals:
            raise ValueError("approve_reject feedback requires boolean approval values")
        approved_candidate_ids = [candidate_id for candidate_id, approved in approvals.items() if approved]
        if not approved_candidate_ids:
            raise ValueError("approve_reject feedback requires at least one approved candidate")
        winner_candidate_id = payload.get("winner_candidate_id") or approved_candidate_ids[0]
        if winner_candidate_id not in approved_candidate_ids:
            raise ValueError("approve_reject winner_candidate_id must also be approved")
        normalized = {
            "winner_candidate_id": winner_candidate_id,
            "approved_candidate_ids": approved_candidate_ids,
            "rejected_candidate_ids": [candidate_id for candidate_id, approved in approvals.items() if not approved],
            "approvals": approvals,
        }
    else:
        ranking = payload.get("ranking", [])
        if not isinstance(ranking, list):
            raise ValueError("ranking feedback requires ranking to be a list")
        if not ranking:
            raise ValueError("ranking feedback requires a non-empty ranking list")
        if len(ranking) < 2:
            raise ValueError("ranking feedback requires at least two ranked candidates")
        if len(set(ranking)) != len(ranking):
            raise ValueError("ranking feedback requires unique candidate ids")
        normalized = {"winner_candidate_id": ranking[0], "ranking": ranking}

    return FeedbackEvent(
        round_id=round_id,
        type=request.feedback_type,
        payload=payload,
        normalized_payload=normalized,
        critique_text=request.critique_text,
    )
