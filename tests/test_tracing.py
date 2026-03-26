from __future__ import annotations

import json
from pathlib import Path


def test_frontend_event_endpoint_persists_trace(client, tmp_path: Path) -> None:
    experiment = client.post("/experiments", json={"name": "Frontend trace", "config": {"candidate_count": 2}}).json()
    session = client.post(
        "/sessions",
        json={"experiment_id": experiment["id"], "prompt": "A setup trace prompt", "negative_prompt": ""},
    ).json()
    response = client.post(
        "/frontend-events",
        json={
            "event": "page.loaded",
            "page": f"/sessions/{session['id']}/view",
            "session_id": session["id"],
            "round_id": None,
            "details": {"view": "session"},
        },
    )
    assert response.status_code == 200
    trace_path = tmp_path / "data" / "traces" / "frontend-events.jsonl"
    assert trace_path.exists()
    lines = trace_path.read_text(encoding="utf-8").strip().splitlines()
    record = json.loads(lines[-1])
    assert record["event"] == "page.loaded"
    assert record["payload"]["page"] == f"/sessions/{session['id']}/view"

    session_trace_path = tmp_path / "data" / "traces" / "sessions" / session["id"] / "frontend-events.jsonl"
    assert session_trace_path.exists()
    session_report_path = tmp_path / "data" / "traces" / "sessions" / session["id"] / "report.html"
    assert session_report_path.exists()
    report_html = session_report_path.read_text(encoding="utf-8")
    assert "StableSteering Run Trace Report" in report_html
    assert session["id"] in report_html


def test_backend_trace_is_written_during_round_generation(client) -> None:
    experiment = client.post("/experiments", json={"name": "Trace test", "config": {"candidate_count": 2}}).json()
    session = client.post("/sessions", json={"experiment_id": experiment["id"], "prompt": "A tracing prompt"}).json()
    response = client.post(f"/sessions/{session['id']}/rounds/next")
    assert response.status_code == 200
