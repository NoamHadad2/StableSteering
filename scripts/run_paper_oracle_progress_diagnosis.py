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
from run_paper_oracle_multimetric_repeated import DINOv2Metric, MetricSpec, _metric_specs_from_suite
from run_paper_oracle_target_recovery import (
    ClipOracle,
    OracleTarget,
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
class PolicySpec:
    id: str
    label: str
    sampler: str
    updater: str
    feedback_mode: str
    oracle_policy: str
    candidate_count: int | None = None
    trust_radius: float | None = None
    anchor_strength: float | None = None


def _results_root() -> Path:
    return _paper_root() / "results" / "oracle_progress_diagnosis"


def _policy_specs_from_suite(suite: dict[str, Any]) -> list[PolicySpec]:
    specs: list[PolicySpec] = []
    for record in suite.get("policies", []):
        specs.append(
            PolicySpec(
                id=str(record["id"]),
                label=str(record["label"]),
                sampler=str(record["sampler"]),
                updater=str(record["updater"]),
                feedback_mode=str(record["feedback_mode"]),
                oracle_policy=str(record["oracle_policy"]),
                candidate_count=int(record["candidate_count"]) if "candidate_count" in record else None,
                trust_radius=float(record["trust_radius"]) if "trust_radius" in record else None,
                anchor_strength=float(record["anchor_strength"]) if "anchor_strength" in record else None,
            )
        )
    if not specs:
        raise ValueError("policies must contain at least one policy")
    return specs


def _strategy_config(base_suite: dict[str, Any], policy: PolicySpec) -> StrategyConfig:
    payload = dict(base_suite.get("fixed_conditions", {}))
    payload["sampler"] = policy.sampler
    payload["updater"] = policy.updater
    payload["feedback_mode"] = policy.feedback_mode
    if policy.candidate_count is not None:
        payload["candidate_count"] = policy.candidate_count
    if policy.trust_radius is not None:
        payload["trust_radius"] = policy.trust_radius
    if policy.anchor_strength is not None:
        payload["anchor_strength"] = policy.anchor_strength
    image_size = payload.get("image_size", "512x512")
    if isinstance(image_size, list) and len(image_size) == 2:
        payload["image_size"] = f"{image_size[0]}x{image_size[1]}"
    return StrategyConfig.model_validate(payload)


def _safe_mean(values: list[float]) -> float:
    return sum(values) / len(values) if values else 0.0


def _rescale(values: list[float]) -> list[float]:
    if not values:
        return []
    lo = min(values)
    hi = max(values)
    if hi - lo < 1e-8:
        return [1.0 for _ in values]
    return [(value - lo) / (hi - lo) for value in values]


def _build_metric_objects(metric_specs: list[MetricSpec], oracle_model_id: str) -> dict[str, Any]:
    metric_objects: dict[str, Any] = {}
    for spec in metric_specs:
        if spec.kind == "clip":
            metric_objects[spec.short_name] = ClipOracle(spec.id)
        elif spec.kind == "dinov2":
            metric_objects[spec.short_name] = DINOv2Metric(spec.id, device="cpu")
        else:
            raise ValueError(f"Unsupported metric kind: {spec.kind}")
    if "clip" not in metric_objects:
        metric_objects["clip"] = ClipOracle(oracle_model_id)
    return metric_objects


def _oracle_score_candidates(
    scored_candidates: list[dict[str, Any]],
    *,
    policy: PolicySpec,
    margin_epsilon: float,
    target_clip_embedding: list[float] | Any = None,
    incumbent_clip_embedding: list[float] | Any = None,
) -> list[dict[str, Any]]:
    if policy.oracle_policy == "clip_only":
        for row in scored_candidates:
            row["oracle_score"] = float(row["clip_score"])
        return scored_candidates

    if policy.oracle_policy == "pareto_frontier_mix":
        return _oracle_score_candidates_pareto(scored_candidates)

    if policy.oracle_policy == "clip_advantage_novelty_mix":
        return _oracle_score_candidates_advantage(
            scored_candidates,
            margin_epsilon=margin_epsilon,
        )

    if policy.oracle_policy == "clip_directional_mix":
        return _oracle_score_candidates_directional(
            scored_candidates,
            target_clip_embedding=target_clip_embedding,
            incumbent_clip_embedding=incumbent_clip_embedding,
            margin_epsilon=margin_epsilon,
        )

    if policy.oracle_policy != "clip_margin_mix":
        raise ValueError(f"Unsupported oracle policy: {policy.oracle_policy}")

    incumbent = next((row for row in scored_candidates if row.get("carried_forward")), None)
    challengers = [row for row in scored_candidates if not row.get("carried_forward")]
    if incumbent is None or not challengers:
        for row in scored_candidates:
            row["oracle_score"] = float(row["clip_score"])
        return scored_candidates

    incumbent_clip = float(incumbent["clip_score"])
    best_challenger_clip = max(float(row["clip_score"]) for row in challengers)
    if best_challenger_clip < incumbent_clip - margin_epsilon:
        for row in scored_candidates:
            row["oracle_score"] = float(row["clip_score"])
        return scored_candidates

    clip_scaled = _rescale([float(row["clip_score"]) for row in scored_candidates])
    dino_scaled = _rescale([float(row["dinov2_score"]) for row in scored_candidates])
    novelty_scaled = _rescale([float(row["novelty_to_incumbent"]) for row in scored_candidates])
    for row, clip_value, dino_value, novelty_value in zip(
        scored_candidates,
        clip_scaled,
        dino_scaled,
        novelty_scaled,
        strict=True,
    ):
        blended = (0.68 * clip_value) + (0.22 * dino_value) + (0.10 * novelty_value)
        if row.get("carried_forward"):
            blended -= 0.025
        row["oracle_score"] = blended
    return scored_candidates


def _oracle_score_candidates_advantage(
    scored_candidates: list[dict[str, Any]],
    *,
    margin_epsilon: float,
) -> list[dict[str, Any]]:
    incumbent = next((row for row in scored_candidates if row.get("carried_forward")), None)
    if incumbent is None:
        for row in scored_candidates:
            row["oracle_score"] = float(row["clip_score"])
        return scored_candidates

    incumbent_clip = float(incumbent["clip_score"])
    clip_scaled = _rescale([float(row["clip_score"]) for row in scored_candidates])
    novelty_scaled = _rescale([float(row["novelty_to_incumbent"]) for row in scored_candidates])
    advantage_scaled = _rescale([float(row["clip_score"]) - incumbent_clip for row in scored_candidates])
    any_positive_advantage = any((float(row["clip_score"]) - incumbent_clip) > (margin_epsilon * 0.5) for row in scored_candidates if not row.get("carried_forward"))
    for row, clip_value, novelty_value, advantage_value in zip(
        scored_candidates,
        clip_scaled,
        novelty_scaled,
        advantage_scaled,
        strict=True,
    ):
        blended = (0.52 * clip_value) + (0.33 * advantage_value) + (0.15 * novelty_value)
        if row.get("carried_forward") and any_positive_advantage:
            blended -= 0.04
        row["oracle_score"] = blended
    return scored_candidates


def _projection_progress(candidate_embedding: Any, incumbent_embedding: Any, target_embedding: Any) -> float:
    incumbent_to_target = [float(target) - float(incumbent) for target, incumbent in zip(target_embedding, incumbent_embedding, strict=False)]
    incumbent_to_candidate = [float(candidate) - float(incumbent) for candidate, incumbent in zip(candidate_embedding, incumbent_embedding, strict=False)]
    target_norm = math.sqrt(sum(value * value for value in incumbent_to_target))
    if target_norm < 1e-8:
        return 0.0
    return sum(left * right for left, right in zip(incumbent_to_candidate, incumbent_to_target, strict=False)) / target_norm


def _oracle_score_candidates_directional(
    scored_candidates: list[dict[str, Any]],
    *,
    target_clip_embedding: Any,
    incumbent_clip_embedding: Any = None,
    margin_epsilon: float,
) -> list[dict[str, Any]]:
    if incumbent_clip_embedding is None:
        for row in scored_candidates:
            row["oracle_score"] = float(row["clip_score"])
        return scored_candidates

    clip_scaled = _rescale([float(row["clip_score"]) for row in scored_candidates])
    novelty_scaled = _rescale([float(row["novelty_to_incumbent"]) for row in scored_candidates])
    directional_values = [
        _projection_progress(row["_clip_embedding"], incumbent_clip_embedding, target_clip_embedding)
        for row in scored_candidates
    ]
    directional_scaled = _rescale(directional_values)
    any_positive_directional = any(value > margin_epsilon for row, value in zip(scored_candidates, directional_values, strict=True) if not row.get("carried_forward"))
    for row, clip_value, novelty_value, directional_value in zip(
        scored_candidates,
        clip_scaled,
        novelty_scaled,
        directional_scaled,
        strict=True,
    ):
        blended = (0.45 * clip_value) + (0.35 * directional_value) + (0.20 * novelty_value)
        if row.get("carried_forward") and any_positive_directional:
            blended -= 0.035
        row["oracle_score"] = blended
    return scored_candidates


def _oracle_score_candidates_pareto(scored_candidates: list[dict[str, Any]]) -> list[dict[str, Any]]:
    clip_scaled = _rescale([float(row["clip_score"]) for row in scored_candidates])
    dino_scaled = _rescale([float(row["dinov2_score"]) for row in scored_candidates])
    novelty_scaled = _rescale([float(row["novelty_to_incumbent"]) for row in scored_candidates])
    metrics = [
        {
            "clip": clip_value,
            "dino": dino_value,
            "novelty": novelty_value,
        }
        for clip_value, dino_value, novelty_value in zip(clip_scaled, dino_scaled, novelty_scaled, strict=True)
    ]
    for index, row in enumerate(scored_candidates):
        domination_count = 0
        current = metrics[index]
        for other_index, other in enumerate(metrics):
            if other_index == index:
                continue
            dominates = (
                other["clip"] >= current["clip"]
                and other["dino"] >= current["dino"]
                and other["novelty"] >= current["novelty"]
                and (
                    other["clip"] > current["clip"]
                    or other["dino"] > current["dino"]
                    or other["novelty"] > current["novelty"]
                )
            )
            if dominates:
                domination_count += 1
        pareto_bonus = 1.0 / (1.0 + domination_count)
        blended = (0.42 * current["clip"]) + (0.33 * current["dino"]) + (0.25 * current["novelty"])
        if row.get("carried_forward"):
            blended -= 0.03
        row["oracle_score"] = (0.72 * pareto_bonus) + (0.28 * blended)
    return scored_candidates


def _oracle_feedback_request(scored_candidates: list[dict[str, Any]], feedback_mode: str, critique_text: str) -> FeedbackRequest:
    sorted_rows = sorted(scored_candidates, key=lambda row: (-float(row["oracle_score"]), row["candidate_id"]))
    winner_id = sorted_rows[0]["candidate_id"]
    feedback_type = FeedbackType(feedback_mode)
    if feedback_type == FeedbackType.scalar_rating:
        oracle_scores = [float(row["oracle_score"]) for row in sorted_rows]
        lo = min(oracle_scores)
        hi = max(oracle_scores)
        if hi - lo < 1e-8:
            ratings = {row["candidate_id"]: 3.0 for row in sorted_rows}
        else:
            ratings = {
                row["candidate_id"]: round(1.0 + (4.0 * ((float(row["oracle_score"]) - lo) / (hi - lo))), 4)
                for row in sorted_rows
            }
        return FeedbackRequest(feedback_type=feedback_type, payload={"ratings": ratings}, critique_text=critique_text)
    if feedback_type == FeedbackType.top_k:
        ranking = [row["candidate_id"] for row in sorted_rows]
        return FeedbackRequest(feedback_type=feedback_type, payload={"ranking": ranking}, critique_text=critique_text)
    return FeedbackRequest(
        feedback_type=FeedbackType.winner_only,
        payload={"winner_candidate_id": winner_id},
        critique_text=critique_text,
    )


def _build_progress_svg(curve_rows: list[dict[str, Any]], output_path: Path) -> None:
    width = 1180
    height = 800
    left = 92
    right = 64
    panel_height = 250
    panel_gap = 56
    plot_width = width - left - right
    top_panel_y = 120
    bottom_panel_y = top_panel_y + panel_height + panel_gap
    rounds = sorted({int(row["round_index"]) for row in curve_rows})
    policy_ids = list(dict.fromkeys(str(row["policy_id"]) for row in curve_rows))
    colors = {
        "baseline_clip": "#6b4f2a",
        "sampler_upgrade": "#2563eb",
        "preference_upgrade": "#0f766e",
        "full_progress": "#b45309",
        "qd_sampler": "#7c3aed",
        "pl_listwise": "#be185d",
        "pareto_listwise": "#0f766e",
        "bt_progress": "#2563eb",
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
  <title id="title">Oracle progress diagnosis</title>
  <desc id="desc">Comparison of baseline and targeted anti-plateau policies under CLIP and DINOv2 evaluation.</desc>
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
  <text class="title" x="72" y="46">Oracle Progress Diagnosis</text>
  <text class="subtitle" x="72" y="72">Focused compact comparison for incumbent lock-in, richer feedback, and softer oracle selection.</text>
"""
    for y0, lo, hi, panel_title, best_field, base_field in [
        (top_panel_y, clip_lo, clip_hi, "CLIP cosine to target", "mean_best_clip", "mean_baseline_clip"),
        (bottom_panel_y, dino_lo, dino_hi, "DINOv2 cosine to target", "mean_best_dinov2", "mean_baseline_dinov2"),
    ]:
        svg += f'  <text class="panel" x="{left}" y="{y0 - 18}">{panel_title}</text>\n'
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
        baseline_points = [
            (int(row["round_index"]), float(row[base_field]))
            for row in curve_rows
            if str(row["policy_id"]) == policy_ids[0]
        ]
        svg += f'  <polyline class="baseline" points="{series(baseline_points, y0, lo, hi)}"/>\n'
        for policy_id in policy_ids:
            points = [
                (int(row["round_index"]), float(row[best_field]))
                for row in curve_rows
                if str(row["policy_id"]) == policy_id
            ]
            stroke = colors.get(policy_id, "#334155")
            svg += f'  <polyline fill="none" stroke="{stroke}" stroke-width="3.4" points="{series(points, y0, lo, hi)}"/>\n'

    legend_x = width - 360
    legend_y = 84
    for index, policy_id in enumerate(policy_ids):
        y = legend_y + index * 24
        stroke = colors.get(policy_id, "#334155")
        label = policy_id.replace("_", " ")
        svg += f'  <line x1="{legend_x}" y1="{y}" x2="{legend_x + 32}" y2="{y}" stroke="{stroke}" stroke-width="3.4"/>\n'
        svg += f'  <text class="legend" x="{legend_x + 42}" y="{y + 5}">{label}</text>\n'
    svg += f'  <line x1="{legend_x}" y1="{legend_y + len(policy_ids) * 24 + 8}" x2="{legend_x + 32}" y2="{legend_y + len(policy_ids) * 24 + 8}" class="baseline"/>\n'
    svg += f'  <text class="legend" x="{legend_x + 42}" y="{legend_y + len(policy_ids) * 24 + 13}">prompt-only baseline</text>\n'
    svg += "</svg>\n"
    _write_text(output_path, svg)


def _run_policy_target(
    *,
    output_dir: Path,
    suite: dict[str, Any],
    policy: PolicySpec,
    target: OracleTarget,
    metric_specs: list[MetricSpec],
    metric_objects: dict[str, Any],
    backend: str,
) -> dict[str, Any]:
    config = _strategy_config(suite, policy)
    run_root = output_dir / "runs" / policy.id / target.id
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
            name=f"Oracle progress diagnosis / {policy.label} / {target.label}",
            description="Focused compact oracle progress diagnosis",
            config=config,
        )
    )
    session = orchestrator.create_session(
        SessionCreate(experiment_id=experiment.id, prompt=target.caption, negative_prompt=target.negative_prompt)
    )
    max_rounds = int(suite.get("max_rounds", 6))
    margin_epsilon = float(suite.get("margin_epsilon", 0.015))
    round_rows: list[dict[str, Any]] = []
    candidate_rows: list[dict[str, Any]] = []
    baseline_scores = {spec.short_name: None for spec in metric_specs}
    final_best_scores = {spec.short_name: None for spec in metric_specs}
    incumbent_rounds = 0
    incumbent_selected_rounds = 0
    late_improvement_rounds = 0
    incumbent_clip_margins: list[float] = []
    selected_paths: list[str] = []
    running_best_clip = -1.0
    running_best_dino = -1.0

    for round_index in range(1, max_rounds + 1):
        orchestrator.generate_round(session.id)
        round_obj = orchestrator.get_session_rounds(session.id)[-1]
        scored_candidates: list[dict[str, Any]] = []
        incumbent_row: dict[str, Any] | None = None
        incumbent_clip_embedding = None
        for candidate in round_obj.candidates:
            image_path = _artifact_path(runtime_root, candidate.image_path)
            clip_embedding = metric_objects["clip"].embed_image(image_path)
            dino_embedding = metric_objects["dinov2"].embed_image(image_path)
            clip_score = ClipOracle.cosine(clip_embedding, target_embeddings["clip"])
            dino_score = DINOv2Metric.cosine(dino_embedding, target_embeddings["dinov2"])
            record: dict[str, Any] = {
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
                "seed": candidate.seed,
                "image_path": str(image_path),
                "carried_forward": bool(candidate.generation_params.get("carried_forward")),
                "baseline_prompt": bool(candidate.generation_params.get("baseline_prompt")),
                "clip_score": round(clip_score, 6),
                "dinov2_score": round(dino_score, 6),
                "_clip_embedding": clip_embedding,
            }
            if record["carried_forward"]:
                incumbent_row = record
                incumbent_clip_embedding = clip_embedding
                incumbent_rounds += 1
            scored_candidates.append(record)

        for record in scored_candidates:
            if incumbent_clip_embedding is None or record["candidate_id"] == (incumbent_row or {}).get("candidate_id"):
                novelty = 0.0
            else:
                novelty = 1.0 - ClipOracle.cosine(record["_clip_embedding"], incumbent_clip_embedding)
            record["novelty_to_incumbent"] = round(novelty, 6)

        _oracle_score_candidates(
            scored_candidates,
            policy=policy,
            margin_epsilon=margin_epsilon,
            target_clip_embedding=target_embeddings["clip"],
            incumbent_clip_embedding=incumbent_clip_embedding,
        )
        feedback = _oracle_feedback_request(
            scored_candidates,
            feedback_mode=policy.feedback_mode,
            critique_text=f"Oracle progress diagnosis policy: {policy.label}",
        )
        response = orchestrator.submit_feedback(round_obj.id, feedback)
        winner_id = str(response.update_summary["winner_candidate_id"])
        selected_row = next(row for row in scored_candidates if row["candidate_id"] == winner_id)
        if selected_row.get("carried_forward"):
            incumbent_selected_rounds += 1
        selected_paths.append(selected_row["image_path"])

        if incumbent_row is not None:
            challengers = [row for row in scored_candidates if not row.get("carried_forward")]
            if challengers:
                best_challenger = max(challengers, key=lambda row: float(row["clip_score"]))
                incumbent_clip_margins.append(float(incumbent_row["clip_score"]) - float(best_challenger["clip_score"]))

        best_clip = max(float(row["clip_score"]) for row in scored_candidates)
        best_dino = max(float(row["dinov2_score"]) for row in scored_candidates)
        if round_index == 1:
            baseline_scores["clip"] = float(next(row for row in scored_candidates if row["baseline_prompt"])["clip_score"])
            baseline_scores["dinov2"] = float(next(row for row in scored_candidates if row["baseline_prompt"])["dinov2_score"])
        if round_index > 3 and best_clip > running_best_clip + 1e-6:
            late_improvement_rounds += 1
        running_best_clip = max(running_best_clip, best_clip)
        running_best_dino = max(running_best_dino, best_dino)
        final_best_scores["clip"] = best_clip
        final_best_scores["dinov2"] = best_dino

        round_rows.append(
            {
                "policy_id": policy.id,
                "policy_label": policy.label,
                "oracle_policy": policy.oracle_policy,
                "target_id": target.id,
                "target_label": target.label,
                "session_id": session.id,
                "round_id": round_obj.id,
                "round_index": round_index,
                "winner_candidate_id": winner_id,
                "winner_sampler_role": selected_row["sampler_role"],
                "candidate_count": len(scored_candidates),
                "best_clip": round(best_clip, 6),
                "baseline_clip": round(float(baseline_scores["clip"]), 6),
                "best_dinov2": round(best_dino, 6),
                "baseline_dinov2": round(float(baseline_scores["dinov2"]), 6),
                "winner_oracle_score": round(float(selected_row["oracle_score"]), 6),
                "winner_carried_forward": bool(selected_row.get("carried_forward")),
            }
        )
        for row in scored_candidates:
            candidate_rows.append(
                {key: value for key, value in row.items() if not str(key).startswith("_")}
                | {"selected": row["candidate_id"] == winner_id}
            )

    trace_report = runtime_root / "traces" / "sessions" / session.id / "report.html"
    copied_trace = _copy_trace_report(trace_report, run_root)
    unique_selected_ratio = len(set(selected_paths)) / len(selected_paths) if selected_paths else 0.0
    last_three_plateau = len(selected_paths) >= 3 and len(set(selected_paths[-3:])) == 1
    return {
        "policy_id": policy.id,
        "policy_label": policy.label,
        "oracle_policy": policy.oracle_policy,
        "target_id": target.id,
        "target_label": target.label,
        "session_id": session.id,
        "trace_report": str(copied_trace),
        "baseline_clip": round(float(baseline_scores["clip"]), 6),
        "final_clip": round(float(final_best_scores["clip"]), 6),
        "delta_clip": round(float(final_best_scores["clip"] - float(baseline_scores["clip"])), 6),
        "baseline_dinov2": round(float(baseline_scores["dinov2"]), 6),
        "final_dinov2": round(float(final_best_scores["dinov2"]), 6),
        "delta_dinov2": round(float(final_best_scores["dinov2"] - float(baseline_scores["dinov2"])), 6),
        "late_improvement_rounds": late_improvement_rounds,
        "incumbent_rounds": incumbent_rounds,
        "incumbent_selected_rounds": incumbent_selected_rounds,
        "incumbent_selection_share": round((incumbent_selected_rounds / incumbent_rounds) if incumbent_rounds else 0.0, 6),
        "mean_incumbent_margin_clip": round(_safe_mean(incumbent_clip_margins), 6),
        "unique_selected_ratio": round(unique_selected_ratio, 6),
        "last_three_plateau": last_three_plateau,
        "round_rows": round_rows,
        "candidate_rows": candidate_rows,
    }


def _build_analysis(output_dir: Path, suite: dict[str, Any], run_rows: list[dict[str, Any]], round_rows: list[dict[str, Any]]) -> None:
    analysis_dir = output_dir / "analysis"
    figures_dir = analysis_dir / "figures"
    tables_dir = output_dir / "tables"
    analysis_dir.mkdir(parents=True, exist_ok=True)
    figures_dir.mkdir(parents=True, exist_ok=True)
    tables_dir.mkdir(parents=True, exist_ok=True)

    summary_rows: list[dict[str, Any]] = []
    for policy_id in dict.fromkeys(row["policy_id"] for row in run_rows):
        rows = [row for row in run_rows if row["policy_id"] == policy_id]
        policy_record = next(policy for policy in suite["policies"] if policy["id"] == policy_id)
        summary_rows.append(
            {
                "policy_id": policy_id,
                "policy_label": rows[0]["policy_label"],
                "oracle_policy": rows[0]["oracle_policy"],
                "sampler": policy_record["sampler"],
                "updater": policy_record["updater"],
                "feedback_mode": policy_record["feedback_mode"],
                "target_count": len(rows),
                "mean_baseline_clip": round(_safe_mean([float(row["baseline_clip"]) for row in rows]), 6),
                "mean_final_clip": round(_safe_mean([float(row["final_clip"]) for row in rows]), 6),
                "mean_delta_clip": round(_safe_mean([float(row["delta_clip"]) for row in rows]), 6),
                "mean_baseline_dinov2": round(_safe_mean([float(row["baseline_dinov2"]) for row in rows]), 6),
                "mean_final_dinov2": round(_safe_mean([float(row["final_dinov2"]) for row in rows]), 6),
                "mean_delta_dinov2": round(_safe_mean([float(row["delta_dinov2"]) for row in rows]), 6),
                "mean_late_improvement_rounds": round(_safe_mean([float(row["late_improvement_rounds"]) for row in rows]), 6),
                "incumbent_selection_share": round(_safe_mean([float(row["incumbent_selection_share"]) for row in rows]), 6),
                "mean_incumbent_margin_clip": round(_safe_mean([float(row["mean_incumbent_margin_clip"]) for row in rows]), 6),
                "mean_unique_selected_ratio": round(_safe_mean([float(row["unique_selected_ratio"]) for row in rows]), 6),
                "plateau_run_share": round(sum(1 for row in rows if row["last_three_plateau"]) / len(rows), 6),
            }
        )

    curve_rows: list[dict[str, Any]] = []
    for policy_id in dict.fromkeys(row["policy_id"] for row in round_rows):
        policy_rounds = [row for row in round_rows if row["policy_id"] == policy_id]
        for round_index in sorted({int(row["round_index"]) for row in policy_rounds}):
            rows = [row for row in policy_rounds if int(row["round_index"]) == round_index]
            curve_rows.append(
                {
                    "policy_id": policy_id,
                    "policy_label": rows[0]["policy_label"],
                    "round_index": round_index,
                    "mean_best_clip": round(_safe_mean([float(row["best_clip"]) for row in rows]), 6),
                    "mean_baseline_clip": round(_safe_mean([float(row["baseline_clip"]) for row in rows]), 6),
                    "mean_best_dinov2": round(_safe_mean([float(row["best_dinov2"]) for row in rows]), 6),
                    "mean_baseline_dinov2": round(_safe_mean([float(row["baseline_dinov2"]) for row in rows]), 6),
                }
            )

    _write_csv(tables_dir / "runs.csv", run_rows, list(run_rows[0].keys()))
    _write_csv(tables_dir / "rounds.csv", round_rows, list(round_rows[0].keys()))
    _write_csv(tables_dir / "policy_summary.csv", summary_rows, list(summary_rows[0].keys()))
    _write_csv(tables_dir / "curve_summary.csv", curve_rows, list(curve_rows[0].keys()))

    svg_path = figures_dir / "oracle_progress_diagnosis.svg"
    _build_progress_svg(curve_rows, svg_path)
    paper_figure_name = str(suite.get("paper_figure_name", "figure_16_oracle_progress_diagnosis.svg"))
    paper_figure = _paper_root() / "figures" / paper_figure_name
    paper_figure.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(svg_path, paper_figure)

    baseline = next((row for row in summary_rows if row["policy_id"] == "baseline_clip"), summary_rows[0])
    best_progress = max(summary_rows, key=lambda row: (row["mean_late_improvement_rounds"], -row["incumbent_selection_share"]))
    best_clip = max(summary_rows, key=lambda row: row["mean_final_clip"])
    markdown = f"""# Oracle Progress Diagnosis Analysis

This compact study tests why oracle steering often stops making visible round-by-round progress. The comparison keeps the same hidden-target recovery scaffold while changing proposal geometry, feedback modeling, and oracle selection.

## Scope

- targets: `{len(set(row["target_id"] for row in run_rows))}`
- policies: `{len(summary_rows)}`
- total runs: `{len(run_rows)}`
- total rounds: `{len(round_rows)}`

## Policy summary

| policy | clip final | clip delta | dinov2 final | late improvements | incumbent selection share | plateau share |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
"""
    for row in summary_rows:
        markdown += (
            f"| {row['policy_label']} | {row['mean_final_clip']:.3f} | {row['mean_delta_clip']:.3f} | "
            f"{row['mean_final_dinov2']:.3f} | {row['mean_late_improvement_rounds']:.2f} | "
            f"{row['incumbent_selection_share']:.2f} | {row['plateau_run_share']:.2f} |\n"
        )
    markdown += f"""

## Interpretation

- The baseline still shows heavy incumbent lock-in, with incumbent selection share `{baseline['incumbent_selection_share']:.2f}`.
- The strongest anti-stagnation policy by late-round movement is `{best_progress['policy_label']}`.
- The strongest final CLIP target-recovery policy in this compact slice is `{best_clip['policy_label']}`.
- The key question is therefore not only which policy ends highest, but which policy preserves challenger pressure without sacrificing final target recovery too heavily.

## Figure

![Oracle progress diagnosis](figures/oracle_progress_diagnosis.svg)
"""
    _write_text(analysis_dir / "analysis_summary.md", markdown)
    _markdown_to_html("Oracle Progress Diagnosis Analysis", markdown, analysis_dir / "analysis_summary.html")
    _write_text(
        output_dir / "README.md",
        "# Oracle Progress Diagnosis Bundle\n\n"
        "This compact bundle diagnoses incumbent lock-in in oracle steering and compares targeted fixes.\n\n"
        "- analysis: [analysis/analysis_summary.md](analysis/analysis_summary.md)\n"
        f"- paper figure: [../figures/figure_16_oracle_progress_diagnosis.svg]({paper_figure})\n",
    )
    _write_json(
        output_dir / "manifest.json",
        {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "suite_name": suite.get("suite_name", "oracle_progress_diagnosis"),
            "run_count": len(run_rows),
            "round_count": len(round_rows),
            "policy_count": len(summary_rows),
            "paper_figure": str(paper_figure),
        },
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Run a compact oracle progress diagnosis study.")
    parser.add_argument("--suite", type=Path, default=_paper_root() / "protocols" / "oracle_progress_diagnosis_suite.yaml")
    parser.add_argument("--output-dir", type=Path, default=_results_root())
    parser.add_argument("--backend", type=str, default="diffusers")
    args = parser.parse_args()

    suite = _read_yaml(args.suite)
    output_dir = args.output_dir
    output_dir.mkdir(parents=True, exist_ok=True)
    policy_specs = _policy_specs_from_suite(suite)
    targets = _load_targets(suite)
    metric_specs = _metric_specs_from_suite(suite)
    metric_objects = _build_metric_objects(metric_specs, str(suite["oracle_model"]))

    run_rows: list[dict[str, Any]] = []
    round_rows: list[dict[str, Any]] = []
    candidate_rows: list[dict[str, Any]] = []
    for policy in policy_specs:
        for target in targets:
            result = _run_policy_target(
                output_dir=output_dir,
                suite=suite,
                policy=policy,
                target=target,
                metric_specs=metric_specs,
                metric_objects=metric_objects,
                backend=args.backend,
            )
            run_rows.append({key: value for key, value in result.items() if key not in {"round_rows", "candidate_rows"}})
            round_rows.extend(result["round_rows"])
            candidate_rows.extend(result["candidate_rows"])

    tables_dir = output_dir / "tables"
    tables_dir.mkdir(parents=True, exist_ok=True)
    _write_csv(tables_dir / "candidates.csv", candidate_rows, list(candidate_rows[0].keys()))
    _build_analysis(output_dir, suite, run_rows, round_rows)


if __name__ == "__main__":
    main()
