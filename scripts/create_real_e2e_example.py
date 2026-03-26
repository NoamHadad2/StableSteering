from __future__ import annotations

import json
import shutil
from html import escape
from pathlib import Path
from typing import Any

from PIL import Image, ImageFilter, ImageStat

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
            candidate_ids[0]: 2,
            candidate_ids[1]: 5,
            candidate_ids[2]: 4,
            candidate_ids[3]: 3,
            candidate_ids[4]: 1,
        }
        critique = (
            "The unmodified prompt baseline is promising, but candidate 2 has the clearest silhouette, "
            "the strongest sunrise rim light, and the most premium hero-shot composition. "
            "The extra alternatives are useful, but they do not beat the top two."
        )
        return ratings, critique

    if round_index == 2:
        ratings = {
            candidate_ids[0]: 5,
            candidate_ids[1]: 4,
            candidate_ids[2]: 2,
            candidate_ids[3]: 3,
            candidate_ids[4]: 1,
        }
        critique = "Keep the carried-forward winner, but push harder toward cleaner panel detail and a stronger studio-product framing."
        return ratings, critique

    if round_index == 3:
        ratings = {
            candidate_ids[0]: 4,
            candidate_ids[1]: 5,
            candidate_ids[2]: 3,
            candidate_ids[3]: 2,
            candidate_ids[4]: 1,
        }
        critique = "Candidate 2 improves the bodywork and surfacing. It feels more like a premium launch image while staying true to the concept."
        return ratings, critique

    if round_index == 4:
        ratings = {
            candidate_ids[0]: 4,
            candidate_ids[1]: 5,
            candidate_ids[2]: 3,
            candidate_ids[3]: 2,
            candidate_ids[4]: 1,
        }
        critique = "Candidate 2 has the best balance of dramatic lighting and realistic product geometry. Keep that direction for the next phase."
        return ratings, critique

    ratings = {
        candidate_ids[0]: 5,
        candidate_ids[1]: 4,
        candidate_ids[2]: 3,
        candidate_ids[3]: 2,
        candidate_ids[4]: 1,
    }
    critique = "The incumbent now reads like the strongest finished hero image, so preserve it as the final preferred direction."
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


def _average_hash(path: Path, hash_size: int = 8) -> str:
    """Return a small perceptual hash for duplicate-like image detection."""

    with Image.open(path) as image:
        grayscale = image.convert("L").resize((hash_size, hash_size))
        pixels = list(grayscale.getdata())
    mean_value = sum(pixels) / len(pixels)
    return "".join("1" if pixel >= mean_value else "0" for pixel in pixels)


def _visual_metrics(path: Path) -> dict[str, Any]:
    """Compute lightweight visual sanity metrics for one generated image."""

    with Image.open(path) as image:
        rgb = image.convert("RGB")
        grayscale = rgb.convert("L")
        width, height = rgb.size
        stat = ImageStat.Stat(rgb)
        gray_stat = ImageStat.Stat(grayscale)
        edge_image = grayscale.filter(ImageFilter.FIND_EDGES)
        edge_stat = ImageStat.Stat(edge_image)
        entropy = float(grayscale.entropy())
        channel_stddev = sum(stat.stddev) / len(stat.stddev)
        brightness = gray_stat.mean[0]
        edge_mean = edge_stat.mean[0]

    checks = {
        "readable": True,
        "expected_min_size": width >= 384 and height >= 384,
        "non_blank_entropy": entropy >= 4.0,
        "has_contrast": channel_stddev >= 25.0,
        "has_edge_detail": edge_mean >= 12.0,
    }
    passed = sum(1 for value in checks.values() if value)
    return {
        "path": str(path),
        "width": width,
        "height": height,
        "entropy": round(entropy, 3),
        "channel_stddev": round(channel_stddev, 3),
        "brightness_mean": round(brightness, 3),
        "edge_mean": round(edge_mean, 3),
        "hash": _average_hash(path),
        "checks": checks,
        "passed_checks": passed,
        "failed_checks": [name for name, value in checks.items() if not value],
    }


def _evaluate_visual_checks(rounds: list[dict], images_dir: Path, copied_images: dict[str, str]) -> dict[str, Any]:
    """Summarize automated visual checks across the generated sample bundle."""

    image_usage: dict[str, list[str]] = {}
    for candidate_id, relative_path in copied_images.items():
        image_usage.setdefault(relative_path, []).append(candidate_id)

    per_image: list[dict[str, Any]] = []
    for relative_path, candidate_ids in sorted(image_usage.items()):
        metrics = _visual_metrics(images_dir / Path(relative_path).name)
        metrics["relative_path"] = relative_path
        metrics["candidate_ids"] = candidate_ids
        per_image.append(metrics)

    hash_groups: dict[str, list[dict[str, Any]]] = {}
    for item in per_image:
        hash_groups.setdefault(item["hash"], []).append(item)

    duplicate_groups = []
    for hash_value, items in hash_groups.items():
        if len(items) < 2:
            continue
        duplicate_groups.append(
            {
                "hash": hash_value,
                "paths": [item["relative_path"] for item in items],
                "candidate_ids": [candidate_id for item in items for candidate_id in item["candidate_ids"]],
            }
        )

    failing_images = [item for item in per_image if item["failed_checks"]]
    reused_candidates = sum(max(0, len(candidate_ids) - 1) for candidate_ids in image_usage.values())
    return {
        "summary": {
            "round_count": len(rounds),
            "candidate_count": sum(len(round_obj["candidates"]) for round_obj in rounds),
            "unique_image_count": len(per_image),
            "reused_candidate_count": reused_candidates,
            "failing_image_count": len(failing_images),
            "duplicate_image_group_count": len(duplicate_groups),
        },
        "per_image": per_image,
        "failing_images": failing_images,
        "duplicate_groups": duplicate_groups,
    }


def _render_html(
    *,
    session: dict,
    rounds: list[dict],
    diagnostics: dict,
    copied_images: dict[str, str],
    visual_checks: dict[str, Any],
    output_path: Path,
    objective: str,
    success_criteria: list[str],
    demo_script: list[str],
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
        "    .callout { background: #f6efe4; border-left: 4px solid #a55b16; border-radius: 14px; padding: 16px 18px; }",
        "    .columns { display: grid; grid-template-columns: repeat(auto-fit, minmax(280px, 1fr)); gap: 16px; }",
        "    pre { white-space: pre-wrap; word-break: break-word; background: #f7f1e9; border-radius: 14px; padding: 14px; font-size: 0.88rem; }",
        "    table { width: 100%; border-collapse: collapse; }",
        "    th, td { text-align: left; vertical-align: top; padding: 10px; border-top: 1px solid #e7dbce; }",
        "    details.card { padding: 0; overflow: hidden; }",
        "    details.card > summary { list-style: none; cursor: pointer; padding: 22px 24px; font-family: 'Segoe UI', sans-serif; font-weight: 700; }",
        "    details.card > summary::-webkit-details-marker { display: none; }",
        "    details.card > summary::after { content: '+'; float: right; color: #87562a; }",
        "    details.card[open] > summary::after { content: '−'; }",
        "    .card-body { padding: 0 24px 24px; }",
        "  </style>",
        "</head>",
        "<body>",
        "<main>",
        '  <section class="hero">',
        '    <p class="eyebrow">Real GPU Example</p>',
        f"    <h1>{escape(session['prompt'])}</h1>",
        "    <p class=\"lede\">This is a real end-to-end steering run executed against the Diffusers backend on GPU. It is designed to show the core value of the system: starting from a user text prompt, proposing multiple steerable directions, recording preference-guided choices, and moving the session toward a clearer creative target over multiple rounds.</p>",
        '    <div class="metrics">',
        f'      <div class="metric"><strong>Session</strong><span>{escape(session["id"])}</span></div>',
        f'      <div class="metric"><strong>Backend</strong><span>{escape(str(diagnostics.get("backend", "unknown")))}</span></div>',
        f'      <div class="metric"><strong>Device</strong><span>{escape(str(diagnostics.get("active_device") or diagnostics.get("configured_device") or "n/a"))}</span></div>',
        f'      <div class="metric"><strong>CUDA Available</strong><span>{escape(str(diagnostics.get("cuda_available")))}</span></div>',
        f'      <div class="metric"><strong>Rounds</strong><span>{len(rounds)}</span></div>',
        f'      <div class="metric"><strong>Model</strong><span>{escape(session["model_name"])}</span></div>',
        f'      <div class="metric"><strong>Unique images</strong><span>{escape(str(visual_checks["summary"]["unique_image_count"]))}</span></div>',
        "    </div>",
        "  </section>",
        '  <details class="card" open>',
        "    <summary>Demonstration Overview</summary>",
        '    <div class="card-body stack">',
        '      <div class="callout">',
        "      <h2>Demonstration Objective</h2>",
        f"      <p>{escape(objective)}</p>",
        "      </div>",
        '      <div class="columns">',
        "      <div>",
        "        <h3>Success Criteria</h3>",
        "        <ul>",
        *[f"          <li>{escape(item)}</li>" for item in success_criteria],
        "        </ul>",
        "      </div>",
        "      <div>",
        "        <h3>Demo Script</h3>",
        "        <ol>",
        *[f"          <li>{escape(item)}</li>" for item in demo_script],
        "        </ol>",
        "      </div>",
        "    </div>",
        "    </div>",
        "  </details>",
        '  <details class="card" open>',
        "    <summary>Run Setup</summary>",
        '    <div class="card-body stack">',
        "      <div>",
        "      <h2>Run Setup</h2>",
        f"      <p><strong>Prompt:</strong> {escape(session['prompt'])}</p>",
        f"      <p><strong>Negative prompt:</strong> {escape(session.get('negative_prompt') or '(none)')}</p>",
        f"      <p><strong>Sampler:</strong> <code>{escape(session['config']['sampler'])}</code> | <strong>Updater:</strong> <code>{escape(session['config']['updater'])}</code> | <strong>Feedback mode:</strong> <code>{escape(session['config']['feedback_mode'])}</code></p>",
        f"      <p><strong>Output file:</strong> <code>{escape(str(output_path))}</code></p>",
        "      </div>",
        f"      <pre>{escape(json.dumps(diagnostics, indent=2, sort_keys=True))}</pre>",
        "    </div>",
        "  </details>",
        '  <details class="card" open>',
        "    <summary>Automated Visual Checks</summary>",
        '    <div class="card-body stack">',
        "      <div>",
        "      <h2>Automated Visual Checks</h2>",
        "      <p>These checks do not prove semantic correctness, but they do catch common generation failures such as blank-looking outputs, unreadable files, low-detail artifacts, and accidental duplication.</p>",
        "      </div>",
        '      <div class="metrics">',
        f'      <div class="metric"><strong>Unique image files</strong><span>{escape(str(visual_checks["summary"]["unique_image_count"]))}</span></div>',
        f'      <div class="metric"><strong>Reused candidates</strong><span>{escape(str(visual_checks["summary"]["reused_candidate_count"]))}</span></div>',
        f'      <div class="metric"><strong>Flagged images</strong><span>{escape(str(visual_checks["summary"]["failing_image_count"]))}</span></div>',
        f'      <div class="metric"><strong>Duplicate groups</strong><span>{escape(str(visual_checks["summary"]["duplicate_image_group_count"]))}</span></div>',
        "      </div>",
        "      <table>",
        "      <thead><tr><th>Image</th><th>Candidates</th><th>Size</th><th>Entropy</th><th>Contrast</th><th>Edges</th><th>Status</th></tr></thead>",
        "      <tbody>",
        *[
            "      <tr>"
            f"<td><code>{escape(item['relative_path'])}</code></td>"
            f"<td>{escape(', '.join(item['candidate_ids']))}</td>"
            f"<td>{escape(str(item['width']))}x{escape(str(item['height']))}</td>"
            f"<td>{escape(str(item['entropy']))}</td>"
            f"<td>{escape(str(item['channel_stddev']))}</td>"
            f"<td>{escape(str(item['edge_mean']))}</td>"
            f"<td>{escape('ok' if not item['failed_checks'] else 'flagged: ' + ', '.join(item['failed_checks']))}</td>"
            "</tr>"
            for item in visual_checks["per_image"]
        ],
        "      </tbody>",
        "    </table>",
        (
            f"      <pre>{escape(json.dumps(visual_checks, indent=2, sort_keys=True))}</pre>"
            if visual_checks["failing_images"] or visual_checks["duplicate_groups"]
            else "      <p>All automated visual sanity checks passed for the unique generated images in this bundle.</p>"
        ),
        "    </div>",
        "  </details>",
    ]

    for round_obj in rounds:
        feedback = round_obj["feedback_events"][0] if round_obj["feedback_events"] else None
        winner_id = round_obj.get("update_summary", {}).get("winner_candidate_id")
        sections.extend(
            [
                '  <details class="card round">',
                f"    <summary>Phase {round_obj['round_index']}: propose, inspect, choose, update</summary>",
                '    <div class="card-body">',
                f"    <p class=\"eyebrow\">Round {round_obj['round_index']}</p>",
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
        sections.extend(["    </div>", "  </details>"])

    sections.extend(
        [
            '  <details class="card" open>',
            "    <summary>Outcome</summary>",
            '    <div class="card-body">',
            "    <h2>Outcome</h2>",
            f"    <p>The session ended at round <strong>{len(rounds)}</strong> with incumbent candidate <code>{escape(str(session.get('incumbent_candidate_id') or 'n/a'))}</code>.</p>",
            "    <p>This report demonstrates system value by showing that the workflow does not stop at one prompt and one image. It keeps the user in a controlled compare-select-update loop with visible evidence for what was proposed, what was preferred, and how the next state was chosen.</p>",
            f"    <p>Backend session traces and the auto-generated audit report also exist under <code>{escape(str((output_path.parent / 'data' / 'traces').resolve()))}</code>.</p>",
            "    </div>",
            "  </details>",
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
        num_inference_steps=30,
    )
    orchestrator = Orchestrator(repository=repository, generator=generator)

    experiment = orchestrator.create_experiment(
        ExperimentCreate(
            name="Premium product hero image demo",
            description="A scripted user steering walkthrough that demonstrates creative refinement on the real Diffusers backend.",
            config=StrategyConfig(
                candidate_count=5,
                image_size="512x512",
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
            prompt="A premium cinematic product hero photo of an expedition-ready electric explorer motorcycle, photographed in a desert sunrise studio set with brushed titanium surfaces, crisp rim lighting, and magazine-cover composition",
            negative_prompt="blurry, low contrast, flat lighting, distorted wheels, text, watermark, cluttered background, cropped subject",
        )
    )
    objective = (
        "Demonstrate that StableSteering can start from a rich user text prompt and then guide image generation "
        "toward a sharper, more premium product-marketing result through iterative user preferences rather than one-shot prompting."
    )
    success_criteria = [
        "The first round should include the unmodified-prompt baseline plus clearly different on-theme alternatives.",
        "Later rounds should preserve the previous winner while still exploring nearby alternatives.",
        "User preference should steer the session toward stronger silhouette, lighting, and premium material detail.",
        "By round five, the session should look more aligned with the desired hero-shot direction than the initial round.",
        "The report should make the proposal, selection, and update logic easy to inspect after the run.",
    ]
    demo_script = [
        "Start from a user-written product prompt rather than a hidden preset.",
        "Generate a first comparison round and inspect the baseline prompt render beside two steered alternatives.",
        "Choose the candidate with the strongest hero-shot silhouette and lighting.",
        "Generate additional rounds that keep the previous winner visible while exploring nearby refinements.",
        "Continue for five rounds so the session history shows convergence instead of a one-step jump.",
        "Review the report to see the proposed images, critiques, and incumbent transitions together.",
    ]

    trace_recorder = orchestrator.trace_recorder
    _frontend_event(trace_recorder, "page.loaded", page="/setup", session_id=session.id, details={"view": "setup"})
    _frontend_event(trace_recorder, "session.created", page=f"/sessions/{session.id}/view", session_id=session.id, details={"prompt": session.prompt})

    round_payloads: list[dict] = []
    copied_images: dict[str, str] = {}

    for round_index in range(1, 6):
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
    visual_checks = _evaluate_visual_checks(rounds, images_dir, copied_images)

    html_path = bundle_root / "real_e2e_example_run.html"
    html_path.write_text(
        _render_html(
            session=session_summary.model_dump(mode="json"),
            rounds=rounds,
            diagnostics=generator.diagnostics(),
            copied_images=copied_images,
            visual_checks=visual_checks,
            output_path=html_path.resolve(),
            objective=objective,
            success_criteria=success_criteria,
            demo_script=demo_script,
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
        "objective": objective,
        "round_count": len(rounds),
        "candidate_count": sum(len(round_obj["candidates"]) for round_obj in rounds),
        "backend": generator.diagnostics(),
        "visual_checks": visual_checks,
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
