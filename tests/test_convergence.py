from __future__ import annotations

from app.core.schema import Candidate, Round, Session, StrategyConfig
from app.engine.convergence import evaluate_convergence


def _make_round(round_index: int, incumbent_z: list[float], winner_z: list[float], winner_image: str) -> Round:
    """Build a completed round whose feedback selected a known winner image."""

    round_obj = Round(
        session_id="ses_unit",
        round_index=round_index,
        incumbent_z=incumbent_z,
        trust_radius=0.55,
        seed_policy="fixed-per-candidate",
    )
    winner = Candidate(
        round_id=round_obj.id,
        candidate_index=0,
        z=winner_z,
        sampler_role="incumbent",
        seed=1,
        generation_params={},
        image_path=winner_image,
    )
    round_obj.candidates = [winner]
    round_obj.update_summary = {"winner_candidate_id": winner.id}
    return round_obj


def _make_session(current_z: list[float], *, patience: int = 2, min_delta: float = 0.04) -> Session:
    config = StrategyConfig(
        updater="winner_copy",
        trust_radius=0.55,
        convergence_patience=patience,
        convergence_min_delta=min_delta,
    )
    return Session(
        experiment_id="exp_unit",
        prompt="unit prompt",
        model_name=config.model_name,
        config=config,
        current_z=current_z,
    )


# ----------------------------------------------------------------------------
# Unit-level tests of the pure convergence evaluator (the three reason branches).
# ----------------------------------------------------------------------------


def test_evaluate_convergence_step_below_threshold() -> None:
    rounds = [
        _make_round(1, [0.0, 0.0], [0.5, 0.0], "img-a"),
        _make_round(2, [0.5, 0.0], [0.5, 0.0], "img-b"),
        _make_round(3, [0.5, 0.0], [0.5, 0.0], "img-c"),
    ]
    report = evaluate_convergence(_make_session([0.5, 0.0]), rounds)

    assert report.rounds_completed == 3
    assert len(report.step_magnitudes) == 3
    assert report.converged is True
    assert report.rounds_to_convergence == 3
    assert report.reason == "step_below_threshold"


def test_evaluate_convergence_incumbent_repeated() -> None:
    # z keeps drifting above the quiet threshold, but the same winner image
    # repeats every round, which should still count as a quiet (settled) signal.
    rounds = [
        _make_round(1, [0.0, 0.0], [0.1, 0.0], "same-img"),
        _make_round(2, [0.1, 0.0], [0.2, 0.0], "same-img"),
        _make_round(3, [0.2, 0.0], [0.3, 0.0], "same-img"),
    ]
    report = evaluate_convergence(_make_session([0.3, 0.0]), rounds)

    assert report.converged is True
    assert report.rounds_to_convergence == 3
    assert report.reason == "incumbent_repeated"


def test_evaluate_convergence_not_converged_when_still_moving() -> None:
    rounds = [
        _make_round(1, [0.0, 0.0], [0.2, 0.0], "img-a"),
        _make_round(2, [0.2, 0.0], [0.4, 0.0], "img-b"),
        _make_round(3, [0.4, 0.0], [0.6, 0.0], "img-c"),
    ]
    report = evaluate_convergence(_make_session([0.8, 0.0]), rounds)

    assert report.converged is False
    assert report.rounds_to_convergence is None
    assert report.reason == "not_converged"


def test_evaluate_convergence_disabled_with_zero_patience() -> None:
    rounds = [
        _make_round(1, [0.0, 0.0], [0.5, 0.0], "img-a"),
        _make_round(2, [0.5, 0.0], [0.5, 0.0], "img-a"),
        _make_round(3, [0.5, 0.0], [0.5, 0.0], "img-a"),
    ]
    report = evaluate_convergence(_make_session([0.5, 0.0], patience=0), rounds)

    assert report.converged is False
    assert report.rounds_to_convergence is None
    # Measurements are still surfaced even when detection is disabled.
    assert report.step_magnitudes


# ----------------------------------------------------------------------------
# End-to-end tests through the API, driving a real session to convergence with
# the mock backend (no GPU).
# ----------------------------------------------------------------------------


def _create_session(client, *, convergence_patience: int) -> str:
    experiment = client.post(
        "/experiments",
        json={
            "name": "Convergence flow",
            "description": "Drive a session to a settled steering state",
            "config": {
                "sampler": "random_local",
                "updater": "winner_copy",
                "feedback_mode": "winner_only",
                "candidate_count": 4,
                "convergence_patience": convergence_patience,
            },
        },
    )
    assert experiment.status_code == 200
    session = client.post(
        "/sessions",
        json={"experiment_id": experiment.json()["id"], "prompt": "A calm settled scene", "negative_prompt": ""},
    )
    assert session.status_code == 200
    return session.json()["id"]


def _winner_only_feedback(client, round_id: str, winner_candidate_id: str) -> None:
    response = client.post(
        f"/rounds/{round_id}/feedback",
        json={"feedback_type": "winner_only", "payload": {"winner_candidate_id": winner_candidate_id}},
    )
    assert response.status_code == 200


def test_session_converges_when_user_keeps_the_incumbent(client) -> None:
    session_id = _create_session(client, convergence_patience=2)

    # Round 1: pick an exploratory candidate so the steering vector moves.
    round_one = client.post(f"/sessions/{session_id}/rounds/next").json()
    _winner_only_feedback(client, round_one["round_id"], round_one["candidate_metadata"][1]["id"])
    assert client.get(f"/sessions/{session_id}").json()["converged"] is False

    # Round 2: keep the carried-forward incumbent (index 0) -> z stops moving.
    round_two = client.post(f"/sessions/{session_id}/rounds/next").json()
    assert round_two["candidate_metadata"][0]["sampler_role"] == "incumbent"
    _winner_only_feedback(client, round_two["round_id"], round_two["candidate_metadata"][0]["id"])
    assert client.get(f"/sessions/{session_id}").json()["converged"] is False

    # Round 3: keep the incumbent again -> two consecutive quiet rounds -> converged.
    round_three = client.post(f"/sessions/{session_id}/rounds/next").json()
    _winner_only_feedback(client, round_three["round_id"], round_three["candidate_metadata"][0]["id"])

    session_payload = client.get(f"/sessions/{session_id}").json()
    assert session_payload["converged"] is True
    assert session_payload["rounds_to_convergence"] == 3

    convergence = client.get(f"/sessions/{session_id}/convergence/json")
    assert convergence.status_code == 200
    report = convergence.json()
    assert report["converged"] is True
    assert report["rounds_to_convergence"] == 3
    assert report["rounds_completed"] == 3
    assert len(report["step_magnitudes"]) == 3
    assert report["reason"] in {"step_below_threshold", "incumbent_repeated"}


def test_session_never_converges_when_patience_disabled(client) -> None:
    session_id = _create_session(client, convergence_patience=0)

    round_one = client.post(f"/sessions/{session_id}/rounds/next").json()
    _winner_only_feedback(client, round_one["round_id"], round_one["candidate_metadata"][1]["id"])
    for _ in range(3):
        nxt = client.post(f"/sessions/{session_id}/rounds/next").json()
        _winner_only_feedback(client, nxt["round_id"], nxt["candidate_metadata"][0]["id"])

    session_payload = client.get(f"/sessions/{session_id}").json()
    assert session_payload["converged"] is False
    assert session_payload["rounds_to_convergence"] is None


def test_convergence_endpoint_unknown_session_returns_404(client) -> None:
    response = client.get("/sessions/ses_missing/convergence/json")
    assert response.status_code == 404
    assert response.json()["error_code"] == "not_found"
