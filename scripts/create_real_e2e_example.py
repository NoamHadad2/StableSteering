from __future__ import annotations

import json
import shutil
from html import escape
from pathlib import Path

from app.core.schema import ExperimentCreate, FeedbackRequest, SessionCreate, StrategyConfig
from app.engine.generation import build_generation_engine
from app.engine.orchestrator import Orchestrator
from app.storage.repository import JsonRepository


def _copy_artifact(image_url: str, artifacts_dir: Path, images_dir: Path) -> str:
    """Copy one generated artifact into the portable example bundle."""

    filename = Path(image_url).name
    source = artifacts_dir / filename
    target = images_dir / filename
    shutil.copy2(source, target)
    return f"images/{filename}"


def _pick_feedback(round_payload: dict, round_index: int) -> tuple[dict[str, int], str]:
    """Return deterministic user ratings and a short critique for one round."""

    candidate_ids = [candidate["id"] for candidate in round_payload["candidate_metadata"]]
    if round_index == 1:
        ratings = {
            candidate_ids[0]: 3,
            candidate_ids[1]: 5,
            candidate_ids[2]: 4,
        }
        critique = "Candidate 2 has the clearest silhouette and the strongest cinematic lighting."
        return ratings, critique

    ratings = {
        candidate_ids[0]: 5,
        candidate_ids[1]: 4,
        candidate_ids[2]: 2,
    }
    critique = "Candidate 1 pushes the metallic detail and composition closer to the target look."
    return ratings, critique


def _frontend_event(trace_recorder, event: str, *, page: str, session_id: str, round_id: str | None = None, details: dict | None = None) -> None:
    """Append one synthetic frontend event for the scripted example flow."""

    trace_recorder.append_frontend(
        event,
        {
            "page": page,
            "session_id": session_id,
            "round_id": round_id,
            "details": details or {},
        },
    )


def _render_html(
    *,
    session: dict,
    rounds: list[dict],
    diagnostics: dict,
    copied_images: dict[str, str],
    output_path: Path,
) -> str:
    """Render a standalone HTML walkthrough of the real example run."""

    sections: list[str] = [
        "<!doctype html>",
        '<html lang="en">',
        "<head>",
        '  <meta charset="utf-8">',
        '  <meta name="viewport" content="width=device-width, initial-scale=1">',
        f"  <title>Real E2E Example Run {escape(session['id'])}</title>",
        "  <style>",
        "    :root { color-scheme: light; font-family: Georgia, 'Times New Roman', serif; }",
        "    body { margin: 0; background: linear-gradient(180deg, #f1e8dc 0%, #fcfaf6 100%); color: #231b15; }",
        "    main { max-width: 1180px; margin: 0 auto; padding: 32px 20px 48px; }",
        "    .hero, .card { background: rgba(255, 252, 247, 0.96); border: 1px solid #d7ccbf; border-radius: 20px; padding: 24px; box-shadow: 0 14px 38px rgba(74, 50, 23, 0.08); }",
        "    .hero { margin-bottom: 18px; }",
        "    .eyebrow { text-transform: uppercase; letter-spacing: 0.12em; color: #87562a; font-size: 0.82rem; margin: 0 0 8px; }",
        "    h1, h2, h3 { margin-top: 0; font-family: 'Segoe UI', sans-serif; }",
        "    .lede { font-size: 1.08rem; line-height: 1.65; max-width: 900px; }",
        "    .metrics { display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 12px; margin-top: 18px; }",
        "    .metric { background: #f8f1e7; border-radius: 16px; padding: 14px; }",
        "    .metric strong { display: block; font-family: 'Segoe UI', sans-serif; font-size: 0.82rem; text-transform: uppercase; letter-spacing: 0.08em; color: #765434; margin-bottom: 6px; }",
        "    .metric span { font-size: 1.02rem; font-weight: 700; }",
        "    .stack { display: grid; gap: 18px; }",
        "    .round { margin-top: 18px; }",
        "    .candidate-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 16px; }",
        "    .candidate { background: #fff; border-radius: 16px; overflow: hidden; border: 1px solid #e5d9cb; }",
        "    .candidate img { width: 100%; aspect-ratio: 1 / 1; object-fit: cover; display: block; background: #e9e0d4; }",
        "    .candidate .body { padding: 12px; font-size: 0.94rem; line-height: 1.45; }",
        "    .winner { outline: 3px solid #b16d1e; }",
        "    .pill { display: inline-block; margin-right: 8px; margin-bottom: 8px; padding: 6px 10px; background: #efe2cf; border-radius: 999px; font-size: 0.84rem; }",
        "    pre { white-space: pre-wrap; word-break: break-word; background: #f7f1e9; border-radius: 14px; padding: 14px; font-size: 0.88rem; }",
        "    table { width: 100%; border-collapse: collapse; }",
        "    th, td { text-align: left; vertical-align: top; padding: 10px; border-top: 1px solid #e7dbce; }",
        "  </style>",
        "</head>",
        "<body>",
        "<main>",
        '  <section class="hero">',
        '    <p class="eyebrow">Real GPU Example</p>',
        f"    <h1>{escape(session['prompt'])}</h1>",
        "    <p class=\"lede\">This is a real end-to-end steering run executed against the Diffusers backend on GPU. It records the generated proposals, the simulated user steering choices, and the updated system state after each feedback phase.</p>",
        '    <div class="metrics">',
        f'      <div class="metric"><strong>Session</strong><span>{escape(session["id"])}</span></div>',
        f'      <div class="metric"><strong>Backend</strong><span>{escape(str(diagnostics.get("backend", "unknown")))}</span></div>',
        f'      <div class="metric"><strong>Device</strong><span>{escape(str(diagnostics.get("active_device") or diagnostics.get("configured_device") or "n/a"))}</span></div>',
        f'      <div class="metric"><strong>CUDA Available</strong><span>{escape(str(diagnostics.get("cuda_available")))}</span></div>',
        f'      <div class="metric"><strong>Rounds</strong><span>{len(rounds)}</span></div>',
        f'      <div class="metric"><strong>Model</strong><span>{escape(session["model_name"])}</span></div>',
        "    </div>",
        "  </section>",
        '  <section class="card stack">',
        "    <div>",
        "      <h2>Run Setup</h2>",
        f"      <p><strong>Prompt:</strong> {escape(session['prompt'])}</p>",
        f"      <p><strong>Negative prompt:</strong> {escape(session.get('negative_prompt') or '(none)')}</p>",
        f"      <p><strong>Sampler:</strong> <code>{escape(session['config']['sampler'])}</code> | <strong>Updater:</strong> <code>{escape(session['config']['updater'])}</code> | <strong>Feedback mode:</strong> <code>{escape(session['config']['feedback_mode'])}</code></p>",
        f"      <p><strong>Output file:</strong> <code>{escape(str(output_path))}</code></p>",
        "    </div>",
        f"    <pre>{escape(json.dumps(diagnostics, indent=2, sort_keys=True))}</pre>",
        "  </section>",
    ]

    for round_obj in rounds:
        feedback = round_obj["feedback_events"][0] if round_obj["feedback_events"] else None
        winner_id = round_obj.get("update_summary", {}).get("winner_candidate_id")
        sections.extend(
            [
                '  <section class="card round">',
                f"    <p class=\"eyebrow\">Round {round_obj['round_index']}</p>",
                f"    <h2>Phase {round_obj['round_index']}: propose, inspect, choose, update</h2>",
                f"    <p><span class=\"pill\">Round id: {escape(round_obj['id'])}</span><span class=\"pill\">Latency: {escape(str(round_obj.get('latency_ms', 0)))} ms</span><span class=\"pill\">Incumbent z before update: {escape(json.dumps(round_obj.get('incumbent_z', [])))}</span></p>",
                '    <div class="candidate-grid">',
            ]
        )
        for candidate in round_obj["candidates"]:
            winner_class = " candidate winner" if candidate["id"] == winner_id else " candidate"
            sections.extend(
                [
                    f'      <article class="{winner_class.strip()}">',
                    f'        <img src="{escape(copied_images[candidate["id"]])}" alt="{escape(candidate["id"])}">',
                    '        <div class="body">',
                    f'          <p><strong>{escape(candidate["id"])}</strong></p>',
                    f'          <p>Role: {escape(candidate["sampler_role"])}</p>',
                    f'          <p>Seed: {escape(str(candidate["seed"]))}</p>',
                    f'          <p>z: <code>{escape(json.dumps(candidate["z"]))}</code></p>',
                ]
            )
            if feedback and "ratings" in feedback["payload"]:
                rating = feedback["payload"]["ratings"].get(candidate["id"])
                sections.append(f"          <p>User rating: <strong>{escape(str(rating))}</strong></p>")
            if candidate["id"] == winner_id:
                sections.append("          <p><strong>Selected as winner for the next phase.</strong></p>")
            sections.extend(
                [
                    "        </div>",
                    "      </article>",
                ]
            )
        sections.append("    </div>")
        if feedback:
            sections.extend(
                [
                    "    <h3>User Action</h3>",
                    f"    <p>{escape(feedback.get('critique_text') or '(no critique)')}</p>",
                    f"    <pre>{escape(json.dumps(feedback['normalized_payload'], indent=2, sort_keys=True))}</pre>",
                ]
            )
        if round_obj.get("update_summary"):
            sections.extend(
                [
                    "    <h3>Next Phase State</h3>",
                    f"    <pre>{escape(json.dumps(round_obj['update_summary'], indent=2, sort_keys=True))}</pre>",
                ]
            )
        sections.append("  </section>")

    sections.extend(
        [
            '  <section class="card">',
            "    <h2>Outcome</h2>",
            f"    <p>The session ended at round <strong>{len(rounds)}</strong> with incumbent candidate <code>{escape(str(session.get('incumbent_candidate_id') or 'n/a'))}</code>.</p>",
            f"    <p>Backend session traces and the auto-generated audit report also exist under <code>{escape(str((output_path.parent / 'data' / 'traces').resolve()))}</code>.</p>",
            "  </section>",
            "</main>",
            "</body>",
            "</html>",
        ]
    )
    return "\n".join(sections)


def main() -> int:
    """Execute a real GPU-backed example session and export a readable HTML artifact."""

    try:
        import torch
    except ImportError as exc:
        raise RuntimeError("PyTorch is required for the real end-to-end example run.") from exc

    if not torch.cuda.is_available():
        raise RuntimeError(
            "The real end-to-end example run requires a CUDA-capable GPU. "
            "This script does not fall back to the mock backend."
        )

    bundle_root = Path("output") / "examples" / "real_e2e_example_run"
    images_dir = bundle_root / "images"
    if bundle_root.exists():
        shutil.rmtree(bundle_root)
    images_dir.mkdir(parents=True, exist_ok=True)

    repository = JsonRepository(bundle_root / "data")
    generator = build_generation_engine(
        backend="diffusers",
        model_id="runwayml/stable-diffusion-v1-5",
        models_root=Path("models"),
        artifacts_dir=bundle_root / "data" / "artifacts",
    )
    orchestrator = Orchestrator(repository=repository, generator=generator)

    experiment = orchestrator.create_experiment(
        ExperimentCreate(
            name="Real E2E example run",
            description="A scripted user steering walkthrough on the real Diffusers backend.",
            config=StrategyConfig(
                candidate_count=3,
                image_size="256x256",
                sampler="random_local",
                updater="winner_average",
                feedback_mode="scalar_rating",
                model_name="runwayml/stable-diffusion-v1-5",
            ),
        )
    )
    session = orchestrator.create_session(
        SessionCreate(
            experiment_id=experiment.id,
            prompt="A cinematic studio product photo of a retro-futuristic bronze exploration rover",
            negative_prompt="blurry, low contrast, distorted wheels, text, watermark",
        )
    )

    trace_recorder = orchestrator.trace_recorder
    _frontend_event(trace_recorder, "page.loaded", page="/setup", session_id=session.id, details={"view": "setup"})
    _frontend_event(trace_recorder, "session.created", page=f"/sessions/{session.id}/view", session_id=session.id, details={"prompt": session.prompt})

    round_payloads: list[dict] = []
    copied_images: dict[str, str] = {}

    for round_index in (1, 2):
        _frontend_event(
            trace_recorder,
            "round.generate.clicked",
            page=f"/sessions/{session.id}/view",
            session_id=session.id,
            details={"round_index": round_index},
        )
        round_response = orchestrator.generate_round(session.id).model_dump(mode="json")
        round_payloads.append(round_response)
        _frontend_event(
            trace_recorder,
            "round.visible",
            page=f"/sessions/{session.id}/view",
            session_id=session.id,
            round_id=round_response["round_id"],
            details={"candidate_count": len(round_response["candidate_metadata"])},
        )

        ratings, critique = _pick_feedback(round_response, round_index)
        _frontend_event(
            trace_recorder,
            "feedback.submit.clicked",
            page=f"/sessions/{session.id}/view",
            session_id=session.id,
            round_id=round_response["round_id"],
            details={"ratings": ratings, "critique_text": critique},
        )
        orchestrator.submit_feedback(
            round_response["round_id"],
            FeedbackRequest(
                feedback_type="scalar_rating",
                payload={"ratings": ratings},
                critique_text=critique,
            ),
        )

    session_summary = orchestrator.get_session(session.id)
    rounds = [round_obj.model_dump(mode="json") for round_obj in orchestrator.get_session_rounds(session.id)]
    for round_obj in rounds:
        for candidate in round_obj["candidates"]:
            copied_images[candidate["id"]] = _copy_artifact(
                candidate["image_path"],
                bundle_root / "data" / "artifacts",
                images_dir,
            )

    html_path = bundle_root / "real_e2e_example_run.html"
    html_path.write_text(
        _render_html(
            session=session_summary.model_dump(mode="json"),
            rounds=rounds,
            diagnostics=generator.diagnostics(),
            copied_images=copied_images,
            output_path=html_path.resolve(),
        ),
        encoding="utf-8",
    )

    trace_report_path = orchestrator.generate_trace_report(session.id)
    portable_trace_report = bundle_root / "session_trace_report.html"
    shutil.copy2(trace_report_path, portable_trace_report)

    manifest = {
        "session_id": session.id,
        "experiment_id": experiment.id,
        "html_report": str(html_path.resolve()),
        "trace_report": str(portable_trace_report.resolve()),
        "bundle_root": str(bundle_root.resolve()),
        "round_count": len(rounds),
        "candidate_count": sum(len(round_obj["candidates"]) for round_obj in rounds),
        "backend": generator.diagnostics(),
    }
    (bundle_root / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    print("Real end-to-end example run completed:")
    print(f"  session_id: {session.id}")
    print(f"  html_report: {html_path.resolve()}")
    print(f"  trace_report: {portable_trace_report.resolve()}")
    print(f"  manifest: {(bundle_root / 'manifest.json').resolve()}")
    print(f"  rounds: {len(rounds)}")
    print(f"  images: {sum(len(round_obj['candidates']) for round_obj in rounds)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
