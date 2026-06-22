from __future__ import annotations

import argparse
import math
import shutil
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

from app.core.schema import ExperimentCreate, FeedbackRequest, FeedbackType, SessionCreate, StrategyConfig
from app.engine.generation import build_generation_engine
from app.engine.orchestrator import Orchestrator
from app.storage.repository import JsonRepository
from run_paper_oracle_multimetric_repeated import (
    DINOv2Metric,
    MetricSpec,
    _artifact_path,
    _build_metric_objects,
    _download,
    _metric_specs_from_suite,
    _paper_root,
    _read_yaml,
    _safe_mean,
    _safe_std,
    _strategy_config_from_suite,
)
from run_paper_oracle_target_recovery import (
    ClipOracle,
    OracleTarget,
    _copy_trace_report,
    _load_targets,
    _markdown_to_html,
    _write_csv,
    _write_json,
    _write_text,
)


@dataclass(frozen=True)
class PolicySpec:
    id: str
    label: str
    incumbent_policy: str
    cooldown_rounds: int
    penalty_after_streak: int
    penalty_value: float


def _results_root() -> Path:
    return _paper_root() / "results" / "oracle_incumbent_policy_slice"


def _policy_specs_from_suite(suite: dict[str, Any]) -> list[PolicySpec]:
    specs: list[PolicySpec] = []
    for record in suite.get("policies", []):
        specs.append(
            PolicySpec(
                id=str(record["id"]),
                label=str(record["label"]),
                incumbent_policy=str(record["incumbent_policy"]),
                cooldown_rounds=int(record.get("cooldown_rounds", 0)),
                penalty_after_streak=int(record.get("incumbent_penalty_after_streak", 999)),
                penalty_value=float(record.get("incumbent_penalty", 0.0)),
            )
        )
    if not specs:
        raise ValueError("policies must contain at least one policy spec")
    return specs


def _oracle_feedback_request_from_field(
    scored_candidates: list[dict[str, Any]],
    *,
    score_field: str,
    critique_text: str,
) -> FeedbackRequest:
    sorted_rows = sorted(scored_candidates, key=lambda row: (-float(row[score_field]), row["candidate_id"]))
    winner_id = sorted_rows[0]["candidate_id"]
    feedback_mode = str(sorted_rows[0].get("oracle_feedback_mode", FeedbackType.winner_only.value))
    feedback_type = FeedbackType(feedback_mode)

    if feedback_type == FeedbackType.scalar_rating:
        scores = [float(row[score_field]) for row in sorted_rows]
        lo = min(scores)
        hi = max(scores)
        if hi - lo < 1e-8:
            ratings = {row["candidate_id"]: 3.0 for row in sorted_rows}
        else:
            ratings = {
                row["candidate_id"]: round(1.0 + (4.0 * ((float(row[score_field]) - lo) / (hi - lo))), 4)
                for row in sorted_rows
            }
        return FeedbackRequest(feedback_type=feedback_type, payload={"ratings": ratings}, critique_text=critique_text)

    if feedback_type == FeedbackType.top_k:
        ranking = [row["candidate_id"] for row in sorted_rows]
        return FeedbackRequest(feedback_type=feedback_type, payload={"ranking": ranking}, critique_text=critique_text)

    if feedback_type == FeedbackType.pairwise:
        loser_id = sorted_rows[-1]["candidate_id"]
        return FeedbackRequest(
            feedback_type=feedback_type,
            payload={"winner_candidate_id": winner_id, "loser_candidate_id": loser_id},
            critique_text=critique_text,
        )

    return FeedbackRequest(
        feedback_type=FeedbackType.winner_only,
        payload={"winner_candidate_id": winner_id},
        critique_text=critique_text,
    )


def _select_policy_candidates(
    scored_candidates: list[dict[str, Any]],
    *,
    policy: PolicySpec,
    repeated_selected_image_streak: int,
) -> list[dict[str, Any]]:
    if policy.incumbent_policy == "hard_cooldown":
        if policy.cooldown_rounds > 0 and repeated_selected_image_streak >= policy.cooldown_rounds:
            challengers = [row for row in scored_candidates if not row.get("carried_forward")]
            return challengers or scored_candidates
        return scored_candidates
    return scored_candidates


def _policy_adjusted_score(
    row: dict[str, Any],
    *,
    policy: PolicySpec,
    repeated_selected_image_streak: int,
) -> float:
    score = float(row["clip_score"])
    if policy.incumbent_policy == "soft_penalty":
        if row.get("carried_forward") and repeated_selected_image_streak >= policy.penalty_after_streak:
            score -= policy.penalty_value
    return score


def _build_policy_svg(curve_rows: list[dict[str, Any]], output_path: Path) -> None:
    width = 1160
    height = 780
    left = 92
    right = 60
    top = 70
    panel_gap = 54
    panel_height = 248
    plot_width = width - left - right
    top_panel_y = 116
    bottom_panel_y = top_panel_y + panel_height + panel_gap
    rounds = sorted({int(row["round_index"]) for row in curve_rows})
    policy_ids = list(dict.fromkeys(str(row["policy_id"]) for row in curve_rows))
    colors = {
        "carry_forward_baseline": "#6b4f2a",
        "soft_penalty": "#0f766e",
        "hard_cooldown": "#b45309",
    }
    dash = {
        "carry_forward_baseline": "",
        "soft_penalty": "",
        "hard_cooldown": "10 6",
    }

    def x_pos(round_index: int) -> float:
        if len(rounds) == 1:
            return left + plot_width / 2
        return left + ((round_index - min(rounds)) / (max(rounds) - min(rounds))) * plot_width

    clip_values = [float(row["mean_best_clip"]) for row in curve_rows]
    clip_bases = [float(row["mean_baseline_clip"]) for row in curve_rows]
    dino_values = [float(row["mean_best_dinov2"]) for row in curve_rows]
    dino_bases = [float(row["mean_baseline_dinov2"]) for row in curve_rows]
    clip_lo = min(min(clip_values), min(clip_bases)) - 0.02
    clip_hi = max(max(clip_values), max(clip_bases)) + 0.02
    dino_lo = min(min(dino_values), min(dino_bases)) - 0.02
    dino_hi = max(max(dino_values), max(dino_bases)) + 0.02

    def y_pos(score: float, y0: float, lo: float, hi: float) -> float:
        if hi == lo:
            return y0 + panel_height / 2
        return y0 + (1 - ((score - lo) / (hi - lo))) * panel_height

    def series(points: list[tuple[int, float]], y0: float, lo: float, hi: float) -> str:
        return " ".join(f"{x_pos(r):.1f},{y_pos(v, y0, lo, hi):.1f}" for r, v in points)

    svg = f"""<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}" role="img" aria-labelledby="title desc">
  <title id="title">Incumbent-policy oracle comparison</title>
  <desc id="desc">Budget-matched oracle comparison across baseline carry-forward, soft incumbent penalty, and hard cooldown policies under CLIP and DINOv2 evaluation.</desc>
  <style>
    .bg {{ fill: #fbfaf6; }}
    .axis {{ stroke: #475467; stroke-width: 2.0; }}
    .grid {{ stroke: #ddd4c5; stroke-width: 1.0; }}
    .title {{ font: 700 28px Georgia, 'Times New Roman', serif; fill: #1f2937; }}
    .subtitle {{ font: 16px Georgia, 'Times New Roman', serif; fill: #334155; }}
    .tick {{ font: 14px Georgia, 'Times New Roman', serif; fill: #334155; }}
    .panel {{ font: 700 18px Georgia, 'Times New Roman', serif; fill: #1f2937; }}
    .legend {{ font: 14px Georgia, 'Times New Roman', serif; fill: #1f2937; }}
    .baseline {{ fill: none; stroke: #94a3b8; stroke-width: 1.8; stroke-dasharray: 8 6; opacity: 0.75; }}
  </style>
  <rect class="bg" width="{width}" height="{height}"/>
  <text class="title" x="72" y="46">Budget-Matched Incumbent-Policy Oracle Slice</text>
  <text class="subtitle" x="72" y="72">Same targets, same rounds, same sampler/updater family; only incumbent handling changes.</text>
"""
    for y0, lo, hi, title_text, best_field, base_field in [
        (top_panel_y, clip_lo, clip_hi, "CLIP cosine to target", "mean_best_clip", "mean_baseline_clip"),
        (bottom_panel_y, dino_lo, dino_hi, "DINOv2 cosine to target", "mean_best_dinov2", "mean_baseline_dinov2"),
    ]:
        svg += f'  <text class="panel" x="{left}" y="{y0 - 18}">{title_text}</text>\n'
        svg += f'  <line class="axis" x1="{left}" y1="{y0}" x2="{left}" y2="{y0 + panel_height}"/>\n'
        svg += f'  <line class="axis" x1="{left}" y1="{y0 + panel_height}" x2="{left + plot_width}" y2="{y0 + panel_height}"/>\n'
        for step in range(5):
            tick_value = lo + ((hi - lo) * step / 4)
            y = y_pos(tick_value, y0, lo, hi)
            svg += f'  <line class="grid" x1="{left}" y1="{y:.1f}" x2="{left + plot_width}" y2="{y:.1f}"/>\n'
            svg += f'  <text class="tick" x="{left - 10}" y="{y + 4:.1f}" text-anchor="end">{tick_value:.3f}</text>\n'
        for round_index in rounds:
            x = x_pos(round_index)
            svg += f'  <line class="grid" x1="{x:.1f}" y1="{y0}" x2="{x:.1f}" y2="{y0 + panel_height}"/>\n'
            svg += f'  <text class="tick" x="{x:.1f}" y="{y0 + panel_height + 22}" text-anchor="middle">{round_index}</text>\n'
        baseline_points = [(int(row["round_index"]), float(row[base_field])) for row in curve_rows if str(row["policy_id"]) == policy_ids[0]]
        svg += f'  <polyline class="baseline" points="{series(baseline_points, y0, lo, hi)}"/>\n'
        for policy_id in policy_ids:
            points = [
                (int(row["round_index"]), float(row[best_field]))
                for row in curve_rows
                if str(row["policy_id"]) == policy_id
            ]
            stroke = colors.get(policy_id, "#334155")
            dasharray = dash.get(policy_id, "")
            dash_attr = f' stroke-dasharray="{dasharray}"' if dasharray else ""
            svg += (
                f'  <polyline fill="none" stroke="{stroke}" stroke-width="3.4"{dash_attr} '
                f'points="{series(points, y0, lo, hi)}"/>\n'
            )

    legend_x = width - 360
    legend_y = 84
    for index, policy_id in enumerate(policy_ids):
        y = legend_y + index * 26
        stroke = colors.get(policy_id, "#334155")
        dasharray = dash.get(policy_id, "")
        dash_attr = f' stroke-dasharray="{dasharray}"' if dasharray else ""
        label = policy_id.replace("_", " ")
        svg += f'  <line x1="{legend_x}" y1="{y}" x2="{legend_x + 32}" y2="{y}" stroke="{stroke}" stroke-width="3.4"{dash_attr}/>\n'
        svg += f'  <text class="legend" x="{legend_x + 42}" y="{y + 5}">{label}</text>\n'
    svg += f'  <line x1="{legend_x}" y1="{legend_y + len(policy_ids) * 26 + 8}" x2="{legend_x + 32}" y2="{legend_y + len(policy_ids) * 26 + 8}" class="baseline"/>\n'
    svg += f'  <text class="legend" x="{legend_x + 42}" y="{legend_y + len(policy_ids) * 26 + 13}">prompt-only baseline</text>\n'
    svg += "</svg>\n"
    _write_text(output_path, svg)


def _run_policy_target_repeat(
    *,
    output_dir: Path,
    suite: dict[str, Any],
    policy: PolicySpec,
    target: OracleTarget,
    repeat_index: int,
    metric_specs: list[MetricSpec],
    metric_objects: dict[str, Any],
    backend: str,
) -> dict[str, Any]:
    config = _strategy_config_from_suite(suite)
    run_root = output_dir / "runs" / policy.id / target.id / f"repeat_{repeat_index + 1}"
    runtime_root = run_root / "runtime"
    repository = JsonRepository(data_dir=runtime_root)
    generator = build_generation_engine(
        backend=backend,
        artifacts_dir=repository.artifacts_dir,
        num_inference_steps=config.num_inference_steps,
    )
    orchestrator = Orchestrator(repository=repository, generator=generator)
    target_dir = output_dir / "targets"
    target_name = Path(target.image_url.split("/")[-1]).name or f"{target.id}.jpg"
    target_path = target_dir / target_name
    _download(target.image_url, target_path)
    target_embeddings = {spec.short_name: metric_objects[spec.short_name].embed_image(target_path) for spec in metric_specs}

    experiment = orchestrator.create_experiment(
        ExperimentCreate(
            name=f"Oracle incumbent policy / {policy.label} / {target.label} / r{repeat_index + 1}",
            description=f"Budget-matched oracle incumbent-policy comparison for {target.id}",
            config=config,
        )
    )
    session = orchestrator.create_session(
        SessionCreate(experiment_id=experiment.id, prompt=target.caption, negative_prompt=target.negative_prompt)
    )

    max_rounds = int(suite.get("max_rounds", 8))
    round_rows: list[dict[str, Any]] = []
    candidate_rows: list[dict[str, Any]] = []
    baseline_scores = {spec.short_name: None for spec in metric_specs}
    first_round_best_scores = {spec.short_name: None for spec in metric_specs}
    final_best_scores = {spec.short_name: None for spec in metric_specs}
    repeated_selected_image_streak = 0
    last_selected_image_path: str | None = None
    selected_image_paths: list[str] = []

    for round_index in range(1, max_rounds + 1):
        orchestrator.generate_round(session.id)
        round_obj = orchestrator.get_session_rounds(session.id)[-1]
        scored_candidates: list[dict[str, Any]] = []
        for candidate in round_obj.candidates:
            image_path = _artifact_path(runtime_root, candidate.image_path)
            record: dict[str, Any] = {
                "policy_id": policy.id,
                "policy_label": policy.label,
                "target_id": target.id,
                "target_label": target.label,
                "repeat_index": repeat_index,
                "session_id": session.id,
                "round_id": round_obj.id,
                "round_index": round_index,
                "candidate_id": candidate.id,
                "candidate_index": candidate.candidate_index,
                "sampler_role": candidate.sampler_role,
                "seed": candidate.seed,
                "image_path": str(image_path),
                "selected": False,
                "carried_forward": bool(candidate.generation_params.get("carried_forward", False)),
                "baseline_prompt": bool(candidate.generation_params.get("baseline_prompt", False)),
                "oracle_feedback_mode": session.config.feedback_mode.value,
            }
            image_embeddings = {spec.short_name: metric_objects[spec.short_name].embed_image(image_path) for spec in metric_specs}
            for spec in metric_specs:
                score = metric_objects[spec.short_name].cosine(target_embeddings[spec.short_name], image_embeddings[spec.short_name])
                record[f"{spec.short_name}_score"] = round(score, 6)
                if record["baseline_prompt"] and baseline_scores[spec.short_name] is None:
                    baseline_scores[spec.short_name] = score
            record["selection_score"] = round(
                _policy_adjusted_score(record, policy=policy, repeated_selected_image_streak=repeated_selected_image_streak),
                6,
            )
            candidate_rows.append(record)
            scored_candidates.append(record)

        eligible_candidates = _select_policy_candidates(
            scored_candidates,
            policy=policy,
            repeated_selected_image_streak=repeated_selected_image_streak,
        )
        winner = max(eligible_candidates, key=lambda row: (float(row["selection_score"]), float(row["clip_score"])))
        winner["selected"] = True
        winner_image_path = str(winner["image_path"])
        selected_image_paths.append(winner_image_path)
        if last_selected_image_path == winner_image_path:
            repeated_selected_image_streak += 1
        else:
            repeated_selected_image_streak = 1
            last_selected_image_path = winner_image_path
        round_record = {
            "policy_id": policy.id,
            "policy_label": policy.label,
            "target_id": target.id,
            "target_label": target.label,
            "repeat_index": repeat_index,
            "session_id": session.id,
            "round_id": round_obj.id,
            "round_index": round_index,
            "winner_candidate_id": winner["candidate_id"],
            "winner_sampler_role": winner["sampler_role"],
            "candidate_count": len(scored_candidates),
            "selection_score": round(float(winner["selection_score"]), 6),
        }
        for spec in metric_specs:
            best_round_score = max(float(row[f"{spec.short_name}_score"]) for row in scored_candidates)
            round_record[f"best_{spec.short_name}"] = round(best_round_score, 6)
            round_record[f"baseline_{spec.short_name}"] = round(float(baseline_scores[spec.short_name] or 0.0), 6)
            if round_index == 1:
                first_round_best_scores[spec.short_name] = best_round_score
            if round_index == max_rounds:
                final_best_scores[spec.short_name] = best_round_score
        round_rows.append(round_record)

        if round_index < max_rounds:
            feedback_candidates = eligible_candidates if policy.incumbent_policy == "hard_cooldown" else scored_candidates
            for row in feedback_candidates:
                row["policy_feedback_score"] = round(
                    _policy_adjusted_score(row, policy=policy, repeated_selected_image_streak=repeated_selected_image_streak),
                    6,
                )
            orchestrator.submit_feedback(
                round_obj.id,
                _oracle_feedback_request_from_field(
                    feedback_candidates,
                    score_field="policy_feedback_score",
                    critique_text=f"Oracle feedback derived from CLIP target-image similarity under the {policy.label} incumbent policy.",
                ),
            )

    trace_report_path = orchestrator.generate_trace_report(session.id)
    copied_report = _copy_trace_report(trace_report_path, run_root)
    plateau_last3 = 1 if len(selected_image_paths) >= 3 and len(set(selected_image_paths[-3:])) == 1 else 0
    repeated_any = 1 if len(set(selected_image_paths)) < len(selected_image_paths) else 0
    unique_ratio = round(len(set(selected_image_paths)) / max(1, len(selected_image_paths)), 6)
    selected_clip_scores = [
        float(next(row["clip_score"] for row in candidate_rows if row["round_id"] == round_row["round_id"] and row["candidate_id"] == round_row["winner_candidate_id"]))
        for round_row in round_rows
    ]
    improve_after_round4 = 1 if len(selected_clip_scores) > 4 and max(selected_clip_scores[4:]) > max(selected_clip_scores[:4]) else 0

    summary: dict[str, Any] = {
        "policy_id": policy.id,
        "policy_label": policy.label,
        "target_id": target.id,
        "target_label": target.label,
        "repeat_index": repeat_index,
        "target_path": str(target_path),
        "target_attribution": target.attribution,
        "session_id": session.id,
        "experiment_id": experiment.id,
        "trace_report": str(copied_report.relative_to(output_dir)),
        "runtime_root": str(runtime_root.relative_to(output_dir)),
        "max_rounds": max_rounds,
        "repeated_any": repeated_any,
        "plateau_last3": plateau_last3,
        "unique_selected_ratio": unique_ratio,
        "improve_after_round4": improve_after_round4,
    }
    for spec in metric_specs:
        baseline = float(baseline_scores[spec.short_name] or 0.0)
        final_best = float(final_best_scores[spec.short_name] or 0.0)
        first_best = float(first_round_best_scores[spec.short_name] or 0.0)
        summary[f"baseline_{spec.short_name}"] = round(baseline, 6)
        summary[f"first_round_best_{spec.short_name}"] = round(first_best, 6)
        summary[f"final_best_{spec.short_name}"] = round(final_best, 6)
        summary[f"delta_{spec.short_name}"] = round(final_best - baseline, 6)
    _write_json(run_root / "summary.json", summary)
    return {"summary": summary, "round_rows": round_rows, "candidate_rows": candidate_rows}


def _build_analysis(
    output_dir: Path,
    target_rows: list[dict[str, Any]],
    round_rows: list[dict[str, Any]],
    metric_specs: list[MetricSpec],
    policy_specs: list[PolicySpec],
) -> None:
    analysis_root = output_dir / "analysis"
    analysis_root.mkdir(parents=True, exist_ok=True)
    rounds_by_policy_round: dict[tuple[str, int], list[dict[str, Any]]] = {}
    for row in round_rows:
        key = (str(row["policy_id"]), int(row["round_index"]))
        rounds_by_policy_round.setdefault(key, []).append(row)

    curve_rows: list[dict[str, Any]] = []
    for policy in policy_specs:
        for round_index in sorted({key[1] for key in rounds_by_policy_round if key[0] == policy.id}):
            rows = rounds_by_policy_round[(policy.id, round_index)]
            record: dict[str, Any] = {"policy_id": policy.id, "policy_label": policy.label, "round_index": round_index}
            for spec in metric_specs:
                best_values = [float(row[f"best_{spec.short_name}"]) for row in rows]
                baseline_values = [float(row[f"baseline_{spec.short_name}"]) for row in rows]
                record[f"mean_best_{spec.short_name}"] = round(_safe_mean(best_values), 6)
                record[f"std_best_{spec.short_name}"] = round(_safe_std(best_values), 6)
                record[f"mean_baseline_{spec.short_name}"] = round(_safe_mean(baseline_values), 6)
            curve_rows.append(record)
    curve_fields = ["policy_id", "policy_label", "round_index"]
    for spec in metric_specs:
        curve_fields.extend([f"mean_best_{spec.short_name}", f"std_best_{spec.short_name}", f"mean_baseline_{spec.short_name}"])
    _write_csv(analysis_root / "round_curve.csv", curve_rows, curve_fields)
    _build_policy_svg(curve_rows, analysis_root / "oracle_incumbent_policy_slice.svg")

    policy_summary_rows: list[dict[str, Any]] = []
    for policy in policy_specs:
        rows = [row for row in target_rows if str(row["policy_id"]) == policy.id]
        summary: dict[str, Any] = {"policy_id": policy.id, "policy_label": policy.label, "runs": len(rows)}
        for spec in metric_specs:
            finals = [float(row[f"final_best_{spec.short_name}"]) for row in rows]
            deltas = [float(row[f"delta_{spec.short_name}"]) for row in rows]
            summary[f"mean_final_{spec.short_name}"] = round(_safe_mean(finals), 6)
            summary[f"std_final_{spec.short_name}"] = round(_safe_std(finals), 6)
            summary[f"mean_delta_{spec.short_name}"] = round(_safe_mean(deltas), 6)
            summary[f"std_delta_{spec.short_name}"] = round(_safe_std(deltas), 6)
        summary["plateau_last3_runs"] = int(sum(int(row["plateau_last3"]) for row in rows))
        summary["repeated_any_runs"] = int(sum(int(row["repeated_any"]) for row in rows))
        summary["improve_after_round4_runs"] = int(sum(int(row["improve_after_round4"]) for row in rows))
        summary["mean_unique_selected_ratio"] = round(_safe_mean([float(row["unique_selected_ratio"]) for row in rows]), 6)
        policy_summary_rows.append(summary)

    summary_fields = ["policy_id", "policy_label", "runs"]
    for spec in metric_specs:
        summary_fields.extend([f"mean_final_{spec.short_name}", f"std_final_{spec.short_name}", f"mean_delta_{spec.short_name}", f"std_delta_{spec.short_name}"])
    summary_fields.extend(["plateau_last3_runs", "repeated_any_runs", "improve_after_round4_runs", "mean_unique_selected_ratio"])
    _write_csv(analysis_root / "policy_summary.csv", policy_summary_rows, summary_fields)
    _write_csv(output_dir / "tables" / "summary.csv", policy_summary_rows, summary_fields)

    lines = []
    for row in policy_summary_rows:
        lines.append(
            f"| {row['policy_label']} | {row['runs']} | {float(row['mean_final_clip']):.3f} ± {float(row['std_final_clip']):.3f} | "
            f"{float(row['mean_final_dinov2']):.3f} ± {float(row['std_final_dinov2']):.3f} | "
            f"{int(row['improve_after_round4_runs'])}/{int(row['runs'])} | {int(row['plateau_last3_runs'])}/{int(row['runs'])} | "
            f"{float(row['mean_unique_selected_ratio']):.3f} |"
        )

    summary_md = (
        "# Incumbent-Policy Oracle Slice\n\n"
        "This budget-matched oracle slice compares three incumbent-handling policies under one fixed proposal and update family.\n\n"
        "## Scope\n\n"
        f"- policies: `{len(policy_specs)}`\n"
        f"- runs: `{len(target_rows)}`\n"
        f"- rounds: `{len(round_rows)}`\n"
        f"- targets: `{len(set(str(row['target_id']) for row in target_rows))}`\n\n"
        "## Policy summary\n\n"
        "| policy | runs | final CLIP (mean ± sd) | final DINOv2 (mean ± sd) | improves after round 4 | last-3 identical-image plateaus | mean unique selected-image ratio |\n"
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: |\n"
        + "\n".join(lines)
        + "\n\n## Interpretation boundary\n\n"
        "- all policies use the same targets, model family, candidate budget, and metric pair\n"
        "- CLIP still drives oracle selection, while DINOv2 remains a secondary evaluator\n"
        "- this slice compares incumbent-handling tradeoffs, not general image quality\n"
        "- later-round movement and final proxy recovery should be read together, not separately\n\n"
        "## Figure\n\n![Budget-matched incumbent-policy oracle slice](oracle_incumbent_policy_slice.svg)\n"
    )
    _write_text(analysis_root / "analysis_summary.md", summary_md)
    _markdown_to_html("Incumbent-Policy Oracle Slice", summary_md, analysis_root / "analysis_summary.html")
    shutil.copy2(analysis_root / "oracle_incumbent_policy_slice.svg", _paper_root() / "figures" / "figure_12_incumbent_policy_slice.svg")


def main() -> int:
    parser = argparse.ArgumentParser(description="Run a budget-matched oracle incumbent-policy comparison slice.")
    parser.add_argument("--suite", type=Path, default=_paper_root() / "protocols" / "oracle_incumbent_policy_slice.yaml")
    parser.add_argument("--output-dir", type=Path, default=_results_root())
    parser.add_argument("--backend", choices=["diffusers", "mock", "auto"], default="diffusers")
    args = parser.parse_args()

    suite = _read_yaml(args.suite)
    output_dir = args.output_dir
    output_dir.mkdir(parents=True, exist_ok=True)
    _write_text(output_dir / "protocol_snapshot.yaml", yaml.safe_dump(suite, sort_keys=False, allow_unicode=False))

    metric_specs = _metric_specs_from_suite(suite)
    oracle_model_id = str(suite.get("oracle_model", "openai/clip-vit-base-patch32"))
    metric_objects = _build_metric_objects(metric_specs, oracle_model_id)
    targets = _load_targets(suite)
    policies = _policy_specs_from_suite(suite)
    repeats = int(suite.get("repeats_per_target", 2))

    target_rows: list[dict[str, Any]] = []
    round_rows: list[dict[str, Any]] = []
    candidate_rows: list[dict[str, Any]] = []
    for policy in policies:
        for target in targets:
            for repeat_index in range(repeats):
                result = _run_policy_target_repeat(
                    output_dir=output_dir,
                    suite=suite,
                    policy=policy,
                    target=target,
                    repeat_index=repeat_index,
                    metric_specs=metric_specs,
                    metric_objects=metric_objects,
                    backend=args.backend,
                )
                target_rows.append(result["summary"])
                round_rows.extend(result["round_rows"])
                candidate_rows.extend(result["candidate_rows"])

    target_fields = [
        "policy_id",
        "policy_label",
        "target_id",
        "target_label",
        "repeat_index",
        "target_path",
        "target_attribution",
        "session_id",
        "experiment_id",
        "trace_report",
        "runtime_root",
        "max_rounds",
        "repeated_any",
        "plateau_last3",
        "unique_selected_ratio",
        "improve_after_round4",
    ]
    for spec in metric_specs:
        target_fields.extend([f"baseline_{spec.short_name}", f"first_round_best_{spec.short_name}", f"final_best_{spec.short_name}", f"delta_{spec.short_name}"])
    _write_csv(output_dir / "tables" / "targets.csv", target_rows, target_fields)

    round_fields = ["policy_id", "policy_label", "target_id", "target_label", "repeat_index", "session_id", "round_id", "round_index", "winner_candidate_id", "winner_sampler_role", "candidate_count", "selection_score"]
    for spec in metric_specs:
        round_fields.extend([f"best_{spec.short_name}", f"baseline_{spec.short_name}"])
    _write_csv(output_dir / "tables" / "rounds.csv", round_rows, round_fields)

    candidate_fields = [
        "policy_id",
        "policy_label",
        "target_id",
        "target_label",
        "repeat_index",
        "session_id",
        "round_id",
        "round_index",
        "candidate_id",
        "candidate_index",
        "sampler_role",
        "seed",
        "image_path",
        "selected",
        "carried_forward",
        "baseline_prompt",
        "selection_score",
    ] + [f"{spec.short_name}_score" for spec in metric_specs]
    _write_csv(output_dir / "tables" / "candidates.csv", candidate_rows, candidate_fields)

    _write_json(
        output_dir / "manifest.json",
        {
            "suite_name": suite.get("suite_name", "oracle_incumbent_policy_slice"),
            "description": suite.get("description", ""),
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "policy_count": len(policies),
            "target_count": len(targets),
            "repeats_per_target": repeats,
            "run_count": len(target_rows),
            "round_count": len(round_rows),
            "candidate_count": len(candidate_rows),
            "oracle_model": oracle_model_id,
            "evaluation_models": [spec.id for spec in metric_specs],
            "backend": args.backend,
        },
    )
    _build_analysis(output_dir, target_rows, round_rows, metric_specs, policies)
    _write_text(
        output_dir / "README.md",
        (
            "# Incumbent-Policy Oracle Slice Results\n\n"
            "This directory contains a budget-matched oracle comparison of baseline carry-forward, soft incumbent penalty, and hard cooldown policies.\n\n"
            f"Current bundle summary: {len(target_rows)} runs, {len(round_rows)} rounds, and {len(candidate_rows)} candidate rows.\n"
        ),
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
