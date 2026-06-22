from __future__ import annotations

import argparse
import math
import random
import shutil
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import torch
import yaml
from PIL import Image

from app.bootstrap.experiment_models import get_dino_components
from app.core.schema import ExperimentCreate, FeedbackRequest, FeedbackType, SessionCreate, StrategyConfig
from app.engine.generation import build_generation_engine
from app.engine.orchestrator import Orchestrator
from app.storage.repository import JsonRepository
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
class MetricSpec:
    id: str
    short_name: str
    label: str
    kind: str


class DINOv2Metric:
    def __init__(self, model_id: str, device: str = "cpu") -> None:
        self.model_id = model_id
        self.device = device
        self.processor, self.model = get_dino_components(model_id, device)

    def embed_image(self, image_path: Path) -> torch.Tensor:
        image = Image.open(image_path).convert("RGB")
        inputs = self.processor(images=image, return_tensors="pt")
        inputs = {key: value.to(self.device) for key, value in inputs.items()}
        with torch.no_grad():
            outputs = self.model(**inputs)
        if hasattr(outputs, "pooler_output") and outputs.pooler_output is not None:
            features = outputs.pooler_output
        elif hasattr(outputs, "last_hidden_state"):
            features = outputs.last_hidden_state[:, 0, :]
        else:
            raise TypeError(f"Unsupported DINO output type: {type(outputs)!r}")
        features = features / features.norm(dim=-1, keepdim=True)
        return features[0].detach().cpu()

    @staticmethod
    def cosine(left: torch.Tensor, right: torch.Tensor) -> float:
        return float(torch.dot(left, right).item())


def _results_root() -> Path:
    return _paper_root() / "results" / "oracle_multimetric_repeated"


def _metric_specs_from_suite(suite: dict[str, Any]) -> list[MetricSpec]:
    specs: list[MetricSpec] = []
    for record in suite.get("evaluation_models", []):
        specs.append(
            MetricSpec(
                id=str(record["id"]),
                short_name=str(record["short_name"]),
                label=str(record["label"]),
                kind=str(record["kind"]),
            )
        )
    if not specs:
        raise ValueError("evaluation_models must contain at least one metric")
    return specs


def _strategy_config_from_suite(suite: dict[str, Any]) -> StrategyConfig:
    payload = dict(suite.get("fixed_conditions", {}))
    image_size = payload.get("image_size", "512x512")
    if isinstance(image_size, list) and len(image_size) == 2:
        payload["image_size"] = f"{image_size[0]}x{image_size[1]}"
    return StrategyConfig.model_validate(payload)


def _safe_mean(values: list[float]) -> float:
    return sum(values) / len(values) if values else 0.0


def _safe_std(values: list[float]) -> float:
    if len(values) <= 1:
        return 0.0
    mean = _safe_mean(values)
    return math.sqrt(sum((value - mean) ** 2 for value in values) / (len(values) - 1))


def _bootstrap_mean_ci(values: list[float], *, seed: int = 0, samples: int = 2000) -> tuple[float, float]:
    if not values:
        return (0.0, 0.0)
    if len(values) == 1:
        return (values[0], values[0])
    rng = random.Random(seed)
    sample_means: list[float] = []
    for _ in range(samples):
        drawn = [values[rng.randrange(len(values))] for _ in range(len(values))]
        sample_means.append(sum(drawn) / len(drawn))
    sample_means.sort()
    lo_index = max(0, int(0.025 * samples) - 1)
    hi_index = min(samples - 1, int(0.975 * samples) - 1)
    return (sample_means[lo_index], sample_means[hi_index])


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


def _oracle_feedback_request(scored_candidates: list[dict[str, Any]], critique_text: str) -> FeedbackRequest:
    """Build one feedback request from oracle-scored candidates using the configured feedback mode."""

    sorted_rows = sorted(scored_candidates, key=lambda row: (-float(row.get("oracle_score", row["clip_score"])), row["candidate_id"]))
    winner_id = sorted_rows[0]["candidate_id"]
    feedback_mode = str(sorted_rows[0].get("oracle_feedback_mode", FeedbackType.winner_only.value))
    feedback_type = FeedbackType(feedback_mode)

    if feedback_type == FeedbackType.scalar_rating:
        oracle_scores = [float(row.get("oracle_score", row["clip_score"])) for row in sorted_rows]
        lo = min(oracle_scores)
        hi = max(oracle_scores)
        if hi - lo < 1e-8:
            ratings = {row["candidate_id"]: 3.0 for row in sorted_rows}
        else:
            ratings = {
                row["candidate_id"]: round(
                    1.0 + (4.0 * ((float(row.get("oracle_score", row["clip_score"])) - lo) / (hi - lo))),
                    4,
                )
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


def _eligible_oracle_candidates(
    scored_candidates: list[dict[str, Any]],
    *,
    repeated_selected_image_streak: int,
    cooldown_rounds: int,
    penalty_rounds: int,
    incumbent_selection_penalty: float,
) -> list[dict[str, Any]]:
    """Apply oracle selection controls after repeated stagnation."""

    penalty_active = (
        incumbent_selection_penalty > 0.0
        and penalty_rounds > 0
        and repeated_selected_image_streak >= penalty_rounds
    )
    for row in scored_candidates:
        oracle_score = float(row["clip_score"])
        penalty_applied = penalty_active and bool(row.get("carried_forward"))
        if penalty_applied:
            oracle_score -= incumbent_selection_penalty
        row["oracle_score"] = round(oracle_score, 6)
        row["oracle_penalty_applied"] = penalty_applied

    if cooldown_rounds <= 0 or repeated_selected_image_streak < cooldown_rounds:
        return scored_candidates
    challengers = [row for row in scored_candidates if not row.get("carried_forward")]
    return challengers or scored_candidates


def _build_dual_metric_svg(curve_rows: list[dict[str, Any]], output_path: Path) -> None:
    width = 1120
    height = 760
    left = 84
    right = 60
    top = 66
    panel_gap = 48
    panel_height = 250
    plot_width = width - left - right
    top_panel_y = 110
    bottom_panel_y = top_panel_y + panel_height + panel_gap
    rounds = sorted({int(row["round_index"]) for row in curve_rows})
    clip_scores = [float(row["mean_best_clip"]) for row in curve_rows]
    clip_base = [float(row["mean_baseline_clip"]) for row in curve_rows]
    dino_scores = [float(row["mean_best_dinov2"]) for row in curve_rows]
    dino_base = [float(row["mean_baseline_dinov2"]) for row in curve_rows]
    clip_ci_lows = [float(row["ci_low_best_clip"]) for row in curve_rows]
    clip_ci_highs = [float(row["ci_high_best_clip"]) for row in curve_rows]
    dino_ci_lows = [float(row["ci_low_best_dinov2"]) for row in curve_rows]
    dino_ci_highs = [float(row["ci_high_best_dinov2"]) for row in curve_rows]

    def x_pos(round_index: int) -> float:
        if len(rounds) == 1:
            return left + plot_width / 2
        return left + ((round_index - min(rounds)) / (max(rounds) - min(rounds))) * plot_width

    def y_pos(score: float, y0: float, lo: float, hi: float) -> float:
        if hi == lo:
            return y0 + panel_height / 2
        return y0 + (1 - ((score - lo) / (hi - lo))) * panel_height

    clip_lo = min(min(clip_scores), min(clip_base), min(clip_ci_lows)) - 0.02
    clip_hi = max(max(clip_scores), max(clip_base), max(clip_ci_highs)) + 0.02
    dino_lo = min(min(dino_scores), min(dino_base), min(dino_ci_lows)) - 0.02
    dino_hi = max(max(dino_scores), max(dino_base), max(dino_ci_highs)) + 0.02

    def series(points: list[float], y0: float, lo: float, hi: float) -> str:
        return " ".join(f"{x_pos(r):.1f},{y_pos(v, y0, lo, hi):.1f}" for r, v in zip(rounds, points, strict=True))

    def band(points_low: list[float], points_high: list[float], y0: float, lo: float, hi: float) -> str:
        upper = [f"{x_pos(r):.1f},{y_pos(v, y0, lo, hi):.1f}" for r, v in zip(rounds, points_high, strict=True)]
        lower = [f"{x_pos(r):.1f},{y_pos(v, y0, lo, hi):.1f}" for r, v in zip(reversed(rounds), reversed(points_low), strict=True)]
        return " ".join(upper + lower)

    svg = f"""<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}" role="img" aria-labelledby="title desc">
  <title id="title">Repeated-seed multi-metric oracle study</title>
  <desc id="desc">Top panel shows CLIP convergence, bottom panel shows DINOv2 convergence, both aggregated across repeated seeds.</desc>
  <style>
    .bg {{ fill: #fbfaf6; }}
    .axis {{ stroke: #475467; stroke-width: 2.1; }}
    .grid {{ stroke: #d9cfbf; stroke-width: 1.1; }}
    .clipBand {{ fill: #8b4513; opacity: 0.12; }}
    .dinoBand {{ fill: #1f6f8b; opacity: 0.12; }}
    .clip {{ fill: none; stroke: #8b4513; stroke-width: 3.8; }}
    .clipBase {{ fill: none; stroke: #8b4513; stroke-width: 2.2; stroke-dasharray: 10 7; opacity: 0.65; }}
    .dino {{ fill: none; stroke: #1f6f8b; stroke-width: 3.8; }}
    .dinoBase {{ fill: none; stroke: #1f6f8b; stroke-width: 2.2; stroke-dasharray: 10 7; opacity: 0.65; }}
    .title {{ font: 700 28px Georgia, 'Times New Roman', serif; fill: #1f2937; }}
    .subtitle {{ font: 16px Georgia, 'Times New Roman', serif; fill: #334155; }}
    .tick {{ font: 14px Georgia, 'Times New Roman', serif; fill: #334155; }}
    .panel {{ font: 700 18px Georgia, 'Times New Roman', serif; fill: #1f2937; }}
  </style>
  <rect class="bg" width="{width}" height="{height}"/>
  <text class="title" x="70" y="44">Repeated-Seed Multi-Metric Oracle Study</text>
  <text class="subtitle" x="70" y="70">Mean best-candidate similarity over rounds with 95% bootstrap confidence intervals.</text>
"""
    for y0, lo, hi, panel_title, score_points, base_points, ci_low, ci_high, band_class, score_class, base_class in [
        (top_panel_y, clip_lo, clip_hi, "CLIP cosine to target", clip_scores, clip_base, clip_ci_lows, clip_ci_highs, "clipBand", "clip", "clipBase"),
        (bottom_panel_y, dino_lo, dino_hi, "DINOv2 cosine to target", dino_scores, dino_base, dino_ci_lows, dino_ci_highs, "dinoBand", "dino", "dinoBase"),
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
        svg += f'  <polygon class="{band_class}" points="{band(ci_low, ci_high, y0, lo, hi)}"/>\n'
        svg += f'  <polyline class="{base_class}" points="{series(base_points, y0, lo, hi)}"/>\n'
        svg += f'  <polyline class="{score_class}" points="{series(score_points, y0, lo, hi)}"/>\n'
    svg += "</svg>\n"
    _write_text(output_path, svg)


def _run_target_repeat(
    *,
    output_dir: Path,
    suite: dict[str, Any],
    target: OracleTarget,
    repeat_index: int,
    metric_specs: list[MetricSpec],
    metric_objects: dict[str, Any],
    backend: str,
) -> dict[str, Any]:
    config = _strategy_config_from_suite(suite)
    run_root = output_dir / "runs" / target.id / f"repeat_{repeat_index + 1}"
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
            name=f"Oracle multimetric repeat / {target.label} / r{repeat_index + 1}",
            description=f"Repeated-seed multi-metric oracle experiment for {target.id}",
            config=config,
        )
    )
    session = orchestrator.create_session(
        SessionCreate(experiment_id=experiment.id, prompt=target.caption, negative_prompt=target.negative_prompt)
    )

    max_rounds = int(suite.get("max_rounds", 10))
    round_rows: list[dict[str, Any]] = []
    candidate_rows: list[dict[str, Any]] = []
    baseline_scores = {spec.short_name: None for spec in metric_specs}
    first_round_best_scores = {spec.short_name: None for spec in metric_specs}
    final_best_scores = {spec.short_name: None for spec in metric_specs}
    repeated_selected_image_streak = 0
    last_selected_image_path: str | None = None
    cooldown_rounds = int(suite.get("incumbent_selection_cooldown_rounds", 0))
    penalty_rounds = int(suite.get("incumbent_selection_penalty_rounds", 0))
    incumbent_selection_penalty = float(suite.get("incumbent_selection_penalty", 0.0))

    for round_index in range(1, max_rounds + 1):
        orchestrator.generate_round(session.id)
        round_obj = orchestrator.get_session_rounds(session.id)[-1]
        scored_candidates: list[dict[str, Any]] = []
        for candidate in round_obj.candidates:
            image_path = _artifact_path(runtime_root, candidate.image_path)
            record: dict[str, Any] = {
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
                "oracle_score": None,
                "oracle_penalty_applied": False,
            }
            image_embeddings = {spec.short_name: metric_objects[spec.short_name].embed_image(image_path) for spec in metric_specs}
            for spec in metric_specs:
                score = metric_objects[spec.short_name].cosine(target_embeddings[spec.short_name], image_embeddings[spec.short_name])
                record[f"{spec.short_name}_score"] = round(score, 6)
                if record["baseline_prompt"] and baseline_scores[spec.short_name] is None:
                    baseline_scores[spec.short_name] = score
            candidate_rows.append(record)
            scored_candidates.append(record)

        eligible_candidates = _eligible_oracle_candidates(
            scored_candidates,
            repeated_selected_image_streak=repeated_selected_image_streak,
            cooldown_rounds=cooldown_rounds,
            penalty_rounds=penalty_rounds,
            incumbent_selection_penalty=incumbent_selection_penalty,
        )
        winner = max(eligible_candidates, key=lambda row: float(row.get("oracle_score", row["clip_score"])))
        winner["selected"] = True
        winner_image_path = str(winner["image_path"])
        if last_selected_image_path == winner_image_path:
            repeated_selected_image_streak += 1
        else:
            repeated_selected_image_streak = 1
            last_selected_image_path = winner_image_path
        round_record = {
            "target_id": target.id,
            "target_label": target.label,
            "repeat_index": repeat_index,
            "session_id": session.id,
            "round_id": round_obj.id,
            "round_index": round_index,
            "winner_candidate_id": winner["candidate_id"],
            "winner_sampler_role": winner["sampler_role"],
            "winner_clip_score": round(float(winner["clip_score"]), 6),
            "winner_oracle_score": round(float(winner.get("oracle_score", winner["clip_score"])), 6),
            "candidate_count": len(scored_candidates),
            "incumbent_cooldown_active": bool(cooldown_rounds > 0 and repeated_selected_image_streak >= cooldown_rounds),
            "incumbent_penalty_active": bool(
                incumbent_selection_penalty > 0.0
                and penalty_rounds > 0
                and repeated_selected_image_streak >= penalty_rounds
            ),
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
            orchestrator.submit_feedback(
                round_obj.id,
                _oracle_feedback_request(
                    eligible_candidates,
                    critique_text="Oracle feedback derived from CLIP target-image similarity over the current candidate set.",
                ),
            )

    trace_report_path = orchestrator.generate_trace_report(session.id)
    copied_report = _copy_trace_report(trace_report_path, run_root)
    summary: dict[str, Any] = {
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


def _build_analysis(output_dir: Path, target_rows: list[dict[str, Any]], round_rows: list[dict[str, Any]], metric_specs: list[MetricSpec], suite: dict[str, Any]) -> None:
    analysis_root = output_dir / "analysis"
    rounds_by_index: dict[int, list[dict[str, Any]]] = {}
    for row in round_rows:
        rounds_by_index.setdefault(int(row["round_index"]), []).append(row)

    curve_rows: list[dict[str, Any]] = []
    for round_index in sorted(rounds_by_index):
        rows = rounds_by_index[round_index]
        record: dict[str, Any] = {"round_index": round_index}
        for spec in metric_specs:
            best_values = [float(row[f"best_{spec.short_name}"]) for row in rows]
            baseline_values = [float(row[f"baseline_{spec.short_name}"]) for row in rows]
            ci_low, ci_high = _bootstrap_mean_ci(best_values, seed=(round_index * 1000) + len(best_values))
            record[f"mean_best_{spec.short_name}"] = round(_safe_mean(best_values), 6)
            record[f"std_best_{spec.short_name}"] = round(_safe_std(best_values), 6)
            record[f"mean_baseline_{spec.short_name}"] = round(_safe_mean(baseline_values), 6)
            record[f"ci_low_best_{spec.short_name}"] = round(ci_low, 6)
            record[f"ci_high_best_{spec.short_name}"] = round(ci_high, 6)
        curve_rows.append(record)

    curve_fields = ["round_index"]
    for spec in metric_specs:
        curve_fields.extend(
            [
                f"mean_best_{spec.short_name}",
                f"std_best_{spec.short_name}",
                f"mean_baseline_{spec.short_name}",
                f"ci_low_best_{spec.short_name}",
                f"ci_high_best_{spec.short_name}",
            ]
        )
    _write_csv(analysis_root / "round_curve.csv", curve_rows, curve_fields)
    _build_dual_metric_svg(curve_rows, analysis_root / "oracle_multimetric_repeated.svg")

    by_target: dict[str, list[dict[str, Any]]] = {}
    for row in target_rows:
        by_target.setdefault(str(row["target_id"]), []).append(row)

    target_summary_rows: list[dict[str, Any]] = []
    for target_id, rows in sorted(by_target.items()):
        summary: dict[str, Any] = {"target_id": target_id, "target_label": rows[0]["target_label"], "repeats": len(rows)}
        for spec in metric_specs:
            finals = [float(row[f"final_best_{spec.short_name}"]) for row in rows]
            deltas = [float(row[f"delta_{spec.short_name}"]) for row in rows]
            summary[f"mean_final_{spec.short_name}"] = round(_safe_mean(finals), 6)
            summary[f"std_final_{spec.short_name}"] = round(_safe_std(finals), 6)
            summary[f"mean_delta_{spec.short_name}"] = round(_safe_mean(deltas), 6)
            summary[f"std_delta_{spec.short_name}"] = round(_safe_std(deltas), 6)
        target_summary_rows.append(summary)

    target_fields = ["target_id", "target_label", "repeats"]
    for spec in metric_specs:
        target_fields.extend([f"mean_final_{spec.short_name}", f"std_final_{spec.short_name}", f"mean_delta_{spec.short_name}", f"std_delta_{spec.short_name}"])
    _write_csv(analysis_root / "target_summary.csv", target_summary_rows, target_fields)

    lines = []
    for spec in metric_specs:
        baselines = [float(row[f"baseline_{spec.short_name}"]) for row in target_rows]
        finals = [float(row[f"final_best_{spec.short_name}"]) for row in target_rows]
        deltas = [float(row[f"delta_{spec.short_name}"]) for row in target_rows]
        final_ci_low, final_ci_high = _bootstrap_mean_ci(finals, seed=100 + len(finals))
        delta_ci_low, delta_ci_high = _bootstrap_mean_ci(deltas, seed=200 + len(deltas))
        lines.append(
            f"- {spec.label}: baseline `{_safe_mean(baselines):.3f}`, final `{_safe_mean(finals):.3f}` "
            f"(95% CI `{final_ci_low:.3f}` to `{final_ci_high:.3f}`), delta `{_safe_mean(deltas):.3f}` "
            f"(95% CI `{delta_ci_low:.3f}` to `{delta_ci_high:.3f}`; sd `{_safe_std(deltas):.3f}`)"
        )

    dataset = suite.get("dataset", {})
    candidate_count = int(suite.get("fixed_conditions", {}).get("candidate_count", 0))
    dataset_block = [
        f"- dataset: `{dataset.get('name', 'unspecified')}`",
        f"- source: `{dataset.get('source', 'unspecified')}`",
        f"- split: `{dataset.get('split', 'unspecified')}`",
        f"- selected targets: `{dataset.get('selected_target_count', len(by_target))}`",
        f"- total candidates evaluated: `{len(round_rows) * candidate_count}`",
    ]

    target_table = "\n".join(
        f"| {row['target_label']} | {row['repeats']} | "
        + " | ".join(
            f"{float(row[f'mean_final_{spec.short_name}']):.3f} ± {float(row[f'std_final_{spec.short_name}']):.3f}"
            for spec in metric_specs
        )
        + " |"
        for row in target_summary_rows
    )
    summary_md = (
        "# Repeated-Seed Multi-Metric Oracle Analysis\n\n"
        "This study repeats the oracle target-recovery protocol on a deterministic public image-caption subset and evaluates the resulting trajectories under two pretrained image-embedding families.\n\n"
        "## Dataset and scope\n\n"
        + "\n".join(dataset_block)
        + "\n"
        f"- targets: `{len(by_target)}`\n"
        f"- repeats per target: `{len(target_rows) // max(1, len(by_target))}`\n"
        f"- total runs: `{len(target_rows)}`\n"
        f"- total rounds: `{len(round_rows)}`\n\n"
        "## Aggregate summary\n\n"
        + "\n".join(lines)
        + "\n\n## Target-level summary\n\n| target | repeats | clip final (mean ± sd) | dinov2 final (mean ± sd) |\n| --- | ---: | ---: | ---: |\n"
        + target_table
        + "\n\n## Interpretation boundary\n\n"
        "- CLIP remains the oracle selection metric.\n"
        "- DINOv2 is added as an independent evaluation metric rather than an oracle.\n"
        "- Confidence intervals are bootstrapped over run-level outcomes.\n"
        "- Repeated seeds reduce the chance that the observed trend is a single-session artifact.\n"
        "- The study is still a proxy target-recovery evaluation, not a human-preference study.\n\n"
        "## Figure\n\n![Repeated-seed multi-metric oracle convergence](oracle_multimetric_repeated.svg)\n"
    )
    _write_text(analysis_root / "analysis_summary.md", summary_md)
    _markdown_to_html("Repeated-Seed Multi-Metric Oracle Analysis", summary_md, analysis_root / "analysis_summary.html")
    shutil.copy2(analysis_root / "oracle_multimetric_repeated.svg", _paper_root() / "figures" / "figure_11_oracle_multimetric_repeated.svg")


def main() -> int:
    parser = argparse.ArgumentParser(description="Run repeated-seed multi-metric oracle target-recovery study.")
    parser.add_argument("--suite", type=Path, default=_paper_root() / "protocols" / "oracle_multimetric_repeated_suite.yaml")
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
    repeats = int(suite.get("repeats_per_target", 3))

    target_rows: list[dict[str, Any]] = []
    round_rows: list[dict[str, Any]] = []
    candidate_rows: list[dict[str, Any]] = []
    for target in targets:
        for repeat_index in range(repeats):
            result = _run_target_repeat(
                output_dir=output_dir,
                suite=suite,
                target=target,
                repeat_index=repeat_index,
                metric_specs=metric_specs,
                metric_objects=metric_objects,
                backend=args.backend,
            )
            target_rows.append(result["summary"])
            round_rows.extend(result["round_rows"])
            candidate_rows.extend(result["candidate_rows"])

    target_fields = ["target_id", "target_label", "repeat_index", "target_path", "target_attribution", "session_id", "experiment_id", "trace_report", "runtime_root", "max_rounds"]
    for spec in metric_specs:
        target_fields.extend([f"baseline_{spec.short_name}", f"first_round_best_{spec.short_name}", f"final_best_{spec.short_name}", f"delta_{spec.short_name}"])
    _write_csv(output_dir / "tables" / "targets.csv", target_rows, target_fields)

    round_fields = ["target_id", "target_label", "repeat_index", "session_id", "round_id", "round_index", "winner_candidate_id", "winner_sampler_role", "candidate_count"]
    for spec in metric_specs:
        round_fields.extend([f"best_{spec.short_name}", f"baseline_{spec.short_name}"])
    _write_csv(output_dir / "tables" / "rounds.csv", round_rows, round_fields)

    candidate_fields = ["target_id", "target_label", "repeat_index", "session_id", "round_id", "round_index", "candidate_id", "candidate_index", "sampler_role", "seed", "image_path", "selected", "carried_forward", "baseline_prompt"] + [f"{spec.short_name}_score" for spec in metric_specs]
    _write_csv(output_dir / "tables" / "candidates.csv", candidate_rows, candidate_fields)

    _write_json(
        output_dir / "manifest.json",
        {
            "suite_name": suite.get("suite_name", "oracle_multimetric_repeated"),
            "description": suite.get("description", ""),
            "generated_at": datetime.now(timezone.utc).isoformat(),
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
    _build_analysis(output_dir, target_rows, round_rows, metric_specs, suite)
    _write_text(
        output_dir / "README.md",
        (
            "# Repeated-Seed Multi-Metric Oracle Results\n\n"
            "This directory contains the repeated-seed extension of the oracle target-recovery study.\n\n"
            f"Current bundle summary: {len(target_rows)} runs, {len(round_rows)} rounds, and {len(candidate_rows)} candidate rows.\n"
        ),
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
