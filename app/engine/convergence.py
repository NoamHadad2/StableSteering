from __future__ import annotations

import math

from app.core.schema import ConvergenceReport, Round, Session


def _l2_distance(left: list[float], right: list[float]) -> float:
    """Return the Euclidean distance between two equal-length vectors."""

    width = max(len(left), len(right))
    total = 0.0
    for index in range(width):
        a = left[index] if index < len(left) else 0.0
        b = right[index] if index < len(right) else 0.0
        delta = a - b
        total += delta * delta
    return math.sqrt(total)


def _winner_image_key(round_obj: Round) -> str | None:
    """Return a stable key for the image selected as the winner of a round."""

    if not round_obj.update_summary:
        return None
    winner_id = round_obj.update_summary.get("winner_candidate_id")
    if not winner_id:
        return None
    winner = next((candidate for candidate in round_obj.candidates if candidate.id == winner_id), None)
    if winner is None:
        return None
    return winner.image_path or repr([round(value, 6) for value in winner.z])


def evaluate_convergence(
    session: Session,
    rounds: list[Round],
    *,
    patience: int | None = None,
    min_delta: float | None = None,
) -> ConvergenceReport:
    """Measure how settled a session's steering trajectory is.

    A round is considered "quiet" when the steering vector barely moved
    (step magnitude at or below ``min_delta * trust_radius``) or when its
    selected winner image repeated the previous round's winner. The session is
    reported as converged once ``patience`` consecutive quiet rounds occur. With
    ``patience == 0`` convergence detection is disabled, preserving the prior
    open-ended behavior.

    The function is pure: it derives everything from ``session`` and the given
    ``rounds`` list and performs no I/O, which keeps it cheap to unit test.
    """

    resolved_patience = int(session.config.convergence_patience if patience is None else patience)
    resolved_min_delta = float(session.config.convergence_min_delta if min_delta is None else min_delta)
    threshold = resolved_min_delta * float(session.config.trust_radius)

    # Only rounds whose feedback has been applied move the steering state, so we
    # ignore a trailing round that is still awaiting feedback to avoid declaring
    # a premature, artificial convergence.
    completed = [round_obj for round_obj in rounds if round_obj.update_summary]

    report = ConvergenceReport(
        rounds_completed=len(completed),
        patience=resolved_patience,
        min_delta=resolved_min_delta,
    )

    if not completed:
        return report

    # Trajectory of steering points: each completed round's starting incumbent,
    # followed by the session's current (post-feedback) steering vector.
    points = [round_obj.incumbent_z for round_obj in completed] + [session.current_z]
    steps = [_l2_distance(points[index + 1], points[index]) for index in range(len(completed))]
    report.step_magnitudes = [round(value, 6) for value in steps]
    report.latest_step = report.step_magnitudes[-1]

    window = resolved_patience if resolved_patience > 0 else len(steps)
    window = max(1, min(window, len(steps)))
    report.mean_recent_step = round(sum(steps[-window:]) / window, 6)

    if resolved_patience <= 0:
        # Detection disabled: surface the measurements but never report converged.
        return report

    running_streak = 0
    trailing_streak = 0
    rounds_to_convergence: int | None = None
    previous_image_key: str | None = None
    for index, round_obj in enumerate(completed):
        image_key = _winner_image_key(round_obj)
        step_quiet = steps[index] <= threshold
        image_quiet = (
            index > 0 and image_key is not None and image_key == previous_image_key
        )
        previous_image_key = image_key

        if step_quiet or image_quiet:
            running_streak += 1
        else:
            running_streak = 0

        if running_streak >= resolved_patience and rounds_to_convergence is None:
            rounds_to_convergence = round_obj.round_index

    trailing_streak = running_streak
    report.quiet_streak = trailing_streak
    report.converged = trailing_streak >= resolved_patience
    report.rounds_to_convergence = rounds_to_convergence

    if report.converged:
        # Prefer the most specific explanation for the trailing quiet streak.
        last_round = completed[-1]
        last_step_quiet = steps[-1] <= threshold
        last_image_key = _winner_image_key(last_round)
        previous_key = _winner_image_key(completed[-2]) if len(completed) >= 2 else None
        last_image_quiet = last_image_key is not None and last_image_key == previous_key
        if last_step_quiet:
            report.reason = "step_below_threshold"
        elif last_image_quiet:
            report.reason = "incumbent_repeated"
        else:
            report.reason = "step_below_threshold"

    return report
