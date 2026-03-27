from __future__ import annotations

import argparse
import math
import shutil
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.core.schema import ExperimentCreate, FeedbackRequest, FeedbackType, SessionCreate, StrategyConfig
from app.engine.generation import build_generation_engine
from app.engine.orchestrator import Orchestrator
from app.storage.repository import JsonRepository
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
    _write_csv,
    _write_json,
    _write_text,
)


@dataclass(frozen=True)
class Policy:
    slice_id: str
    id: str
    label: str
    sampler: str
    updater: str
    feedback_mode: str
    oracle_policy: str
    description: str


def _results_root() -> Path:
    return _paper_root() / "results" / "method_extension_comparison"


def _load_suite(path: Path) -> tuple[dict[str, Any], list[Any], list[Policy]]:
    suite = _read_yaml(path)
    target_suite_path = Path(suite["target_suite_path"])
    if not target_suite_path.is_absolute():
        target_suite_path = Path(__file__).resolve().parents[1] / target_suite_path
    target_suite = _read_yaml(target_suite_path)
    targets = _load_targets(target_suite)

    policies: list[Policy] = []
    for slice_id, key in (
        ("sampler_slice", "sampler_policies"),
        ("preference_slice", "preference_policies"),
        ("oracle_slice", "oracle_policies"),
    ):
        for record in suite.get(key, []):
            policies.append(
                Policy(
                    slice_id=slice_id,
                    id=str(record["id"]),
                    label=str(record["label"]),
                    sampler=str(record["sampler"]),
                    updater=str(record["updater"]),
                    feedback_mode=str(record["feedback_mode"]),
                    oracle_policy=str(record.get("oracle_policy", "clip_only")),
                    description=str(record.get("description", "")),
                )
            )
    return suite, targets, policies


def _strategy_config(suite: dict[str, Any], policy: Policy) -> StrategyConfig:
    payload = dict(suite.get("shared_conditions", {}))
    payload.update({"sampler": policy.sampler, "updater": policy.updater, "feedback_mode": policy.feedback_mode})
    return StrategyConfig.model_validate(payload)


def _rescale(values: list[float]) -> list[float]:
    if not values:
        return []
    lo = min(values)
    hi = max(values)
    if abs(hi - lo) < 1e-9:
        return [0.5 for _ in values]
    return [(value - lo) / (hi - lo) for value in values]


def _apply_oracle_policy(rows: list[dict[str, Any]], *, oracle_policy: str) -> list[dict[str, Any]]:
    if not rows:
        return rows
    clip_scaled = _rescale([float(row["clip_score"]) for row in rows])
    dino_scaled = _rescale([float(row["dinov2_score"]) for row in rows])
    novelty_scaled = _rescale([float(row.get("incumbent_novelty", 0.0)) for row in rows])
    for row, clip_value, dino_value, novelty_value in zip(rows, clip_scaled, dino_scaled, novelty_scaled, strict=False):
        if oracle_policy == "clip_only":
            row["oracle_score"] = round(float(row["clip_score"]), 6)
        elif oracle_policy == "clip_dino_ensemble":
            row["oracle_score"] = round((0.45 * clip_value) + (0.55 * dino_value), 6)
        elif oracle_policy == "clip_novelty_bonus":
            row["oracle_score"] = round((0.45 * clip_value) + (0.55 * novelty_value), 6)
        else:
            raise ValueError(f"Unsupported oracle policy: {oracle_policy}")
    return rows


def _feedback_request(feedback_mode: str, ordered_scores: list[dict[str, Any]]) -> FeedbackRequest:
    winner_id = ordered_scores[0]["candidate_id"]
    feedback_type = FeedbackType(feedback_mode)
    if feedback_type == FeedbackType.winner_only:
        payload = {"winner_candidate_id": winner_id}
    elif feedback_type == FeedbackType.scalar_rating:
        oracle_scores = [float(row["oracle_score"]) for row in ordered_scores]
        lo = min(oracle_scores)
        hi = max(oracle_scores)
        if abs(hi - lo) < 1e-9:
            ratings = {row["candidate_id"]: 3.0 for row in ordered_scores}
        else:
            ratings = {
                row["candidate_id"]: round(1.0 + (4.0 * ((float(row["oracle_score"]) - lo) / (hi - lo))), 4)
                for row in ordered_scores
            }
        payload = {"ratings": ratings}
    elif feedback_type == FeedbackType.top_k:
        payload = {"ranking": [row["candidate_id"] for row in ordered_scores]}
    elif feedback_type == FeedbackType.pairwise:
        payload = {"winner_candidate_id": winner_id, "loser_candidate_id": ordered_scores[-1]["candidate_id"]}
    elif feedback_type == FeedbackType.approve_reject:
        approvals = {row["candidate_id"]: index < max(1, len(ordered_scores) // 2) for index, row in enumerate(ordered_scores)}
        approvals[winner_id] = True
        payload = {"winner_candidate_id": winner_id, "approvals": approvals}
    else:
        raise ValueError(f"Unsupported feedback mode: {feedback_mode}")
    return FeedbackRequest(feedback_type=feedback_type, payload=payload)


def _safe_mean(values: list[float]) -> float:
    return sum(values) / len(values) if values else 0.0


def _safe_std(values: list[float]) -> float:
    if len(values) <= 1:
        return 0.0
    mean = _safe_mean(values)
    return math.sqrt(sum((value - mean) ** 2 for value in values) / (len(values) - 1))


def _run_policy(
    *,
    output_dir: Path,
    suite: dict[str, Any],
    policy: Policy,
    target: Any,
    clip_oracle: ClipOracle,
    dino_metric: DINOv2Metric,
    backend: str,
) -> dict[str, Any]:
    run_root = output_dir / "runs" / policy.slice_id / policy.id / target.id
    runtime_root = run_root / "runtime"
    repository = JsonRepository(data_dir=runtime_root)
    config = _strategy_config(suite, policy)
    generator = build_generation_engine(backend=backend, artifacts_dir=repository.artifacts_dir, num_inference_steps=config.num_inference_steps)
    orchestrator = Orchestrator(repository=repository, generator=generator)

    target_path = output_dir / "targets" / Path(target.image_url).name
    _download(target.image_url, target_path)
    target_clip = clip_oracle.embed_image(target_path)
    target_dino = dino_metric.embed_image(target_path)

    experiment = orchestrator.create_experiment(ExperimentCreate(name=f"{policy.label} method extension", description=f"{policy.slice_id} / {policy.id} / {target.id}", config=config))
    session = orchestrator.create_session(SessionCreate(experiment_id=experiment.id, prompt=target.caption, negative_prompt=target.negative_prompt))

    round_rows: list[dict[str, Any]] = []
    candidate_rows: list[dict[str, Any]] = []
    best_clip = -1.0
    best_dino = -1.0
    baseline_clip = None
    baseline_dino = None
    incumbent_clip_embedding = None
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
            incumbent_similarity = clip_oracle.cosine(clip_embedding, incumbent_clip_embedding) if incumbent_clip_embedding is not None else 0.0
            record = {
                "slice_id": policy.slice_id,
                "policy_id": policy.id,
                "policy_label": policy.label,
                "oracle_policy": policy.oracle_policy,
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
                "incumbent_novelty": round(max(0.0, 1.0 - incumbent_similarity), 6),
                "carried_forward": bool(candidate.generation_params.get("carried_forward")),
                "image_path": str(image_path),
                "_clip_embedding": clip_embedding,
            }
            if baseline_clip is None and candidate.candidate_index == 0:
                baseline_clip = clip_score
                baseline_dino = dino_score
            scored_candidates.append(record)
            candidate_rows.append({key: value for key, value in record.items() if not key.startswith("_")})

        _apply_oracle_policy(scored_candidates, oracle_policy=policy.oracle_policy)
        scored_candidates.sort(key=lambda row: (-float(row["oracle_score"]), row["candidate_id"]))
        winner = scored_candidates[0]
        incumbent_clip_embedding = winner["_clip_embedding"]
        best_clip = max(best_clip, float(winner["clip_score"]))
        best_dino = max(best_dino, float(winner["dinov2_score"]))
        final_best_image_path = winner["image_path"]

        round_rows.append(
            {
                "slice_id": policy.slice_id,
                "policy_id": policy.id,
                "policy_label": policy.label,
                "oracle_policy": policy.oracle_policy,
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
                "sampler": policy.sampler,
                "updater": policy.updater,
                "feedback_mode": policy.feedback_mode,
            }
        )

        if round_index < int(suite["max_rounds"]):
            orchestrator.submit_feedback(round_obj.id, _feedback_request(policy.feedback_mode, scored_candidates))

    trace_report = _copy_trace_report(orchestrator.generate_trace_report(session.id), run_root)
    run_summary = {
        "slice_id": policy.slice_id,
        "policy_id": policy.id,
        "policy_label": policy.label,
        "oracle_policy": policy.oracle_policy,
        "target_id": target.id,
        "target_label": target.label,
        "sampler": policy.sampler,
        "updater": policy.updater,
        "feedback_mode": policy.feedback_mode,
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
    grouped: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for row in run_rows:
        grouped.setdefault((row["slice_id"], row["policy_id"]), []).append(row)

    rows: list[dict[str, Any]] = []
    for (slice_id, policy_id), group in grouped.items():
        rows.append(
            {
                "slice_id": slice_id,
                "policy_id": policy_id,
                "policy_label": group[0]["policy_label"],
                "oracle_policy": group[0]["oracle_policy"],
                "sampler": group[0]["sampler"],
                "updater": group[0]["updater"],
                "feedback_mode": group[0]["feedback_mode"],
                "target_count": len(group),
                "mean_baseline_clip": round(_safe_mean([float(row["baseline_clip"]) for row in group]), 6),
                "mean_final_best_clip": round(_safe_mean([float(row["final_best_clip"]) for row in group]), 6),
                "mean_delta_clip": round(_safe_mean([float(row["delta_clip"]) for row in group]), 6),
                "mean_baseline_dinov2": round(_safe_mean([float(row["baseline_dinov2"]) for row in group]), 6),
                "mean_final_best_dinov2": round(_safe_mean([float(row["final_best_dinov2"]) for row in group]), 6),
                "mean_delta_dinov2": round(_safe_mean([float(row["delta_dinov2"]) for row in group]), 6),
            }
        )
    rows.sort(key=lambda row: (row["slice_id"], row["policy_id"]))
    return rows


def _curve_rows(round_rows: list[dict[str, Any]], slice_id: str) -> list[dict[str, Any]]:
    grouped: dict[tuple[str, int], list[dict[str, Any]]] = {}
    for row in round_rows:
        if row["slice_id"] != slice_id:
            continue
        grouped.setdefault((row["policy_label"], int(row["round_index"])), []).append(row)

    rows: list[dict[str, Any]] = []
    for (policy_label, round_index), group in grouped.items():
        rows.append(
            {
                "slice_id": slice_id,
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


def _build_curve_svg(rows: list[dict[str, Any]], output_path: Path, title: str) -> None:
    width = 1140
    height = 760
    left = 90
    right = 60
    top = 86
    panel_gap = 54
    panel_height = 235
    plot_width = width - left - right
    rounds = sorted({int(row["round_index"]) for row in rows})
    policy_order = sorted({row["policy_label"] for row in rows})
    palette = ["#8b4513", "#1f6f8b", "#2d6a4f", "#7c3aed", "#b7791f", "#c2410c"]
    color_map = {policy: palette[index % len(palette)] for index, policy in enumerate(policy_order)}
    clip_values = [float(row["mean_best_clip"]) for row in rows] + [float(row["mean_baseline_clip"]) for row in rows]
    dino_values = [float(row["mean_best_dinov2"]) for row in rows] + [float(row["mean_baseline_dinov2"]) for row in rows]
    clip_lo = min(clip_values) - 0.02
    clip_hi = max(clip_values) + 0.02
    dino_lo = min(dino_values) - 0.02
    dino_hi = max(dino_values) + 0.02

    def x_coord(round_index: int) -> float:
        if len(rounds) == 1:
            return left + (plot_width / 2)
        return left + ((round_index - rounds[0]) / (rounds[-1] - rounds[0])) * plot_width

    def y_coord(score: float, y0: float, lo: float, hi: float) -> float:
        if abs(hi - lo) < 1e-9:
            return y0 + (panel_height / 2)
        return y0 + ((hi - score) / (hi - lo)) * panel_height

    svg_lines = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        '<rect width="100%" height="100%" fill="#fbfaf6"/>',
        f'<text x="{left}" y="42" font-size="28" font-family="Georgia, serif" fill="#1f1b17">{title}</text>',
        f'<text x="{left}" y="66" font-size="16" font-family="Georgia, serif" fill="#4b3f34">Round-wise mean best similarity under CLIP and DINOv2 evaluation</text>',
    ]
    panels = [
        ("CLIP cosine to target", clip_lo, clip_hi, "mean_best_clip", "mean_baseline_clip", 110),
        ("DINOv2 cosine to target", dino_lo, dino_hi, "mean_best_dinov2", "mean_baseline_dinov2", 110 + panel_height + panel_gap),
    ]
    for panel_title, lo, hi, metric_key, baseline_key, y0 in panels:
        svg_lines.append(f'<text x="{left}" y="{y0 - 18}" font-size="18" font-family="Georgia, serif" fill="#1f1b17">{panel_title}</text>')
        svg_lines.append(f'<line x1="{left}" y1="{y0}" x2="{left}" y2="{y0 + panel_height}" stroke="#4b3f34" stroke-width="2"/>')
        svg_lines.append(f'<line x1="{left}" y1="{y0 + panel_height}" x2="{left + plot_width}" y2="{y0 + panel_height}" stroke="#4b3f34" stroke-width="2"/>')
        for tick in range(5):
            value = lo + ((hi - lo) * tick / 4)
            y = y_coord(value, y0, lo, hi)
            svg_lines.append(f'<line x1="{left}" y1="{y:.2f}" x2="{left + plot_width}" y2="{y:.2f}" stroke="#e3d7c8" stroke-width="1"/>')
            svg_lines.append(f'<text x="{left - 10}" y="{y + 5:.2f}" text-anchor="end" font-size="13" font-family="Georgia, serif" fill="#4b3f34">{value:.3f}</text>')
        for round_index in rounds:
            x = x_coord(round_index)
            svg_lines.append(f'<line x1="{x:.2f}" y1="{y0}" x2="{x:.2f}" y2="{y0 + panel_height}" stroke="#efe5d8" stroke-width="1"/>')
            svg_lines.append(f'<text x="{x:.2f}" y="{y0 + panel_height + 22}" text-anchor="middle" font-size="13" font-family="Georgia, serif" fill="#4b3f34">{round_index}</text>')
        baseline_y = y_coord(_safe_mean([float(row[baseline_key]) for row in rows]), y0, lo, hi)
        svg_lines.append(f'<line x1="{left}" y1="{baseline_y:.2f}" x2="{left + plot_width}" y2="{baseline_y:.2f}" stroke="#6b5e53" stroke-dasharray="8 6" stroke-width="2"/>')
        for policy in policy_order:
            policy_rows = sorted([row for row in rows if row["policy_label"] == policy], key=lambda row: int(row["round_index"]))
            points = " ".join(
                f"{x_coord(int(row['round_index'])):.2f},{y_coord(float(row[metric_key]), y0, lo, hi):.2f}"
                for row in policy_rows
            )
            color = color_map[policy]
            svg_lines.append(f'<polyline points="{points}" fill="none" stroke="{color}" stroke-width="3.6" stroke-linecap="round" stroke-linejoin="round"/>')
            for row in policy_rows:
                x = x_coord(int(row["round_index"]))
                y = y_coord(float(row[metric_key]), y0, lo, hi)
                svg_lines.append(f'<circle cx="{x:.2f}" cy="{y:.2f}" r="4.5" fill="{color}" stroke="#fbfaf6" stroke-width="1.8"/>')
    legend_x = left + plot_width - 230
    legend_y = 84
    legend_height = 34 + (len(policy_order) * 22)
    svg_lines.append(f'<rect x="{legend_x}" y="{legend_y}" width="214" height="{legend_height}" rx="12" fill="#fffdfa" stroke="#d8cbb9"/>')
    for index, policy in enumerate(policy_order):
        y = legend_y + 24 + (index * 22)
        color = color_map[policy]
        svg_lines.append(f'<line x1="{legend_x + 14}" y1="{y}" x2="{legend_x + 34}" y2="{y}" stroke="{color}" stroke-width="4" stroke-linecap="round"/>')
        svg_lines.append(f'<text x="{legend_x + 42}" y="{y + 5}" font-size="13" font-family="Georgia, serif" fill="#1f1b17">{policy}</text>')
    svg_lines.append("</svg>")
    _write_text(output_path, "\n".join(svg_lines))


def _build_analysis(output_dir: Path, policy_summaries: list[dict[str, Any]], round_rows: list[dict[str, Any]]) -> None:
    analysis_dir = output_dir / "analysis"
    analysis_dir.mkdir(parents=True, exist_ok=True)
    sections = [
        ("sampler_slice", "Sampler methods", "sampler_slice_curve.svg", _paper_root() / "figures" / "figure_13_sampler_extension_curve.svg"),
        ("preference_slice", "Preference models", "preference_slice_curve.svg", _paper_root() / "figures" / "figure_14_preference_extension_curve.svg"),
        ("oracle_slice", "Oracle steering policies", "oracle_slice_curve.svg", _paper_root() / "figures" / "figure_15_oracle_policy_curve.svg"),
    ]

    markdown_parts = ["# Method Extension Comparison Analysis\n"]
    for slice_id, title, filename, paper_figure in sections:
        slice_rows = [row for row in policy_summaries if row["slice_id"] == slice_id]
        curve_rows = _curve_rows(round_rows, slice_id)
        _write_csv(
            analysis_dir / f"{slice_id}_curve.csv",
            curve_rows,
            ["slice_id", "policy_label", "round_index", "mean_best_clip", "mean_baseline_clip", "mean_best_dinov2", "mean_baseline_dinov2"],
        )
        _build_curve_svg(curve_rows, analysis_dir / filename, f"{title}: target-recovery comparison")
        shutil.copy2(analysis_dir / filename, paper_figure)
        markdown_parts.append(f"## {title}\n")
        markdown_parts.append("| policy | clip final | clip delta | dinov2 final | dinov2 delta |")
        markdown_parts.append("| --- | ---: | ---: | ---: | ---: |")
        markdown_parts.extend(
            f"| {row['policy_label']} | {row['mean_final_best_clip']:.3f} | {row['mean_delta_clip']:.3f} | {row['mean_final_best_dinov2']:.3f} | {row['mean_delta_dinov2']:.3f} |"
            for row in slice_rows
        )
        markdown_parts.append("")
        markdown_parts.append(f"![{title}]({filename})")
        markdown_parts.append("")

    summary_md = "\n".join(markdown_parts)
    _write_text(analysis_dir / "analysis_summary.md", summary_md)
    _markdown_to_html("Method Extension Comparison Analysis", summary_md, analysis_dir / "analysis_summary.html")


def _build_readme(manifest: dict[str, Any]) -> str:
    return (
        "# Method Extension Comparison Results\n\n"
        "This bundle compares new sampling methods, richer user-preference models, and alternative oracle steering policies under a shared hidden-target recovery scaffold.\n\n"
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
        "- `tables/candidates.csv`\n"
        "- `analysis/analysis_summary.md`\n"
        "- `analysis/sampler_slice_curve.svg`\n"
        "- `analysis/preference_slice_curve.svg`\n"
        "- `analysis/oracle_slice_curve.svg`\n"
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Compare new sampler, preference, and oracle methods under shared target recovery.")
    parser.add_argument("--suite", type=Path, default=_paper_root() / "protocols" / "method_extension_comparison_suite.yaml")
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
            "slice_id", "policy_id", "policy_label", "oracle_policy", "target_id", "target_label", "sampler", "updater", "feedback_mode",
            "max_rounds", "baseline_clip", "final_best_clip", "delta_clip", "baseline_dinov2", "final_best_dinov2", "delta_dinov2",
            "final_best_image_path", "target_path", "trace_report",
        ],
    )
    _write_csv(
        tables_dir / "rounds.csv",
        round_rows,
        [
            "slice_id", "policy_id", "policy_label", "oracle_policy", "target_id", "target_label", "session_id", "round_id", "round_index",
            "winner_candidate_id", "best_clip", "best_dinov2", "baseline_clip", "baseline_dinov2", "sampler", "updater", "feedback_mode",
        ],
    )
    _write_csv(
        tables_dir / "candidates.csv",
        candidate_rows,
        [
            "slice_id", "policy_id", "policy_label", "oracle_policy", "target_id", "target_label", "session_id", "round_id", "round_index",
            "candidate_id", "candidate_index", "sampler_role", "clip_score", "dinov2_score", "incumbent_novelty", "carried_forward", "image_path",
        ],
    )
    policy_summaries = _policy_summary_rows(run_rows)
    _write_csv(
        tables_dir / "policy_summary.csv",
        policy_summaries,
        [
            "slice_id", "policy_id", "policy_label", "oracle_policy", "sampler", "updater", "feedback_mode", "target_count",
            "mean_baseline_clip", "mean_final_best_clip", "mean_delta_clip", "mean_baseline_dinov2", "mean_final_best_dinov2", "mean_delta_dinov2",
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
    _build_analysis(output_dir, policy_summaries, round_rows)
    print(f"Wrote method extension comparison bundle to {output_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
