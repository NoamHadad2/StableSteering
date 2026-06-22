from __future__ import annotations

import json
import re
import shutil
from html import escape
from pathlib import Path

from app.core.schema import ExperimentCreate, FeedbackRequest, SessionCreate, StrategyConfig
from app.engine.generation import build_generation_engine
from app.engine.orchestrator import Orchestrator
from app.storage.repository import JsonRepository


CONFIGURATIONS = [
    {
        "slug": "random_scalar",
        "title": "Random local + scalar ratings",
        "config": StrategyConfig(
            sampler="random_local",
            updater="winner_average",
            feedback_mode="scalar_rating",
            candidate_count=5,
            image_size="512x512",
            trust_radius=0.35,
            model_name="runwayml/stable-diffusion-v1-5",
        ),
    },
    {
        "slug": "orthogonal_pairwise",
        "title": "Exploit/orthogonal + pairwise",
        "config": StrategyConfig(
            sampler="exploit_orthogonal",
            updater="winner_copy",
            feedback_mode="pairwise",
            candidate_count=5,
            image_size="512x512",
            trust_radius=0.32,
            model_name="runwayml/stable-diffusion-v1-5",
        ),
    },
    {
        "slug": "axis_topk",
        "title": "Axis sweep + top-k ranking",
        "config": StrategyConfig(
            sampler="axis_sweep",
            updater="linear_preference",
            feedback_mode="top_k",
            candidate_count=5,
            image_size="512x512",
            trust_radius=0.34,
            model_name="runwayml/stable-diffusion-v1-5",
        ),
    },
    {
        "slug": "incumbent_winner_only",
        "title": "Incumbent mix + winner only",
        "config": StrategyConfig(
            sampler="incumbent_mix",
            updater="winner_average",
            feedback_mode="winner_only",
            candidate_count=5,
            image_size="512x512",
            trust_radius=0.3,
            model_name="runwayml/stable-diffusion-v1-5",
        ),
    },
    {
        "slug": "uncertainty_approve_reject",
        "title": "Uncertainty-guided + approve/reject",
        "config": StrategyConfig(
            sampler="uncertainty_guided",
            updater="linear_preference",
            feedback_mode="approve_reject",
            candidate_count=5,
            image_size="512x512",
            trust_radius=0.4,
            model_name="runwayml/stable-diffusion-v1-5",
        ),
    },
]


def scripted_feedback(round_payload: dict, feedback_mode: str, round_index: int) -> tuple[FeedbackRequest, str]:
    """Build deterministic scripted feedback for one sample configuration round."""

    ids = [candidate["id"] for candidate in round_payload["candidate_metadata"]]
    preferred = ids[min(2, len(ids) - 1)] if round_index == 1 else ids[1]
    secondary = ids[1] if preferred != ids[1] else ids[2]
    critique = f"Round {round_index}: prefer {preferred} because it balances subject clarity, composition, and controllable variation."

    if feedback_mode == "scalar_rating":
        ratings = {candidate_id: max(1, len(ids) - position) for position, candidate_id in enumerate(ids)}
        ratings[preferred] = 5
        ratings[secondary] = 4
        return FeedbackRequest(feedback_type="scalar_rating", payload={"ratings": ratings}, critique_text=critique), critique

    if feedback_mode == "pairwise":
        return (
            FeedbackRequest(
                feedback_type="pairwise",
                payload={"winner_candidate_id": preferred, "loser_candidate_id": ids[-1]},
                critique_text=critique,
            ),
            critique,
        )

    if feedback_mode == "top_k":
        ranking = [preferred] + [candidate_id for candidate_id in ids if candidate_id != preferred]
        return FeedbackRequest(feedback_type="top_k", payload={"ranking": ranking}, critique_text=critique), critique

    if feedback_mode == "winner_only":
        return (
            FeedbackRequest(
                feedback_type="winner_only",
                payload={"winner_candidate_id": preferred},
                critique_text=critique,
            ),
            critique,
        )

    approvals = {candidate_id: candidate_id in {preferred, secondary} for candidate_id in ids}
    return (
        FeedbackRequest(
            feedback_type="approve_reject",
            payload={"winner_candidate_id": preferred, "approvals": approvals},
            critique_text=critique,
        ),
        critique,
    )


def copy_candidate_image(image_path: str, source_artifacts_dir: Path, target_images_dir: Path) -> str:
    """Copy one generated candidate image into a portable bundle folder."""

    filename = Path(image_path).name
    shutil.copy2(source_artifacts_dir / filename, target_images_dir / filename)
    return f"images/{filename}"


def rewrite_trace_report_image_paths(report_path: Path, destination_path: Path) -> None:
    """Rewrite runtime artifact URLs so a copied trace report works from disk."""

    html = report_path.read_text(encoding="utf-8")
    rewritten = re.sub(r'(["\'])/artifacts/([^"\']+)(["\'])', r"\1images/\2\3", html)
    destination_path.write_text(rewritten, encoding="utf-8")


def render_index(samples: list[dict], output_path: Path, initial_prompt: str, negative_prompt: str) -> None:
    """Write a compact HTML summary for the configuration matrix."""

    sections = [
        "<!doctype html>",
        "<html lang='en'>",
        "<head>",
        "  <meta charset='utf-8'>",
        "  <meta name='viewport' content='width=device-width, initial-scale=1'>",
        "  <title>StableSteering configuration matrix</title>",
        "  <style>",
        "    body { margin: 0; font-family: 'Segoe UI', sans-serif; background: linear-gradient(180deg, #efe7db, #faf7f2); color: #231b15; }",
        "    main { max-width: 1240px; margin: 0 auto; padding: 28px 20px 48px; }",
        "    .hero, .sample { background: rgba(255, 252, 247, 0.97); border: 1px solid #dacdbd; border-radius: 20px; padding: 22px; box-shadow: 0 14px 34px rgba(61, 42, 20, 0.08); }",
        "    .hero { margin-bottom: 18px; }",
        "    .sample { margin-bottom: 18px; }",
        "    .meta { display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 12px; margin: 14px 0 18px; }",
        "    .metric { background: #f6efe6; border-radius: 14px; padding: 12px; }",
        "    .grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(190px, 1fr)); gap: 14px; }",
        "    .card { background: #fff; border: 1px solid #eadfd3; border-radius: 16px; overflow: hidden; }",
        "    .card img { width: 100%; aspect-ratio: 1/1; object-fit: cover; display: block; }",
        "    .card .body { padding: 10px 12px; font-size: 0.92rem; }",
        "    code, pre { font-family: Consolas, monospace; }",
        "    pre { background: #f8f1e8; border-radius: 14px; padding: 12px; overflow: auto; }",
        "    a { color: #8b4f16; }",
        "  </style>",
        "</head>",
        "<body>",
        "<main>",
        "  <section class='hero'>",
        "    <h1>StableSteering configuration matrix</h1>",
        "    <p>This bundle compares multiple real GPU-backed sampling and feedback configurations against the same prompt. Each run uses the same orchestration contract but changes sampler, updater, and feedback mode to show how exploration and selection behavior differ.</p>",
        f"    <p><strong>Initial prompt:</strong> {escape(initial_prompt)}</p>",
        f"    <p><strong>Negative prompt:</strong> {escape(negative_prompt)}</p>",
        "  </section>",
    ]

    for sample in samples:
        sections.extend(
            [
                "  <section class='sample'>",
                f"    <h2>{escape(sample['title'])}</h2>",
                f"    <p><a href='{escape(sample['trace_report'])}'>Trace report</a> · <code>{escape(sample['bundle_dir'])}</code></p>",
                "    <div class='meta'>",
                f"      <div class='metric'><strong>Session</strong><div>{escape(sample['session_id'])}</div></div>",
                f"      <div class='metric'><strong>Sampler</strong><div>{escape(sample['config']['sampler'])}</div></div>",
                f"      <div class='metric'><strong>Feedback mode</strong><div>{escape(sample['config']['feedback_mode'])}</div></div>",
                f"      <div class='metric'><strong>Updater</strong><div>{escape(sample['config']['updater'])}</div></div>",
                "    </div>",
                f"    <p><strong>Initial prompt:</strong> {escape(sample['prompt'])}</p>",
                f"    <pre>{escape(json.dumps(sample['config'], indent=2))}</pre>",
                "    <div class='grid'>",
            ]
        )
        for card in sample["cards"]:
            sections.extend(
                [
                    "      <article class='card'>",
                    f"        <img src='{escape(card['image'])}' alt='{escape(card['candidate_id'])}'>",
                    "        <div class='body'>",
                    f"          <div><strong>{escape(card['label'])}</strong></div>",
                    f"          <div>Candidate: <code>{escape(card['candidate_id'])}</code></div>",
                    f"          <div>Role: {escape(card['role'])}</div>",
                    f"          <div>z: <code>{escape(json.dumps(card['z']))}</code></div>",
                    "        </div>",
                    "      </article>",
                ]
            )
        sections.extend(["    </div>", "  </section>"])

    sections.extend(["</main>", "</body>", "</html>"])
    output_path.write_text("\n".join(sections), encoding="utf-8")


def main() -> int:
    """Generate a real-GPU comparison matrix across multiple configuration modes."""

    try:
        import torch
    except ImportError as exc:
        raise RuntimeError("PyTorch is required for configuration sample generation.") from exc

    if not torch.cuda.is_available():
        raise RuntimeError("Configuration sample generation requires a CUDA-capable GPU.")

    root = Path("output") / "examples" / "configuration_matrix"
    if root.exists():
        shutil.rmtree(root)
    root.mkdir(parents=True, exist_ok=True)
    shared_artifacts_dir = root / "_shared_artifacts"
    shared_artifacts_dir.mkdir(parents=True, exist_ok=True)

    generator = build_generation_engine(
        backend="diffusers",
        model_id="runwayml/stable-diffusion-v1-5",
        models_root=Path("models"),
        artifacts_dir=shared_artifacts_dir,
        num_inference_steps=24,
    )

    prompt = (
        "A cinematic outdoor portrait of a futuristic field scientist standing beside a compact research rover, "
        "golden-hour light, crisp materials, premium editorial photography, realistic proportions"
    )
    negative_prompt = "blurry, low contrast, text, watermark, cropped face, distorted hands, clutter"
    samples: list[dict] = []

    for spec in CONFIGURATIONS:
        bundle_dir = root / spec["slug"]
        images_dir = bundle_dir / "images"
        images_dir.mkdir(parents=True, exist_ok=True)
        repository = JsonRepository(bundle_dir / "data")
        orchestrator = Orchestrator(repository=repository, generator=generator)
        experiment = orchestrator.create_experiment(
            ExperimentCreate(
                name=spec["title"],
                description="Configuration comparison sample",
                config=spec["config"],
            )
        )
        session = orchestrator.create_session(
            SessionCreate(
                experiment_id=experiment.id,
                prompt=prompt,
                negative_prompt=negative_prompt,
            )
        )

        for round_index in range(1, 3):
            round_payload = orchestrator.generate_round(session.id).model_dump(mode="json")
            request, _ = scripted_feedback(round_payload, spec["config"].feedback_mode.value, round_index)
            orchestrator.submit_feedback(round_payload["round_id"], request)

        rounds = [round_obj.model_dump(mode="json") for round_obj in orchestrator.get_session_rounds(session.id)]
        session_state = orchestrator.get_session(session.id).model_dump(mode="json")
        copied_images: set[str] = set()
        for round_obj in rounds:
            for candidate in round_obj["candidates"]:
                filename = Path(candidate["image_path"]).name
                if filename in copied_images:
                    continue
                copy_candidate_image(candidate["image_path"], shared_artifacts_dir, images_dir)
                copied_images.add(filename)
        cards = []
        for round_obj in rounds:
            winner_id = round_obj.get("update_summary", {}).get("winner_candidate_id")
            selected = next(
                (candidate for candidate in round_obj["candidates"] if candidate["id"] == winner_id),
                round_obj["candidates"][0],
            )
            cards.append(
                {
                    "label": f"Round {round_obj['round_index']} winner",
                    "candidate_id": selected["id"],
                    "image": f"{spec['slug']}/images/{Path(selected['image_path']).name}",
                    "role": selected["sampler_role"],
                    "z": selected["z"],
                }
            )

        trace_report_path = orchestrator.generate_trace_report(session.id)
        portable_trace = bundle_dir / "trace_report.html"
        rewrite_trace_report_image_paths(trace_report_path, portable_trace)
        manifest = {
            "session_id": session.id,
            "experiment_id": experiment.id,
            "config": spec["config"].model_dump(mode="json"),
            "round_count": len(rounds),
            "trace_report": str(portable_trace.resolve()),
            "diagnostics": generator.diagnostics(),
        }
        (bundle_dir / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
        samples.append(
            {
                "title": spec["title"],
                "slug": spec["slug"],
                "bundle_dir": str(bundle_dir.resolve()),
                "trace_report": f"{spec['slug']}/trace_report.html",
                "session_id": session.id,
                "config": spec["config"].model_dump(mode="json"),
                "cards": cards,
                "session": session_state,
                "prompt": session_state["prompt"],
            }
        )

    index_path = root / "index.html"
    render_index(samples, index_path, prompt, negative_prompt)
    print(f"Configuration matrix written to {index_path.resolve()}")
    for sample in samples:
        print(f"- {sample['title']}: {sample['session_id']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
