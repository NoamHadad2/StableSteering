from __future__ import annotations

import time


def test_session_lifecycle_round_feedback_round(client) -> None:
    experiment = client.post(
        "/experiments",
        json={
            "name": "Lifecycle",
            "description": "Lifecycle test",
            "config": {
                "sampler": "random_local",
                "updater": "winner_average",
                "feedback_mode": "scalar_rating",
                "candidate_count": 4,
            },
        },
    )
    assert experiment.status_code == 200
    experiment_id = experiment.json()["id"]

    session = client.post(
        "/sessions",
        json={"experiment_id": experiment_id, "prompt": "A red racing car", "negative_prompt": "blurry"},
    )
    assert session.status_code == 200
    session_id = session.json()["id"]

    round_one = client.post(f"/sessions/{session_id}/rounds/next")
    assert round_one.status_code == 200
    round_payload = round_one.json()
    assert len(round_payload["candidate_metadata"]) == 4

    blocked_round = client.post(f"/sessions/{session_id}/rounds/next")
    assert blocked_round.status_code == 409

    ratings = {
        round_payload["candidate_metadata"][0]["id"]: 2,
        round_payload["candidate_metadata"][1]["id"]: 5,
        round_payload["candidate_metadata"][2]["id"]: 3,
        round_payload["candidate_metadata"][3]["id"]: 1,
    }
    feedback = client.post(
        f"/rounds/{round_payload['round_id']}/feedback",
        json={"feedback_type": "scalar_rating", "payload": {"ratings": ratings}},
    )
    assert feedback.status_code == 200
    next_state = feedback.json()["next_incumbent_state"]
    assert next_state != [0.0, 0.0, 0.0]

    round_two = client.post(f"/sessions/{session_id}/rounds/next")
    assert round_two.status_code == 200
    assert round_two.json()["state_summary"]["round_index"] == 2

    duplicate_feedback = client.post(
        f"/rounds/{round_payload['round_id']}/feedback",
        json={"feedback_type": "scalar_rating", "payload": {"ratings": ratings}},
    )
    assert duplicate_feedback.status_code == 409


def test_replay_export_contains_rounds(client) -> None:
    experiment = client.post(
        "/experiments",
        json={"name": "Replay", "description": "Replay test", "config": {"candidate_count": 4}},
    ).json()
    session = client.post(
        "/sessions",
        json={"experiment_id": experiment["id"], "prompt": "A geometric sculpture", "negative_prompt": ""},
    ).json()
    round_payload = client.post(f"/sessions/{session['id']}/rounds/next").json()
    ratings = {candidate["id"]: 5 - index for index, candidate in enumerate(round_payload["candidate_metadata"])}
    client.post(
        f"/rounds/{round_payload['round_id']}/feedback",
        json={"feedback_type": "scalar_rating", "payload": {"ratings": ratings}},
    )
    replay = client.get(f"/sessions/{session['id']}/replay")
    assert replay.status_code == 200
    replay_payload = replay.json()
    assert replay_payload["schema_version"] == "1.0"
    assert replay_payload["app_version"] == "0.1.0"
    assert replay_payload["exported_at"]
    assert replay_payload["session"]["id"] == session["id"]
    assert len(replay_payload["rounds"]) == 1
    assert replay_payload["rounds"][0]["feedback_events"][0]["normalized_payload"]["winner_candidate_id"] in ratings


def test_pairwise_feedback_mode_submits_successfully(client) -> None:
    experiment = client.post(
        "/experiments",
        json={
            "name": "Pairwise",
            "description": "Pairwise test",
            "config": {
                "sampler": "random_local",
                "updater": "winner_copy",
                "feedback_mode": "pairwise",
                "candidate_count": 3,
            },
        },
    ).json()
    session = client.post(
        "/sessions",
        json={"experiment_id": experiment["id"], "prompt": "A glossy concept chair", "negative_prompt": ""},
    ).json()
    round_payload = client.post(f"/sessions/{session['id']}/rounds/next").json()
    winner = round_payload["candidate_metadata"][0]["id"]
    loser = round_payload["candidate_metadata"][1]["id"]

    feedback = client.post(
        f"/rounds/{round_payload['round_id']}/feedback",
        json={"feedback_type": "pairwise", "payload": {"winner_candidate_id": winner, "loser_candidate_id": loser}},
    )
    assert feedback.status_code == 200


def test_feedback_rejects_unknown_candidate_id(client) -> None:
    experiment = client.post(
        "/experiments",
        json={"name": "Invalid feedback", "description": "Invalid candidate", "config": {"candidate_count": 2}},
    ).json()
    session = client.post(
        "/sessions",
        json={"experiment_id": experiment["id"], "prompt": "A clean product render", "negative_prompt": ""},
    ).json()
    round_payload = client.post(f"/sessions/{session['id']}/rounds/next").json()

    feedback = client.post(
        f"/rounds/{round_payload['round_id']}/feedback",
        json={"feedback_type": "pairwise", "payload": {"winner_candidate_id": "cand_missing", "loser_candidate_id": "cand_other"}},
    )
    assert feedback.status_code == 400
    payload = feedback.json()
    assert payload["error_code"] == "invalid_input"
    assert "unknown winner candidate" in payload["message"]


def test_diagnostics_endpoint_reports_backend_and_device(client) -> None:
    response = client.get("/diagnostics")
    assert response.status_code == 200
    payload = response.json()
    assert payload["backend"] == "mock"
    assert payload["test_only_backend"] is True
    assert "cuda_available" in payload
    assert "active_device" in payload


def test_async_round_job_completes_and_returns_result(client) -> None:
    experiment = client.post("/experiments", json={"name": "Async round", "config": {"candidate_count": 2}}).json()
    session = client.post(
        "/sessions",
        json={"experiment_id": experiment["id"], "prompt": "An async round prompt", "negative_prompt": ""},
    ).json()

    job = client.post(f"/sessions/{session['id']}/rounds/next/async")
    assert job.status_code == 202
    status = client.get(job.json()["status_url"]).json()
    assert status["state"] in {"queued", "running", "succeeded"}

    for _ in range(20):
        status = client.get(job.json()["status_url"]).json()
        if status["state"] == "succeeded":
            break
        time.sleep(0.01)
    assert status["state"] == "succeeded"
    assert status["result"]["round_id"]
    assert len(status["result"]["candidate_metadata"]) == 2


def test_async_feedback_job_completes_and_returns_result(client) -> None:
    experiment = client.post("/experiments", json={"name": "Async feedback", "config": {"candidate_count": 2}}).json()
    session = client.post(
        "/sessions",
        json={"experiment_id": experiment["id"], "prompt": "An async feedback prompt", "negative_prompt": ""},
    ).json()
    round_payload = client.post(f"/sessions/{session['id']}/rounds/next").json()
    ratings = {candidate["id"]: 5 - index for index, candidate in enumerate(round_payload["candidate_metadata"])}

    job = client.post(
        f"/rounds/{round_payload['round_id']}/feedback/async",
        json={"feedback_type": "scalar_rating", "payload": {"ratings": ratings}},
    )
    assert job.status_code == 202

    for _ in range(20):
        status = client.get(job.json()["status_url"]).json()
        if status["state"] == "succeeded":
            break
        time.sleep(0.01)
    assert status["state"] == "succeeded"
    assert status["result"]["update_summary"]["winner_candidate_id"] in ratings
