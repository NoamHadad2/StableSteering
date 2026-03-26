from __future__ import annotations

import itertools
import time
import math


def test_setup_session_endpoint_accepts_yaml_config(client) -> None:
    response = client.post(
        "/setup/session",
        json={
            "experiment_name": "YAML setup",
            "description": "Setup page yaml flow",
            "prompt": "A structured YAML setup prompt",
            "negative_prompt": "blurry",
            "config_yaml": """
sampler: exploit_orthogonal
updater: linear_preference
feedback_mode: pairwise
seed_policy: fixed-per-round
steering_mode: low_dimensional
steering_dimension: 5
candidate_count: 3
image_size: 512x512
trust_radius: 0.25
anchor_strength: 0.2
model_name: runwayml/stable-diffusion-v1-5
""",
        },
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["experiment"]["config"]["sampler"] == "exploit_orthogonal"
    assert payload["experiment"]["config"]["updater"] == "linear_preference"
    assert payload["session"]["config"]["feedback_mode"] == "pairwise"
    assert payload["session"]["config"]["steering_dimension"] == 5
    assert payload["session"]["config"]["candidate_count"] == 3


def test_setup_session_endpoint_rejects_invalid_yaml(client) -> None:
    response = client.post(
        "/setup/session",
        json={
            "experiment_name": "Broken YAML setup",
            "description": "",
            "prompt": "Broken config",
            "negative_prompt": "",
            "config_yaml": "sampler: [oops",
        },
    )
    assert response.status_code == 400
    payload = response.json()
    assert payload["error_code"] == "invalid_input"
    assert "Invalid YAML configuration" in payload["message"]


def test_setup_session_endpoint_rejects_unknown_sampler(client) -> None:
    response = client.post(
        "/setup/session",
        json={
            "experiment_name": "Bad sampler",
            "description": "",
            "prompt": "Broken sampler config",
            "negative_prompt": "",
            "config_yaml": """
sampler: definitely_not_real
""",
        },
    )
    assert response.status_code == 400
    payload = response.json()
    assert payload["error_code"] == "invalid_input"
    assert "sampler" in payload["message"]


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
    baseline = round_payload["candidate_metadata"][0]
    assert baseline["sampler_role"] == "baseline_prompt"
    assert baseline["z"] == [0.0, 0.0, 0.0]
    assert baseline["generation_params"]["baseline_prompt"] is True
    assert baseline["generation_params"]["steering_applied"] is False
    exploratory_candidates = round_payload["candidate_metadata"][1:]
    assert exploratory_candidates
    assert all(candidate["generation_params"]["first_round_diversity_boost"] is True for candidate in exploratory_candidates)
    assert all(
        math.sqrt(sum(value * value for value in candidate["z"])) > 0.18 for candidate in exploratory_candidates
    )

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
    round_two_payload = round_two.json()
    assert round_two_payload["state_summary"]["round_index"] == 2
    carried = round_two_payload["candidate_metadata"][0]
    winning_candidate_id = feedback.json()["update_summary"]["winner_candidate_id"]
    previous_winner = next(
        candidate for candidate in round_payload["candidate_metadata"] if candidate["id"] == winning_candidate_id
    )
    assert carried["sampler_role"] == "incumbent"
    assert carried["z"] == previous_winner["z"]
    assert carried["image_path"] == previous_winner["image_path"]
    assert carried["generation_params"]["carried_forward"] is True
    assert carried["generation_params"]["carried_forward_candidate_id"] == previous_winner["id"]
    assert len(round_two_payload["candidate_metadata"]) == 4

    duplicate_feedback = client.post(
        f"/rounds/{round_payload['round_id']}/feedback",
        json={"feedback_type": "scalar_rating", "payload": {"ratings": ratings}},
    )
    assert duplicate_feedback.status_code == 409


def test_session_steering_dimension_comes_from_config(client) -> None:
    experiment = client.post(
        "/experiments",
        json={
            "name": "Dimension test",
            "description": "Steering dimension test",
            "config": {
                "steering_dimension": 5,
                "candidate_count": 4,
            },
        },
    ).json()

    session = client.post(
        "/sessions",
        json={"experiment_id": experiment["id"], "prompt": "A configurable steering vector", "negative_prompt": ""},
    ).json()
    assert session["config"]["steering_dimension"] == 5
    assert session["current_z"] == [0.0, 0.0, 0.0, 0.0, 0.0]

    round_payload = client.post(f"/sessions/{session['id']}/rounds/next").json()
    baseline = round_payload["candidate_metadata"][0]
    assert baseline["z"] == [0.0, 0.0, 0.0, 0.0, 0.0]
    assert all(len(candidate["z"]) == 5 for candidate in round_payload["candidate_metadata"])


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


def test_trace_report_contains_images_and_preferences(client, tmp_path) -> None:
    experiment = client.post(
        "/experiments",
        json={"name": "Trace report", "description": "Trace report test", "config": {"candidate_count": 3}},
    ).json()
    session = client.post(
        "/sessions",
        json={"experiment_id": experiment["id"], "prompt": "A readable trace report", "negative_prompt": "blurry"},
    ).json()
    round_payload = client.post(f"/sessions/{session['id']}/rounds/next").json()
    ratings = {candidate["id"]: 5 - index for index, candidate in enumerate(round_payload["candidate_metadata"])}
    client.post(
        "/frontend-events",
        json={
            "event": "feedback.reviewed",
            "page": f"/sessions/{session['id']}/view",
            "session_id": session["id"],
            "round_id": round_payload["round_id"],
            "details": {"ratings_count": len(ratings)},
        },
    )
    client.post(
        f"/rounds/{round_payload['round_id']}/feedback",
        json={"feedback_type": "scalar_rating", "payload": {"ratings": ratings}, "critique_text": "Prefer the sharper image."},
    )

    report = client.get(f"/sessions/{session['id']}/trace-report")
    assert report.status_code == 200
    assert "StableSteering Run Trace Report" in report.text
    assert "User Preferences" in report.text
    assert "Prefer the sharper image." in report.text
    assert round_payload["candidate_metadata"][0]["id"] in report.text

    report_path = tmp_path / "data" / "traces" / "sessions" / session["id"] / "report.html"
    assert report_path.exists()
    assert round_payload["candidate_metadata"][0]["image_path"] in report_path.read_text(encoding="utf-8")


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


def test_winner_only_feedback_mode_submits_successfully(client) -> None:
    experiment = client.post(
        "/experiments",
        json={
            "name": "Winner only",
            "description": "Winner only test",
            "config": {
                "sampler": "axis_sweep",
                "updater": "winner_copy",
                "feedback_mode": "winner_only",
                "candidate_count": 4,
            },
        },
    ).json()
    session = client.post(
        "/sessions",
        json={"experiment_id": experiment["id"], "prompt": "A sharp studio headphone render", "negative_prompt": ""},
    ).json()
    round_payload = client.post(f"/sessions/{session['id']}/rounds/next").json()
    winner = round_payload["candidate_metadata"][1]["id"]

    feedback = client.post(
        f"/rounds/{round_payload['round_id']}/feedback",
        json={"feedback_type": "winner_only", "payload": {"winner_candidate_id": winner}},
    )
    assert feedback.status_code == 200


def test_approve_reject_feedback_mode_submits_successfully(client) -> None:
    experiment = client.post(
        "/experiments",
        json={
            "name": "Approve reject",
            "description": "Approve reject test",
            "config": {
                "sampler": "incumbent_mix",
                "updater": "linear_preference",
                "feedback_mode": "approve_reject",
                "candidate_count": 5,
            },
        },
    ).json()
    session = client.post(
        "/sessions",
        json={"experiment_id": experiment["id"], "prompt": "A boutique perfume bottle on marble", "negative_prompt": ""},
    ).json()
    round_payload = client.post(f"/sessions/{session['id']}/rounds/next").json()
    candidates = round_payload["candidate_metadata"]

    feedback = client.post(
        f"/rounds/{round_payload['round_id']}/feedback",
        json={
            "feedback_type": "approve_reject",
            "payload": {
                "winner_candidate_id": candidates[2]["id"],
                "approvals": {
                    candidates[0]["id"]: False,
                    candidates[1]["id"]: True,
                    candidates[2]["id"]: True,
                    candidates[3]["id"]: False,
                    candidates[4]["id"]: False,
                },
            },
        },
    )
    assert feedback.status_code == 200


def test_feedback_rejects_unknown_candidate_id(client) -> None:
    experiment = client.post(
        "/experiments",
        json={
            "name": "Invalid feedback",
            "description": "Invalid candidate",
            "config": {"candidate_count": 2, "feedback_mode": "pairwise"},
        },
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


def test_feedback_rejects_mismatched_feedback_mode(client) -> None:
    experiment = client.post(
        "/experiments",
        json={"name": "Mode mismatch", "description": "Wrong feedback type", "config": {"feedback_mode": "winner_only"}},
    ).json()
    session = client.post(
        "/sessions",
        json={"experiment_id": experiment["id"], "prompt": "A clean product render", "negative_prompt": ""},
    ).json()
    round_payload = client.post(f"/sessions/{session['id']}/rounds/next").json()
    candidates = round_payload["candidate_metadata"]

    feedback = client.post(
        f"/rounds/{round_payload['round_id']}/feedback",
        json={
            "feedback_type": "pairwise",
            "payload": {"winner_candidate_id": candidates[0]["id"], "loser_candidate_id": candidates[1]["id"]},
        },
    )
    assert feedback.status_code == 400
    payload = feedback.json()
    assert payload["error_code"] == "invalid_input"
    assert "does not match session mode" in payload["message"]


def test_fixed_per_round_seed_policy_shares_one_seed_across_new_candidates(client) -> None:
    experiment = client.post(
        "/experiments",
        json={
            "name": "Round seed policy",
            "description": "Fixed per round seed test",
            "config": {"candidate_count": 5, "seed_policy": "fixed-per-round"},
        },
    ).json()
    session = client.post(
        "/sessions",
        json={"experiment_id": experiment["id"], "prompt": "A seed policy prompt", "negative_prompt": ""},
    ).json()
    round_payload = client.post(f"/sessions/{session['id']}/rounds/next").json()

    non_baseline = round_payload["candidate_metadata"][1:]
    seeds = {candidate["seed"] for candidate in non_baseline}
    assert len(seeds) == 1
    assert all(candidate["generation_params"]["seed_policy"] == "fixed-per-round" for candidate in non_baseline)
    assert all(candidate["generation_params"]["seed_group"] == "round_shared" for candidate in non_baseline)


def test_fixed_per_candidate_seed_policy_assigns_distinct_seeds(client) -> None:
    experiment = client.post(
        "/experiments",
        json={
            "name": "Candidate seed policy",
            "description": "Fixed per candidate seed test",
            "config": {"candidate_count": 5, "seed_policy": "fixed-per-candidate"},
        },
    ).json()
    session = client.post(
        "/sessions",
        json={"experiment_id": experiment["id"], "prompt": "A seed policy prompt", "negative_prompt": ""},
    ).json()
    round_payload = client.post(f"/sessions/{session['id']}/rounds/next").json()

    candidates = round_payload["candidate_metadata"]
    seeds = [candidate["seed"] for candidate in candidates]
    assert len(set(seeds)) == len(seeds)
    assert candidates[0]["generation_params"]["seed_group"] == "candidate:0"
    assert candidates[1]["generation_params"]["seed_group"] == "candidate:1"
    assert all(candidate["generation_params"]["seed_policy"] == "fixed-per-candidate" for candidate in candidates)


def test_fixed_per_candidate_role_seed_policy_shares_seeds_by_role(client) -> None:
    experiment = client.post(
        "/experiments",
        json={
            "name": "Role seed policy",
            "description": "Fixed per candidate role seed test",
            "config": {
                "sampler": "random_local",
                "candidate_count": 5,
                "seed_policy": "fixed-per-candidate-role",
            },
        },
    ).json()
    session = client.post(
        "/sessions",
        json={"experiment_id": experiment["id"], "prompt": "A seed policy prompt", "negative_prompt": ""},
    ).json()
    round_payload = client.post(f"/sessions/{session['id']}/rounds/next").json()

    candidates = round_payload["candidate_metadata"]
    assert candidates[0]["sampler_role"] == "baseline_prompt"
    explore_candidates = [candidate for candidate in candidates if candidate["sampler_role"] == "explore"]
    assert len(explore_candidates) >= 2
    assert len({candidate["seed"] for candidate in explore_candidates}) == 1
    assert all(candidate["generation_params"]["seed_group"] == "role:explore" for candidate in explore_candidates)

    for left, right in itertools.combinations(candidates, 2):
        if left["sampler_role"] != right["sampler_role"]:
            if left["sampler_role"] == "explore" and right["sampler_role"] == "explore":
                continue
            assert left["seed"] != right["seed"]


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


def test_async_round_job_preflights_conflict_before_queueing(client) -> None:
    experiment = client.post("/experiments", json={"name": "Async round conflict", "config": {"candidate_count": 2}}).json()
    session = client.post(
        "/sessions",
        json={"experiment_id": experiment["id"], "prompt": "An async round prompt", "negative_prompt": ""},
    ).json()
    client.post(f"/sessions/{session['id']}/rounds/next")

    job = client.post(f"/sessions/{session['id']}/rounds/next/async")
    assert job.status_code == 409
    payload = job.json()
    assert payload["error_code"] == "conflict"


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


def test_async_feedback_job_preflights_mode_mismatch(client) -> None:
    experiment = client.post(
        "/experiments",
        json={"name": "Async feedback mismatch", "config": {"candidate_count": 2, "feedback_mode": "winner_only"}},
    ).json()
    session = client.post(
        "/sessions",
        json={"experiment_id": experiment["id"], "prompt": "An async feedback prompt", "negative_prompt": ""},
    ).json()
    round_payload = client.post(f"/sessions/{session['id']}/rounds/next").json()
    candidates = round_payload["candidate_metadata"]

    job = client.post(
        f"/rounds/{round_payload['round_id']}/feedback/async",
        json={
            "feedback_type": "pairwise",
            "payload": {"winner_candidate_id": candidates[0]["id"], "loser_candidate_id": candidates[1]["id"]},
        },
    )
    assert job.status_code == 400
    payload = job.json()
    assert payload["error_code"] == "invalid_input"
