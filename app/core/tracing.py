from __future__ import annotations

import html
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.core.config import settings


def utc_timestamp() -> str:
    """Return an ISO-8601 UTC timestamp for trace events."""

    return datetime.now(timezone.utc).isoformat()


class TraceRecorder:
    """Persist trace events and readable per-session HTML reports."""

    def __init__(self, trace_dir: Path | None = None) -> None:
        self.trace_dir = trace_dir or settings.traces_dir
        self.trace_dir.mkdir(parents=True, exist_ok=True)
        self.sessions_dir = self.trace_dir / "sessions"
        self.sessions_dir.mkdir(parents=True, exist_ok=True)
        self.backend_path = self.trace_dir / "backend-events.jsonl"
        self.frontend_path = self.trace_dir / "frontend-events.jsonl"

    def append_backend(self, event: str, payload: dict[str, Any]) -> None:
        """Append one backend event to the shared backend trace stream."""

        record = self._build_record(event, payload)
        self._append_record(self.backend_path, record)
        self._append_session_record("backend-events.jsonl", payload.get("session_id"), record)

    def append_frontend(self, event: str, payload: dict[str, Any]) -> None:
        """Append one frontend event to the shared frontend trace stream."""

        record = self._build_record(event, payload)
        self._append_record(self.frontend_path, record)
        self._append_session_record("frontend-events.jsonl", payload.get("session_id"), record)

    def load_session_backend_events(self, session_id: str) -> list[dict[str, Any]]:
        """Load backend events previously recorded for one session."""

        return self._read_jsonl(self.session_dir(session_id) / "backend-events.jsonl")

    def load_session_frontend_events(self, session_id: str) -> list[dict[str, Any]]:
        """Load frontend events previously recorded for one session."""

        return self._read_jsonl(self.session_dir(session_id) / "frontend-events.jsonl")

    def session_dir(self, session_id: str) -> Path:
        """Return the filesystem directory for one session trace bundle."""

        path = self.sessions_dir / session_id
        path.mkdir(parents=True, exist_ok=True)
        return path

    def session_report_path(self, session_id: str) -> Path:
        """Return the HTML report path for one session trace bundle."""

        return self.session_dir(session_id) / "report.html"

    def write_session_report(
        self,
        *,
        session: dict[str, Any],
        experiment: dict[str, Any] | None,
        rounds: list[dict[str, Any]],
        backend_events: list[dict[str, Any]],
        frontend_events: list[dict[str, Any]],
        diagnostics: dict[str, Any],
    ) -> Path:
        """Write a readable HTML report that summarizes one session run."""

        report_path = self.session_report_path(session["id"])
        report_path.write_text(
            self._render_session_report(
                session=session,
                experiment=experiment,
                rounds=rounds,
                backend_events=backend_events,
                frontend_events=frontend_events,
                diagnostics=diagnostics,
            ),
            encoding="utf-8",
        )
        return report_path

    def _build_record(self, event: str, payload: dict[str, Any]) -> dict[str, Any]:
        return {"timestamp": utc_timestamp(), "event": event, "payload": payload}

    def _append_record(self, path: Path, record: dict[str, Any]) -> None:
        with path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record) + "\n")

    def _append_session_record(self, name: str, session_id: str | None, record: dict[str, Any]) -> None:
        if not session_id:
            return
        self._append_record(self.session_dir(session_id) / name, record)

    def _read_jsonl(self, path: Path) -> list[dict[str, Any]]:
        if not path.exists():
            return []
        return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]

    def _render_session_report(
        self,
        *,
        session: dict[str, Any],
        experiment: dict[str, Any] | None,
        rounds: list[dict[str, Any]],
        backend_events: list[dict[str, Any]],
        frontend_events: list[dict[str, Any]],
        diagnostics: dict[str, Any],
    ) -> str:
        generated_at = utc_timestamp()
        combined_events = sorted(
            [
                *[{"source": "backend", **event} for event in backend_events],
                *[{"source": "frontend", **event} for event in frontend_events],
            ],
            key=lambda event: event.get("timestamp", ""),
        )
        round_count = len(rounds)
        candidate_count = sum(len(round_obj.get("candidates", [])) for round_obj in rounds)
        feedback_count = sum(len(round_obj.get("feedback_events", [])) for round_obj in rounds)
        experiment_name = experiment.get("name") if experiment else "Ad hoc"
        backend_rel = Path("backend-events.jsonl")
        frontend_rel = Path("frontend-events.jsonl")
        report_name = report_path_name(self.session_report_path(session["id"]))

        html_parts = [
            "<!doctype html>",
            '<html lang="en">',
            "<head>",
            '  <meta charset="utf-8">',
            '  <meta name="viewport" content="width=device-width, initial-scale=1">',
            f"  <title>Trace Report {self._escape(session['id'])}</title>",
            "  <style>",
            "    :root { color-scheme: light; font-family: 'Segoe UI', system-ui, sans-serif; }",
            "    body { margin: 0; background: #f5efe5; color: #1f1b16; }",
            "    main { max-width: 1100px; margin: 0 auto; padding: 24px; }",
            "    .hero, .card { background: #fffdf8; border: 1px solid #d7cfc2; border-radius: 18px; padding: 20px; box-shadow: 0 10px 30px rgba(56, 44, 22, 0.08); }",
            "    .hero { margin-bottom: 18px; }",
            "    .grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(190px, 1fr)); gap: 12px; margin: 16px 0 0; }",
            "    .metric { background: #f8f3ea; border-radius: 14px; padding: 14px; }",
            "    .metric h3 { margin: 0 0 8px; font-size: 0.82rem; text-transform: uppercase; letter-spacing: 0.08em; color: #705a3d; }",
            "    .metric p { margin: 0; font-size: 1.05rem; font-weight: 700; }",
            "    .section { margin-top: 18px; }",
            "    .section h2 { margin: 0 0 12px; }",
            "    .round { margin-top: 16px; }",
            "    .candidate-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 14px; }",
            "    .candidate { border: 1px solid #e6dccf; border-radius: 14px; background: #fff; overflow: hidden; }",
            "    .candidate img { width: 100%; aspect-ratio: 1 / 1; object-fit: cover; display: block; background: #eee5d9; }",
            "    .candidate .body { padding: 12px; }",
            "    .kv { margin: 0; font-size: 0.92rem; line-height: 1.45; }",
            "    .pill { display: inline-block; margin-right: 8px; margin-bottom: 8px; padding: 6px 10px; border-radius: 999px; background: #efe4d2; color: #5e4b31; font-size: 0.85rem; }",
            "    .events { width: 100%; border-collapse: collapse; }",
            "    .events th, .events td { text-align: left; padding: 10px; border-top: 1px solid #e7ddcf; vertical-align: top; }",
            "    pre { margin: 0; white-space: pre-wrap; word-break: break-word; background: #f7f2ea; border-radius: 12px; padding: 12px; }",
            "    a { color: #7a3f13; }",
            "  </style>",
            "</head>",
            "<body>",
            "<main>",
            '  <section class="hero">',
            "    <p>StableSteering Run Trace Report</p>",
            f"    <h1>{self._escape(session['prompt'])}</h1>",
            f"    <p>Session <code>{self._escape(session['id'])}</code> from experiment <strong>{self._escape(experiment_name)}</strong>.</p>",
            f"    <p>Generated at {self._escape(generated_at)}. Stored in <code>{self._escape(report_name)}</code>.</p>",
            '    <div class="grid">',
            f'      <div class="metric"><h3>Status</h3><p>{self._escape(str(session.get("status", "unknown")))}</p></div>',
            f'      <div class="metric"><h3>Rounds</h3><p>{round_count}</p></div>',
            f'      <div class="metric"><h3>Images Proposed</h3><p>{candidate_count}</p></div>',
            f'      <div class="metric"><h3>Feedback Events</h3><p>{feedback_count}</p></div>',
            f'      <div class="metric"><h3>Backend</h3><p>{self._escape(str(diagnostics.get("backend", "unknown")))}</p></div>',
            f'      <div class="metric"><h3>Active Device</h3><p>{self._escape(str(diagnostics.get("active_device") or diagnostics.get("configured_device") or "n/a"))}</p></div>',
            "    </div>",
            "  </section>",
            '  <section class="card section">',
            "    <h2>Artifacts</h2>",
            f"    <p>Backend event log: <code>{self._escape(str(backend_rel))}</code></p>",
            f"    <p>Frontend event log: <code>{self._escape(str(frontend_rel))}</code></p>",
            "  </section>",
            '  <section class="card section">',
            "    <h2>Runtime Diagnostics</h2>",
            f"    <pre>{self._escape(json.dumps(diagnostics, indent=2, sort_keys=True))}</pre>",
            "  </section>",
            '  <section class="card section">',
            "    <h2>Run Summary</h2>",
            f"    <p><strong>Negative prompt:</strong> {self._escape(session.get('negative_prompt') or '(none)')}</p>",
            f"    <p><strong>Model:</strong> <code>{self._escape(session.get('model_name', 'unknown'))}</code></p>",
            f"    <p><strong>Feedback mode:</strong> <code>{self._escape(str(session.get('config', {}).get('feedback_mode', 'unknown')))}</code></p>",
            f"    <p><strong>Sampler:</strong> <code>{self._escape(str(session.get('config', {}).get('sampler', 'unknown')))}</code></p>",
            f"    <p><strong>Updater:</strong> <code>{self._escape(str(session.get('config', {}).get('updater', 'unknown')))}</code></p>",
            "  </section>",
        ]

        for round_obj in rounds:
            html_parts.extend(
                [
                    '  <section class="card section round">',
                    f"    <h2>Round {round_obj.get('round_index')}</h2>",
                    f'    <span class="pill">Round id: {self._escape(round_obj.get("id", ""))}</span>',
                    f'    <span class="pill">Render status: {self._escape(str(round_obj.get("render_status", "unknown")))}</span>',
                    f'    <span class="pill">Latency: {self._escape(str(round_obj.get("latency_ms", 0)))} ms</span>',
                    '    <div class="candidate-grid">',
                ]
            )
            for candidate in round_obj.get("candidates", []):
                html_parts.extend(
                    [
                        '      <article class="candidate">',
                        f'        <img src="{self._escape(candidate.get("image_path") or "")}" alt="Candidate {self._escape(str(candidate.get("candidate_index", "?")))}">',
                        '        <div class="body">',
                        f'          <p class="kv"><strong>{self._escape(candidate.get("id", ""))}</strong></p>',
                        f'          <p class="kv">Role: {self._escape(str(candidate.get("sampler_role", "unknown")))}</p>',
                        f'          <p class="kv">Seed: {self._escape(str(candidate.get("seed", "unknown")))}</p>',
                        f'          <p class="kv">z: <code>{self._escape(json.dumps(candidate.get("z", [])))}</code></p>',
                        f'          <p class="kv">Predicted score: {self._escape(str(candidate.get("predicted_score")))}</p>',
                        f'          <p class="kv">Predicted uncertainty: {self._escape(str(candidate.get("predicted_uncertainty")))}</p>',
                        "        </div>",
                        "      </article>",
                    ]
                )
            html_parts.append("    </div>")
            if round_obj.get("feedback_events"):
                html_parts.append("    <h3>User Preferences</h3>")
                for feedback in round_obj["feedback_events"]:
                    html_parts.extend(
                        [
                            f'    <p class="kv"><strong>{self._escape(str(feedback.get("type", "unknown")))}</strong> at {self._escape(str(feedback.get("created_at", "")))}</p>',
                            f"    <pre>{self._escape(json.dumps(feedback.get('normalized_payload', {}), indent=2, sort_keys=True))}</pre>",
                        ]
                    )
                    if feedback.get("critique_text"):
                        html_parts.append(f"    <p><strong>Critique:</strong> {self._escape(feedback['critique_text'])}</p>")
            if round_obj.get("update_summary"):
                html_parts.append("    <h3>Update Summary</h3>")
                html_parts.append(
                    f"    <pre>{self._escape(json.dumps(round_obj.get('update_summary', {}), indent=2, sort_keys=True))}</pre>"
                )
            html_parts.append("  </section>")

        html_parts.extend(
            [
                '  <section class="card section">',
                "    <h2>Event Timeline</h2>",
                '    <table class="events">',
                "      <thead><tr><th>Time</th><th>Source</th><th>Event</th><th>Details</th></tr></thead>",
                "      <tbody>",
            ]
        )
        for event in combined_events:
            html_parts.extend(
                [
                    "        <tr>",
                    f"          <td>{self._escape(str(event.get('timestamp', '')))}</td>",
                    f"          <td>{self._escape(str(event.get('source', 'unknown')))}</td>",
                    f"          <td><code>{self._escape(str(event.get('event', 'unknown')))}</code></td>",
                    f"          <td><pre>{self._escape(json.dumps(event.get('payload', {}), indent=2, sort_keys=True))}</pre></td>",
                    "        </tr>",
                ]
            )
        if not combined_events:
            html_parts.append('        <tr><td colspan="4">No session-scoped trace events recorded yet.</td></tr>')
        html_parts.extend(
            [
                "      </tbody>",
                "    </table>",
                "  </section>",
                "</main>",
                "</body>",
                "</html>",
            ]
        )
        return "\n".join(html_parts)

    @staticmethod
    def _escape(value: Any) -> str:
        return html.escape("" if value is None else str(value))


def report_path_name(report_path: Path) -> str:
    """Return a small display path for one report file."""

    return report_path.name
