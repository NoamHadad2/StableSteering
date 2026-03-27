from __future__ import annotations

import argparse
import shutil
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw, ImageFont, ImageOps

from app.core.schema import ExperimentCreate, SessionCreate, StrategyConfig
from app.engine.generation import build_generation_engine
from app.engine.orchestrator import Orchestrator
from app.storage.repository import JsonRepository
from run_paper_method_extension_comparison import (
    _apply_oracle_policy,
    _build_curve_svg,
    _feedback_request,
    _safe_mean,
    _write_csv,
    _write_json,
    _write_text,
)
from run_paper_oracle_multimetric_repeated import DINOv2Metric
from run_paper_oracle_target_recovery import (
    ClipOracle,
    _artifact_path,
    _copy_trace_report,
    _download,
    _load_targets,
    _markdown_to_html,
    _paper_root,
    _read_yaml,
)


@dataclass(frozen=True)
class SteeringPolicy:
    id: str
    label: str
    steering_mode: str
    description: str


def _results_root() -> Path:
    return _paper_root() / "results" / "steering_mode_comparison"


def _figure_root() -> Path:
    root = _paper_root() / "figures"
    root.mkdir(parents=True, exist_ok=True)
    return root


def _load_suite(path: Path) -> tuple[dict[str, Any], list[Any], list[SteeringPolicy]]:
    suite = _read_yaml(path)
    target_suite_path = Path(suite["target_suite_path"])
    if not target_suite_path.is_absolute():
        target_suite_path = Path(__file__).resolve().parents[1] / target_suite_path
    target_suite = _read_yaml(target_suite_path)
    targets = _load_targets(target_suite)
    policies = [
        SteeringPolicy(
            id=str(record["id"]),
            label=str(record["label"]),
            steering_mode=str(record["steering_mode"]),
            description=str(record.get("description", "")),
        )
        for record in suite.get("policies", [])
    ]
    return suite, targets, policies


def _strategy_config(suite: dict[str, Any], policy: SteeringPolicy) -> StrategyConfig:
    payload = dict(suite.get("shared_conditions", {}))
    payload["steering_mode"] = policy.steering_mode
    return StrategyConfig.model_validate(payload)


def _font(size: int):
    for candidate in [
        "C:/Windows/Fonts/segoeui.ttf",
        "C:/Windows/Fonts/tahoma.ttf",
        "C:/Windows/Fonts/arial.ttf",
    ]:
        path = Path(candidate)
        if path.exists():
            return ImageFont.truetype(str(path), size=size)
    return ImageFont.load_default()


def _run_policy(
    *,
    output_dir: Path,
    suite: dict[str, Any],
    policy: SteeringPolicy,
    target: Any,
    clip_oracle: ClipOracle,
    dino_metric: DINOv2Metric,
    backend: str,
) -> dict[str, Any]:
    run_root = output_dir / "runs" / policy.id / target.id
    runtime_root = run_root / "runtime"
    repository = JsonRepository(data_dir=runtime_root)
    config = _strategy_config(suite, policy)
    generator = build_generation_engine(
        backend=backend,
        artifacts_dir=repository.artifacts_dir,
        num_inference_steps=config.num_inference_steps,
    )
    orchestrator = Orchestrator(repository=repository, generator=generator)

    target_path = output_dir / "targets" / Path(target.image_url).name
    _download(target.image_url, target_path)
    target_clip = clip_oracle.embed_image(target_path)
    target_dino = dino_metric.embed_image(target_path)

    experiment = orchestrator.create_experiment(
        ExperimentCreate(
            name=f"{policy.label} steering mode comparison",
            description=f"{policy.id} / {target.id}",
            config=config,
        )
    )
    session = orchestrator.create_session(
        SessionCreate(
            experiment_id=experiment.id,
            prompt=target.caption,
            negative_prompt=target.negative_prompt,
        )
    )

    round_rows: list[dict[str, Any]] = []
    candidate_rows: list[dict[str, Any]] = []
    best_clip = -1.0
    best_dino = -1.0
    baseline_clip = None
    baseline_dino = None
    final_best_image_path = ""

    for round_index in range(1, int(suite["max_rounds"]) + 1):
        round_response = orchestrator.generate_round(session.id)
        round_obj = orchestrator.get_session_rounds(session.id)[-1]
        scored_candidates: list[dict[str, Any]] = []
        for candidate in round_response.candidate_metadata:
            image_path = _artifact_path(runtime_root, candidate.image_path)
            clip_embedding = clip_oracle.embed_image(image_path)
            dino_embedding = dino_metric.embed_image(image_path)
            clip_score = clip_oracle.cosine(target_clip, clip_embedding)
            dino_score = dino_metric.cosine(target_dino, dino_embedding)
            record = {
                "policy_id": policy.id,
                "policy_label": policy.label,
                "steering_mode": policy.steering_mode,
                "target_id": target.id,
                "target_label": target.label,
                "session_id": session.id,
                "round_id": round_obj.id,
                "round_index": round_index,
                "candidate_id": candidate.id,
                "candidate_index": candidate.candidate_index,
                "sampler_role": candidate.sampler_role,
                "clip_score": round(clip_score, 6),
                "dinov2_score": round(dino_score, 6),
                "incumbent_novelty": round(float(candidate.generation_params.get("incumbent_novelty", 0.0)), 6),
                "carried_forward": bool(candidate.generation_params.get("carried_forward")),
                "image_path": str(image_path),
            }
            if baseline_clip is None and candidate.candidate_index == 0:
                baseline_clip = clip_score
                baseline_dino = dino_score
            scored_candidates.append(record)
            candidate_rows.append(record)

        _apply_oracle_policy(scored_candidates, oracle_policy=str(suite["oracle_policy"]))
        scored_candidates.sort(key=lambda row: (-float(row["oracle_score"]), row["candidate_id"]))
        winner = scored_candidates[0]
        best_clip = max(best_clip, float(winner["clip_score"]))
        best_dino = max(best_dino, float(winner["dinov2_score"]))
        final_best_image_path = winner["image_path"]

        round_rows.append(
            {
                "policy_id": policy.id,
                "policy_label": policy.label,
                "steering_mode": policy.steering_mode,
                "target_id": target.id,
                "target_label": target.label,
                "session_id": session.id,
                "round_id": round_obj.id,
                "round_index": round_index,
                "winner_candidate_id": winner["candidate_id"],
                "best_clip": round(best_clip, 6),
                "best_dinov2": round(best_dino, 6),
                "baseline_clip": round(float(baseline_clip or 0.0), 6),
                "baseline_dinov2": round(float(baseline_dino or 0.0), 6),
            }
        )

        if round_index < int(suite["max_rounds"]):
            orchestrator.submit_feedback(
                round_obj.id,
                _feedback_request(suite["shared_conditions"]["feedback_mode"], scored_candidates),
            )

    trace_report = _copy_trace_report(orchestrator.generate_trace_report(session.id), run_root)
    run_summary = {
        "policy_id": policy.id,
        "policy_label": policy.label,
        "steering_mode": policy.steering_mode,
        "target_id": target.id,
        "target_label": target.label,
        "sampler": suite["shared_conditions"]["sampler"],
        "updater": suite["shared_conditions"]["updater"],
        "feedback_mode": suite["shared_conditions"]["feedback_mode"],
        "oracle_policy": suite["oracle_policy"],
        "max_rounds": int(suite["max_rounds"]),
        "baseline_clip": round(float(baseline_clip or 0.0), 6),
        "final_best_clip": round(best_clip, 6),
        "delta_clip": round(best_clip - float(baseline_clip or 0.0), 6),
        "baseline_dinov2": round(float(baseline_dino or 0.0), 6),
        "final_best_dinov2": round(best_dino, 6),
        "delta_dinov2": round(best_dino - float(baseline_dino or 0.0), 6),
        "final_best_image_path": final_best_image_path,
        "target_path": str(target_path),
        "trace_report": str(trace_report.relative_to(output_dir)),
    }
    _write_json(run_root / "summary.json", run_summary)
    return {"run_summary": run_summary, "round_rows": round_rows, "candidate_rows": candidate_rows}


def _policy_summary_rows(run_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    for row in run_rows:
        grouped.setdefault(str(row["policy_id"]), []).append(row)

    rows: list[dict[str, Any]] = []
    for policy_id, group in grouped.items():
        rows.append(
            {
                "policy_id": policy_id,
                "policy_label": group[0]["policy_label"],
                "steering_mode": group[0]["steering_mode"],
                "target_count": len(group),
                "mean_baseline_clip": round(_safe_mean([float(row["baseline_clip"]) for row in group]), 6),
                "mean_final_best_clip": round(_safe_mean([float(row["final_best_clip"]) for row in group]), 6),
                "mean_delta_clip": round(_safe_mean([float(row["delta_clip"]) for row in group]), 6),
                "mean_baseline_dinov2": round(_safe_mean([float(row["baseline_dinov2"]) for row in group]), 6),
                "mean_final_best_dinov2": round(_safe_mean([float(row["final_best_dinov2"]) for row in group]), 6),
                "mean_delta_dinov2": round(_safe_mean([float(row["delta_dinov2"]) for row in group]), 6),
            }
        )
    rows.sort(key=lambda row: row["policy_id"])
    return rows


def _curve_rows(round_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[tuple[str, int], list[dict[str, Any]]] = {}
    for row in round_rows:
        grouped.setdefault((str(row["policy_label"]), int(row["round_index"])), []).append(row)

    rows: list[dict[str, Any]] = []
    for (policy_label, round_index), group in grouped.items():
        rows.append(
            {
                "policy_label": policy_label,
                "round_index": round_index,
                "mean_best_clip": round(_safe_mean([float(row["best_clip"]) for row in group]), 6),
                "mean_baseline_clip": round(_safe_mean([float(row["baseline_clip"]) for row in group]), 6),
                "mean_best_dinov2": round(_safe_mean([float(row["best_dinov2"]) for row in group]), 6),
                "mean_baseline_dinov2": round(_safe_mean([float(row["baseline_dinov2"]) for row in group]), 6),
            }
        )
    rows.sort(key=lambda row: (row["policy_label"], row["round_index"]))
    return rows


def _build_examples_figure(run_rows: list[dict[str, Any]], output_path: Path) -> None:
    by_target: dict[str, list[dict[str, Any]]] = {}
    for row in run_rows:
        by_target.setdefault(str(row["target_label"]), []).append(row)

    sorted_targets = sorted(
        by_target.items(),
        key=lambda item: max(float(row["delta_clip"]) for row in item[1]) - min(float(row["delta_clip"]) for row in item[1]),
        reverse=True,
    )
    selected_targets = sorted_targets[: min(2, len(sorted_targets))]
    policies = sorted({str(row["policy_label"]) for row in run_rows})
    policy_order = {policy: index for index, policy in enumerate(policies)}

    tile_w = 220
    tile_h = 220
    gap = 16
    margin = 24
    header_h = 88
    row_gap = 54
    rows = len(selected_targets)
    cols = len(policies) + 1
    width = margin * 2 + cols * tile_w + (cols - 1) * gap
    height = margin * 2 + header_h + rows * tile_h + (rows - 1) * row_gap + rows * 54
    canvas = Image.new("RGB", (width, height), "#faf7f0")
    draw = ImageDraw.Draw(canvas)
    title_font = _font(28)
    label_font = _font(18)
    small_font = _font(14)

    draw.text((margin, 18), "Steering-mode comparison examples", fill="#2b221a", font=title_font)
    draw.text(
        (margin, 52),
        "Targets plus final best images from each steering mode under one shared outer-loop configuration.",
        fill="#6e5a47",
        font=small_font,
    )

    column_labels = ["Target"] + policies
    for col, label in enumerate(column_labels):
        x = margin + col * (tile_w + gap)
        draw.text((x + 6, margin + header_h - 30), label, fill="#7d4a16", font=label_font)

    for row_index, (target_label, entries) in enumerate(selected_targets):
        y = margin + header_h + row_index * (tile_h + row_gap + 54)
        entries = sorted(entries, key=lambda row: policy_order[str(row["policy_label"])])
        target_image = Image.open(entries[0]["target_path"]).convert("RGB")
        target_image = ImageOps.fit(target_image, (tile_w, tile_h), method=Image.Resampling.LANCZOS)
        x = margin
        canvas.paste(target_image, (x, y))
        draw.rounded_rectangle((x, y, x + tile_w, y + tile_h), radius=14, outline="#d6c7b6", width=2)
        draw.text((x + 4, y + tile_h + 8), target_label, fill="#4e4034", font=small_font)

        for col_index, entry in enumerate(entries, start=1):
            x = margin + col_index * (tile_w + gap)
            image = Image.open(entry["final_best_image_path"]).convert("RGB")
            image = ImageOps.fit(image, (tile_w, tile_h), method=Image.Resampling.LANCZOS)
            canvas.paste(image, (x, y))
            draw.rounded_rectangle((x, y, x + tile_w, y + tile_h), radius=14, outline="#d6c7b6", width=2)
            draw.text(
                (x + 4, y + tile_h + 8),
                f"CLIP {float(entry['final_best_clip']):.3f} | DINO {float(entry['final_best_dinov2']):.3f}",
                fill="#4e4034",
                font=small_font,
            )

    canvas.save(output_path, quality=95)


def _build_analysis(output_dir: Path, policy_summaries: list[dict[str, Any]], round_rows: list[dict[str, Any]], run_rows: list[dict[str, Any]]) -> None:
    analysis_dir = output_dir / "analysis"
    analysis_dir.mkdir(parents=True, exist_ok=True)

    curve_rows = _curve_rows(round_rows)
    _write_csv(
        analysis_dir / "steering_mode_curve.csv",
        curve_rows,
        ["policy_label", "round_index", "mean_best_clip", "mean_baseline_clip", "mean_best_dinov2", "mean_baseline_dinov2"],
    )
    figure_root = _figure_root()
    curve_path = analysis_dir / "steering_mode_curve.svg"
    _build_curve_svg(curve_rows, curve_path, "Steering-mode comparison: hidden-target recovery")
    shutil.copy2(curve_path, figure_root / "figure_19_steering_mode_curve.svg")

    examples_path = analysis_dir / "steering_mode_examples.png"
    _build_examples_figure(run_rows, examples_path)
    shutil.copy2(examples_path, figure_root / "figure_20_steering_mode_examples.png")

    markdown_lines = [
        "# Steering Mode Comparison Analysis",
        "",
        "This compact bundle keeps the outer steering loop fixed and compares how the low-dimensional direction is injected into prompt embeddings.",
        "",
        "| steering mode | clip final | clip delta | dinov2 final | dinov2 delta |",
        "| --- | ---: | ---: | ---: | ---: |",
    ]
    markdown_lines.extend(
        f"| {row['policy_label']} | {row['mean_final_best_clip']:.3f} | {row['mean_delta_clip']:.3f} | {row['mean_final_best_dinov2']:.3f} | {row['mean_delta_dinov2']:.3f} |"
        for row in policy_summaries
    )
    markdown_lines.extend(
        [
            "",
            "![Steering mode curve](steering_mode_curve.svg)",
            "",
            "![Steering mode examples](steering_mode_examples.png)",
            "",
        ]
    )
    summary_md = "\n".join(markdown_lines)
    _write_text(analysis_dir / "analysis_summary.md", summary_md)
    _markdown_to_html("Steering Mode Comparison Analysis", summary_md, analysis_dir / "analysis_summary.html")


def _build_readme(manifest: dict[str, Any]) -> str:
    return (
        "# Steering Mode Comparison Results\n\n"
        "This bundle compares different steering-direction injection approaches while keeping the outer steering loop fixed.\n\n"
        f"- targets: `{manifest['target_count']}`\n"
        f"- policies: `{manifest['policy_count']}`\n"
        f"- runs: `{manifest['run_count']}`\n"
        f"- rounds: `{manifest['round_count']}`\n"
        f"- candidate rows: `{manifest['candidate_count']}`\n\n"
        "Key outputs:\n\n"
        "- `manifest.json`\n"
        "- `tables/policy_summary.csv`\n"
        "- `tables/runs.csv`\n"
        "- `tables/rounds.csv`\n"
        "- `analysis/analysis_summary.md`\n"
        "- `analysis/steering_mode_curve.svg`\n"
        "- `analysis/steering_mode_examples.png`\n"
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Compare steering direction-computation approaches under shared oracle target recovery.")
    parser.add_argument("--suite", type=Path, default=_paper_root() / "protocols" / "steering_mode_comparison_suite.yaml")
    parser.add_argument("--output-dir", type=Path, default=_results_root())
    parser.add_argument("--backend", choices=["auto", "diffusers", "mock"], default="auto")
    parser.add_argument("--max-targets", type=int, default=3)
    args = parser.parse_args()

    suite, targets, policies = _load_suite(args.suite)
    targets = targets[: max(1, min(args.max_targets, len(targets)))]
    output_dir = args.output_dir
    output_dir.mkdir(parents=True, exist_ok=True)
    clip_oracle = ClipOracle(str(suite["oracle_model"]))
    dino_metric = DINOv2Metric(str(suite["dino_model"]), device="cpu")

    run_rows: list[dict[str, Any]] = []
    round_rows: list[dict[str, Any]] = []
    candidate_rows: list[dict[str, Any]] = []

    for target in targets:
        for policy in policies:
            result = _run_policy(
                output_dir=output_dir,
                suite=suite,
                policy=policy,
                target=target,
                clip_oracle=clip_oracle,
                dino_metric=dino_metric,
                backend=args.backend,
            )
            run_rows.append(result["run_summary"])
            round_rows.extend(result["round_rows"])
            candidate_rows.extend(result["candidate_rows"])

    tables_dir = output_dir / "tables"
    tables_dir.mkdir(parents=True, exist_ok=True)
    _write_csv(
        tables_dir / "runs.csv",
        run_rows,
        [
            "policy_id", "policy_label", "steering_mode", "target_id", "target_label", "sampler", "updater", "feedback_mode",
            "oracle_policy", "max_rounds", "baseline_clip", "final_best_clip", "delta_clip", "baseline_dinov2", "final_best_dinov2",
            "delta_dinov2", "final_best_image_path", "target_path", "trace_report",
        ],
    )
    _write_csv(
        tables_dir / "rounds.csv",
        round_rows,
        [
            "policy_id", "policy_label", "steering_mode", "target_id", "target_label", "session_id", "round_id", "round_index",
            "winner_candidate_id", "best_clip", "best_dinov2", "baseline_clip", "baseline_dinov2",
        ],
    )
    _write_csv(
        tables_dir / "candidates.csv",
        candidate_rows,
        [
            "policy_id", "policy_label", "steering_mode", "target_id", "target_label", "session_id", "round_id", "round_index",
            "candidate_id", "candidate_index", "sampler_role", "clip_score", "dinov2_score", "incumbent_novelty", "carried_forward", "image_path",
        ],
    )
    policy_summaries = _policy_summary_rows(run_rows)
    _write_csv(
        tables_dir / "policy_summary.csv",
        policy_summaries,
        [
            "policy_id", "policy_label", "steering_mode", "target_count", "mean_baseline_clip", "mean_final_best_clip", "mean_delta_clip",
            "mean_baseline_dinov2", "mean_final_best_dinov2", "mean_delta_dinov2",
        ],
    )

    manifest = {
        "suite_name": suite["suite_name"],
        "description": suite.get("description", ""),
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "target_count": len(targets),
        "policy_count": len(policies),
        "run_count": len(run_rows),
        "round_count": len(round_rows),
        "candidate_count": len(candidate_rows),
        "oracle_model": suite["oracle_model"],
        "dino_model": suite["dino_model"],
        "backend": args.backend,
    }
    _write_json(output_dir / "manifest.json", manifest)
    _write_text(output_dir / "README.md", _build_readme(manifest))
    _build_analysis(output_dir, policy_summaries, round_rows, run_rows)
    print(f"Wrote steering mode comparison bundle to {output_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
