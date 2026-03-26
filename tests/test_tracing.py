from __future__ import annotations

import json
from pathlib import Path


def test_frontend_event_endpoint_persists_trace(client, tmp_path: Path) -> None:
    response = client.post(
        "/frontend-events",
        json={
            "event": "page.loaded",
            "page": "/setup",
            "session_id": None,
            "round_id": None,
            "details": {"view": "setup"},
        },
    )
    assert response.status_code == 200
    trace_path = tmp_path / "data" / "traces" / "frontend-events.jsonl"
    assert trace_path.exists()
    lines = trace_path.read_text(encoding="utf-8").strip().splitlines()
    record = json.loads(lines[-1])
    assert record["event"] == "page.loaded"
    assert record["payload"]["page"] == "/setup"


def test_backend_trace_is_written_during_round_generation(client) -> None:
    experiment = client.post("/experiments", json={"name": "Trace test", "config": {"candidate_count": 2}}).json()
    session = client.post("/sessions", json={"experiment_id": experiment["id"], "prompt": "A tracing prompt"}).json()
    response = client.post(f"/sessions/{session['id']}/rounds/next")
    assert response.status_code == 200
