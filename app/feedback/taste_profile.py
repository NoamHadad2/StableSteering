from __future__ import annotations

import math
from app.core.schema import Round


def compute_taste_profile(rounds: list[Round]) -> dict:
    """Derive a per-dimension preference profile from all feedback events.

    For each dimension collects every rating the user gave across all rounds,
    then computes mean, consistency (1 - normalised std), trend direction, and
    a combined signal strength.  Also tallies recurring negative pins.
    """

    feedback_events = [
        fb
        for r in rounds
        for fb in r.feedback_events
        if r.round_index > 0
    ]

    if not feedback_events:
        return {"dimensions": {}, "negative_pins": {}, "confidence": 0.0, "rounds_used": 0}

    # Collect per-dimension rating lists
    dim_ratings: dict[str, list[float]] = {}
    dim_by_round: dict[str, list[float]] = {}  # round_index -> avg rating that round

    for event in feedback_events:
        round_obj = next((r for r in rounds if r.id == event.round_id), None)
        round_index = round_obj.round_index if round_obj else 0
        for _cid, dims in event.dimension_ratings.items():
            for dim, score in dims.items():
                if score <= 0:
                    continue
                dim_ratings.setdefault(dim, []).append(float(score))
                dim_by_round.setdefault(dim, {}).setdefault(round_index, []).append(float(score))

    # Collect negative pins
    pin_counts: dict[str, int] = {}
    for event in feedback_events:
        for pins in event.negative_pins.values():
            for pin in pins:
                pin_counts[pin] = pin_counts.get(pin, 0) + 1

    # Collect priority signals (lower number = higher priority)
    dim_priority_sum: dict[str, list[int]] = {}
    for event in feedback_events:
        for _cid, priorities in event.dimension_priorities.items():
            for dim, rank in priorities.items():
                dim_priority_sum.setdefault(dim, []).append(rank)

    # Build per-dimension profile
    dimensions: dict[str, dict] = {}
    for dim, ratings in dim_ratings.items():
        mean = sum(ratings) / len(ratings)
        variance = sum((r - mean) ** 2 for r in ratings) / max(len(ratings), 1)
        std = math.sqrt(variance)
        consistency = max(0.0, 1.0 - std / 2.5)
        signal = mean / 5.0 * consistency

        # Trend: compare first half vs second half of rounds
        sorted_rounds = sorted(dim_by_round.get(dim, {}).items())
        if len(sorted_rounds) >= 2:
            mid = len(sorted_rounds) // 2
            early = sum(v for _, vs in sorted_rounds[:mid] for v in (vs if isinstance(vs, list) else [vs])) / max(1, sum(len(vs) if isinstance(vs, list) else 1 for _, vs in sorted_rounds[:mid]))
            late = sum(v for _, vs in sorted_rounds[mid:] for v in (vs if isinstance(vs, list) else [vs])) / max(1, sum(len(vs) if isinstance(vs, list) else 1 for _, vs in sorted_rounds[mid:]))
            diff = late - early
            trend = "growing" if diff > 0.3 else "declining" if diff < -0.3 else "stable"
        else:
            trend = "new"

        # Average priority rank (lower = more important to user)
        avg_priority = None
        if dim in dim_priority_sum and dim_priority_sum[dim]:
            avg_priority = sum(dim_priority_sum[dim]) / len(dim_priority_sum[dim])

        dimensions[dim] = {
            "mean": round(mean, 2),
            "consistency": round(consistency, 2),
            "signal": round(signal, 2),
            "signal_pct": round(signal * 100),
            "trend": trend,
            "sample_count": len(ratings),
            "avg_priority": round(avg_priority, 1) if avg_priority is not None else None,
        }

    # Sort by signal strength descending
    dimensions = dict(sorted(dimensions.items(), key=lambda x: -x[1]["signal"]))

    # Overall profile confidence = mean signal across dims, weighted by sample count
    if dimensions:
        total_samples = sum(d["sample_count"] for d in dimensions.values())
        confidence = sum(d["signal"] * d["sample_count"] for d in dimensions.values()) / max(total_samples, 1)
    else:
        confidence = 0.0

    # Stable since round = first round where all dims had data
    return {
        "dimensions": dimensions,
        "negative_pins": dict(sorted(pin_counts.items(), key=lambda x: -x[1])),
        "confidence": round(confidence * 100),
        "rounds_used": len({r.round_index for r in rounds if r.round_index > 0 and any(fb.dimension_ratings for fb in r.feedback_events)}),
    }
