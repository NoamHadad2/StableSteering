from __future__ import annotations

import argparse
import hashlib
import math
import random
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import torch
from PIL import Image, ImageDraw, ImageFont, ImageOps

from app.core.schema import Candidate, ExperimentCreate, FeedbackRequest, FeedbackType, Session, SessionCreate, SessionStatus, StrategyConfig
from app.engine.generation import build_generation_engine
from app.engine.orchestrator import Orchestrator
from app.storage.repository import JsonRepository
from run_paper_oracle_multimetric_repeated import MetricSpec, _build_metric_objects, _metric_specs_from_suite
from run_paper_oracle_target_recovery import (
    OracleTarget,
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
class MethodSpec:
    id: str
    label: str
    description: str


def _results_root() -> Path:
    return _paper_root() / "results" / "budget_matched_direct_baselines"


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


def _strategy_config_from_suite(suite: dict[str, Any]) -> StrategyConfig:
    payload = dict(suite.get("fixed_conditions", {}))
    image_size = payload.get("image_size", "512x512")
    if isinstance(image_size, list) and len(image_size) == 2:
        payload["image_size"] = f"{image_size[0]}x{image_size[1]}"
    return StrategyConfig.model_validate(payload)


def _methods_from_suite(suite: dict[str, Any]) -> list[MethodSpec]:
    methods: list[MethodSpec] = []
    for record in suite.get("methods", []):
        methods.append(
            MethodSpec(
                id=str(record["id"]),
                label=str(record["label"]),
                description=str(record.get("description", "")),
            )
        )
    if not methods:
        raise ValueError("methods must contain at least one method")
    return methods


def _seed_token(*parts: Any) -> int:
    payload = "|".join(str(part) for part in parts)
    digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()
    return int(digest[:8], 16)


def _font(size: int):
    try:
        return ImageFont.truetype("arial.ttf", size)
    except OSError:
        return ImageFont.load_default()


def _score_image(
    image_path: Path,
    *,
    metric_specs: list[MetricSpec],
    metric_objects: dict[str, Any],
    target_embeddings: dict[str, torch.Tensor],
) -> dict[str, float]:
    scores: dict[str, float] = {}
    for spec in metric_specs:
        metric = metric_objects[spec.short_name]
        embedding = metric.embed_image(image_path)
        score = metric.cosine(embedding, target_embeddings[spec.short_name])
        scores[spec.short_name] = float(score)
    return scores


def _make_prompt_session(prompt: str, negative_prompt: str, config: StrategyConfig) -> Session:
    return Session(
        experiment_id="paper",
        prompt=prompt,
        negative_prompt=negative_prompt,
        model_name=config.model_name,
        status=SessionStatus.ready,
        current_z=[0.0 for _ in range(config.steering_dimension)],
        config=config,
    )


def _render_prompt_image(
    *,
    generator: Any,
    artifacts_dir: Path,
    config: StrategyConfig,
    prompt: str,
    negative_prompt: str,
    seed: int,
    candidate_index: int,
) -> Candidate:
    artifacts_dir.mkdir(parents=True, exist_ok=True)
    generator.artifacts_dir = artifacts_dir
    session = _make_prompt_session(prompt, negative_prompt, config)
    candidate = Candidate(
        round_id="prompt_baseline",
        candidate_index=candidate_index,
        z=[0.0 for _ in range(config.steering_dimension)],
        sampler_role="prompt_only",
        predicted_score=0.0,
        predicted_uncertainty=0.0,
        seed=seed,
        generation_params={"image_size": config.image_size, "baseline_prompt": True},
    )
    return generator.render_candidate(session, candidate)


def _candidate_image_path(artifacts_dir: Path, candidate: Candidate) -> Path:
    if not candidate.image_path:
        raise ValueError("Candidate image_path missing after render")
    return artifacts_dir / Path(candidate.image_path).name


def _build_baseline_image(
    *,
    output_dir: Path,
    generator: Any,
    config: StrategyConfig,
    target: OracleTarget,
    repeat_index: int,
    metric_specs: list[MetricSpec],
    metric_objects: dict[str, Any],
    target_embeddings: dict[str, torch.Tensor],
) -> dict[str, Any]:
    artifacts_dir = output_dir / "shared_baselines" / target.id / f"repeat_{repeat_index + 1}"
    seed = _seed_token(target.id, repeat_index, "shared-baseline")
    candidate = _render_prompt_image(
        generator=generator,
        artifacts_dir=artifacts_dir,
        config=config,
        prompt=target.caption,
        negative_prompt=target.negative_prompt,
        seed=seed,
        candidate_index=0,
    )
    image_path = _candidate_image_path(artifacts_dir, candidate)
    scores = _score_image(image_path, metric_specs=metric_specs, metric_objects=metric_objects, target_embeddings=target_embeddings)
    return {"seed": seed, "image_path": str(image_path), "scores": scores}


def _record_curve_rows(
    *,
    run_rows: list[dict[str, Any]],
    method: MethodSpec,
    target: OracleTarget,
    repeat_index: int,
    round_index: int,
    baseline_scores: dict[str, float],
    round_best: dict[str, float],
    cumulative_best: dict[str, float],
    selected_scores: dict[str, float],
    selected_image_path: str,
    selected_prompt: str,
    ) -> None:
    run_rows.append(
        {
            "method_id": method.id,
            "method_label": method.label,
            "target_id": target.id,
            "target_label": target.label,
            "repeat_index": repeat_index,
            "round_index": round_index,
            "baseline_clip": baseline_scores["clip"],
            "baseline_dinov2": baseline_scores["dinov2"],
            "round_best_clip": round_best["clip"],
            "round_best_dinov2": round_best["dinov2"],
            "best_so_far_clip": cumulative_best["clip"],
            "best_so_far_dinov2": cumulative_best["dinov2"],
            "selected_clip": selected_scores["clip"],
            "selected_dinov2": selected_scores["dinov2"],
            "selected_image_path": selected_image_path,
            "selected_prompt": selected_prompt,
        }
    )


def _run_prompt_best_of_budget(
    *,
    output_dir: Path,
    generator: Any,
    config: StrategyConfig,
    target: OracleTarget,
    repeat_index: int,
    metric_specs: list[MetricSpec],
    metric_objects: dict[str, Any],
    target_embeddings: dict[str, torch.Tensor],
    baseline_payload: dict[str, Any],
    max_rounds: int,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    method = MethodSpec("prompt_best_of_budget", "Prompt-only best-of-budget", "")
    artifacts_dir = output_dir / "runs" / method.id / target.id / f"repeat_{repeat_index + 1}" / "artifacts"
    rows: list[dict[str, Any]] = []
    best_so_far = dict(baseline_payload["scores"])
    best_image_path = str(baseline_payload["image_path"])
    best_prompt = target.caption
    for round_index in range(1, max_rounds + 1):
        candidates: list[dict[str, Any]] = []
        for candidate_index in range(config.candidate_count):
            seed = _seed_token(method.id, target.id, repeat_index, round_index, candidate_index)
            candidate = _render_prompt_image(
                generator=generator,
                artifacts_dir=artifacts_dir,
                config=config,
                prompt=target.caption,
                negative_prompt=target.negative_prompt,
                seed=seed,
                candidate_index=candidate_index,
            )
            image_path = _candidate_image_path(artifacts_dir, candidate)
            scores = _score_image(image_path, metric_specs=metric_specs, metric_objects=metric_objects, target_embeddings=target_embeddings)
            candidates.append({"scores": scores, "image_path": str(image_path), "prompt": target.caption})
        round_best = max(candidates, key=lambda row: (row["scores"]["clip"], row["scores"]["dinov2"]))
        if (round_best["scores"]["clip"], round_best["scores"]["dinov2"]) > (best_so_far["clip"], best_so_far["dinov2"]):
            best_so_far = dict(round_best["scores"])
            best_image_path = round_best["image_path"]
            best_prompt = round_best["prompt"]
        _record_curve_rows(
            run_rows=rows,
            method=method,
            target=target,
            repeat_index=repeat_index,
            round_index=round_index,
            baseline_scores=baseline_payload["scores"],
            round_best=round_best["scores"],
            cumulative_best=best_so_far,
            selected_scores=best_so_far,
            selected_image_path=best_image_path,
            selected_prompt=best_prompt,
        )
    return rows, {"final_image_path": best_image_path, "final_prompt": best_prompt, "final_scores": best_so_far}


def _modifier_candidates(current_modifiers: list[str], library: list[str], round_index: int, candidate_count: int) -> list[list[str]]:
    variants: list[list[str]] = [list(current_modifiers)]
    used = set(current_modifiers)
    offset = (round_index - 1) * (candidate_count - 1)
    library_len = max(1, len(library))
    cursor = 0
    while len(variants) < candidate_count:
        modifier = library[(offset + cursor) % library_len]
        cursor += 1
        if modifier in used:
            continue
        used.add(modifier)
        variants.append([*current_modifiers, modifier])
    return variants


def _prompt_from_modifiers(base_prompt: str, modifiers: list[str]) -> str:
    if not modifiers:
        return base_prompt
    return f"{base_prompt}; " + "; ".join(modifiers)


def _run_prompt_modifier_search(
    *,
    output_dir: Path,
    generator: Any,
    config: StrategyConfig,
    target: OracleTarget,
    repeat_index: int,
    metric_specs: list[MetricSpec],
    metric_objects: dict[str, Any],
    target_embeddings: dict[str, torch.Tensor],
    baseline_payload: dict[str, Any],
    max_rounds: int,
    modifier_library: list[str],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    method = MethodSpec("prompt_modifier_search", "Heuristic prompt-rewrite search", "")
    artifacts_dir = output_dir / "runs" / method.id / target.id / f"repeat_{repeat_index + 1}" / "artifacts"
    rows: list[dict[str, Any]] = []
    current_modifiers: list[str] = []
    best_so_far = dict(baseline_payload["scores"])
    best_image_path = str(baseline_payload["image_path"])
    best_prompt = target.caption
    for round_index in range(1, max_rounds + 1):
        variants = _modifier_candidates(current_modifiers, modifier_library, round_index, config.candidate_count)
        candidates: list[dict[str, Any]] = []
        for candidate_index, modifier_state in enumerate(variants):
            prompt_variant = _prompt_from_modifiers(target.caption, modifier_state)
            seed = _seed_token(method.id, target.id, repeat_index, round_index, candidate_index, prompt_variant)
            candidate = _render_prompt_image(
                generator=generator,
                artifacts_dir=artifacts_dir,
                config=config,
                prompt=prompt_variant,
                negative_prompt=target.negative_prompt,
                seed=seed,
                candidate_index=candidate_index,
            )
            image_path = _candidate_image_path(artifacts_dir, candidate)
            scores = _score_image(image_path, metric_specs=metric_specs, metric_objects=metric_objects, target_embeddings=target_embeddings)
            candidates.append(
                {
                    "scores": scores,
                    "image_path": str(image_path),
                    "prompt": prompt_variant,
                    "modifiers": modifier_state,
                }
            )
        selected = max(candidates, key=lambda row: (row["scores"]["clip"], row["scores"]["dinov2"]))
        current_modifiers = list(selected["modifiers"])
        if (selected["scores"]["clip"], selected["scores"]["dinov2"]) > (best_so_far["clip"], best_so_far["dinov2"]):
            best_so_far = dict(selected["scores"])
            best_image_path = selected["image_path"]
            best_prompt = selected["prompt"]
        round_best = max(candidates, key=lambda row: (row["scores"]["clip"], row["scores"]["dinov2"]))
        _record_curve_rows(
            run_rows=rows,
            method=method,
            target=target,
            repeat_index=repeat_index,
            round_index=round_index,
            baseline_scores=baseline_payload["scores"],
            round_best=round_best["scores"],
            cumulative_best=best_so_far,
            selected_scores=selected["scores"],
            selected_image_path=selected["image_path"],
            selected_prompt=selected["prompt"],
        )
    return rows, {"final_image_path": best_image_path, "final_prompt": best_prompt, "final_scores": best_so_far}


def _run_no_update_resampling(
    *,
    output_dir: Path,
    generator: Any,
    sampler: Any,
    config: StrategyConfig,
    target: OracleTarget,
    repeat_index: int,
    metric_specs: list[MetricSpec],
    metric_objects: dict[str, Any],
    target_embeddings: dict[str, torch.Tensor],
    baseline_payload: dict[str, Any],
    max_rounds: int,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    method = MethodSpec("no_update_resampling", "No-update resampling", "")
    artifacts_dir = output_dir / "runs" / method.id / target.id / f"repeat_{repeat_index + 1}" / "artifacts"
    artifacts_dir.mkdir(parents=True, exist_ok=True)
    rows: list[dict[str, Any]] = []
    best_so_far = dict(baseline_payload["scores"])
    best_image_path = str(baseline_payload["image_path"])
    base_session = _make_prompt_session(target.caption, target.negative_prompt, config)
    for round_index in range(1, max_rounds + 1):
        generator.artifacts_dir = artifacts_dir
        round_seed = _seed_token(method.id, target.id, repeat_index, round_index)
        proposals = sampler.propose(base_session, round_seed)
        candidates: list[dict[str, Any]] = []
        for candidate_index, proposal in enumerate(proposals[: config.candidate_count]):
            proposal.candidate_index = candidate_index
            proposal.seed = _seed_token(method.id, target.id, repeat_index, round_index, candidate_index, "render")
            rendered = generator.render_candidate(base_session, proposal)
            image_path = _candidate_image_path(artifacts_dir, rendered)
            scores = _score_image(image_path, metric_specs=metric_specs, metric_objects=metric_objects, target_embeddings=target_embeddings)
            candidates.append({"scores": scores, "image_path": str(image_path), "prompt": target.caption})
        round_best = max(candidates, key=lambda row: (row["scores"]["clip"], row["scores"]["dinov2"]))
        if (round_best["scores"]["clip"], round_best["scores"]["dinov2"]) > (best_so_far["clip"], best_so_far["dinov2"]):
            best_so_far = dict(round_best["scores"])
            best_image_path = round_best["image_path"]
        _record_curve_rows(
            run_rows=rows,
            method=method,
            target=target,
            repeat_index=repeat_index,
            round_index=round_index,
            baseline_scores=baseline_payload["scores"],
            round_best=round_best["scores"],
            cumulative_best=best_so_far,
            selected_scores=round_best["scores"],
            selected_image_path=round_best["image_path"],
            selected_prompt=target.caption,
        )
    return rows, {"final_image_path": best_image_path, "final_prompt": target.caption, "final_scores": best_so_far}


def _run_stablesteering_best(
    *,
    output_dir: Path,
    generator: Any,
    config: StrategyConfig,
    target: OracleTarget,
    repeat_index: int,
    metric_specs: list[MetricSpec],
    metric_objects: dict[str, Any],
    target_embeddings: dict[str, torch.Tensor],
    baseline_payload: dict[str, Any],
    max_rounds: int,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    method = MethodSpec("stablesteering_best", "StableSteering best current policy", "")
    run_root = output_dir / "runs" / method.id / target.id / f"repeat_{repeat_index + 1}"
    runtime_root = run_root / "runtime"
    repository = JsonRepository(data_dir=runtime_root)
    generator.artifacts_dir = repository.artifacts_dir
    orchestrator = Orchestrator(repository=repository, generator=generator)
    experiment = orchestrator.create_experiment(
        ExperimentCreate(
            name=f"Budget-matched direct baseline / {target.label} / repeat {repeat_index + 1}",
            description="Direct baseline slice for paper",
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
    rows: list[dict[str, Any]] = []
    best_so_far = dict(baseline_payload["scores"])
    best_image_path = str(baseline_payload["image_path"])
    final_prompt = target.caption

    for round_index in range(1, max_rounds + 1):
        round_response = orchestrator.generate_round(session.id)
        candidates: list[dict[str, Any]] = []
        ranking: list[tuple[str, float, float]] = []
        for candidate in round_response.candidate_metadata:
            image_path = runtime_root / "artifacts" / Path(candidate.image_path or "").name
            scores = _score_image(image_path, metric_specs=metric_specs, metric_objects=metric_objects, target_embeddings=target_embeddings)
            candidates.append({"candidate_id": candidate.id, "scores": scores, "image_path": str(image_path)})
            ranking.append((candidate.id, scores["clip"], scores["dinov2"]))
        ranking.sort(key=lambda item: (-item[1], -item[2], item[0]))
        round_best = max(candidates, key=lambda row: (row["scores"]["clip"], row["scores"]["dinov2"]))
        if (round_best["scores"]["clip"], round_best["scores"]["dinov2"]) > (best_so_far["clip"], best_so_far["dinov2"]):
            best_so_far = dict(round_best["scores"])
            best_image_path = round_best["image_path"]
        ranking_ids = [candidate_id for candidate_id, _, _ in ranking]
        selected = next(row for row in candidates if row["candidate_id"] == ranking_ids[0])
        _record_curve_rows(
            run_rows=rows,
            method=method,
            target=target,
            repeat_index=repeat_index,
            round_index=round_index,
            baseline_scores=baseline_payload["scores"],
            round_best=round_best["scores"],
            cumulative_best=best_so_far,
            selected_scores=selected["scores"],
            selected_image_path=selected["image_path"],
            selected_prompt=final_prompt,
        )
        if round_index < max_rounds:
            round_obj = orchestrator.get_session_rounds(session.id)[-1]
            orchestrator.submit_feedback(
                round_obj.id,
                FeedbackRequest(
                    feedback_type=FeedbackType.top_k,
                    payload={"ranking": ranking_ids},
                    critique_text="Oracle budget-matched direct baseline ranking",
                ),
            )

    trace_report_src = runtime_root / "traces" / "sessions" / session.id / "report.html"
    if trace_report_src.exists():
        shutil.copy2(trace_report_src, run_root / "trace_report.html")
    return rows, {"final_image_path": best_image_path, "final_prompt": final_prompt, "final_scores": best_so_far}


def _curve_summary(curve_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[tuple[str, int], list[dict[str, Any]]] = {}
    for row in curve_rows:
        key = (str(row["method_id"]), int(row["round_index"]))
        grouped.setdefault(key, []).append(row)
    summary_rows: list[dict[str, Any]] = []
    for (method_id, round_index), rows in sorted(grouped.items()):
        summary_rows.append(
            {
                "method_id": method_id,
                "method_label": rows[0]["method_label"],
                "round_index": round_index,
                "mean_best_so_far_clip": round(_safe_mean([float(row["best_so_far_clip"]) for row in rows]), 6),
                "mean_best_so_far_dinov2": round(_safe_mean([float(row["best_so_far_dinov2"]) for row in rows]), 6),
                "mean_selected_clip": round(_safe_mean([float(row["selected_clip"]) for row in rows]), 6),
                "mean_selected_dinov2": round(_safe_mean([float(row["selected_dinov2"]) for row in rows]), 6),
                "mean_baseline_clip": round(_safe_mean([float(row["baseline_clip"]) for row in rows]), 6),
                "mean_baseline_dinov2": round(_safe_mean([float(row["baseline_dinov2"]) for row in rows]), 6),
                "ci_low_best_so_far_clip": round(_bootstrap_mean_ci([float(row["best_so_far_clip"]) for row in rows], seed=round_index * 100 + len(rows))[0], 6),
                "ci_high_best_so_far_clip": round(_bootstrap_mean_ci([float(row["best_so_far_clip"]) for row in rows], seed=round_index * 100 + len(rows))[1], 6),
                "ci_low_best_so_far_dinov2": round(_bootstrap_mean_ci([float(row["best_so_far_dinov2"]) for row in rows], seed=round_index * 200 + len(rows))[0], 6),
                "ci_high_best_so_far_dinov2": round(_bootstrap_mean_ci([float(row["best_so_far_dinov2"]) for row in rows], seed=round_index * 200 + len(rows))[1], 6),
            }
        )
    return summary_rows


def _run_summary(curve_rows: list[dict[str, Any]], methods: list[MethodSpec], max_rounds: int) -> list[dict[str, Any]]:
    by_run: dict[tuple[str, str, int], list[dict[str, Any]]] = {}
    for row in curve_rows:
        key = (str(row["method_id"]), str(row["target_id"]), int(row["repeat_index"]))
        by_run.setdefault(key, []).append(row)
    summary_rows: list[dict[str, Any]] = []
    method_labels = {method.id: method.label for method in methods}
    for (method_id, target_id, repeat_index), rows in sorted(by_run.items()):
        rows = sorted(rows, key=lambda row: int(row["round_index"]))
        first = rows[0]
        last = rows[-1]
        summary_rows.append(
            {
                "method_id": method_id,
                "method_label": method_labels[method_id],
                "target_id": target_id,
                "target_label": last["target_label"],
                "repeat_index": repeat_index,
                "baseline_clip": round(float(first["baseline_clip"]), 6),
                "baseline_dinov2": round(float(first["baseline_dinov2"]), 6),
                "final_best_clip": round(float(last["best_so_far_clip"]), 6),
                "final_best_dinov2": round(float(last["best_so_far_dinov2"]), 6),
                "clip_gain": round(float(last["best_so_far_clip"]) - float(first["baseline_clip"]), 6),
                "dinov2_gain": round(float(last["best_so_far_dinov2"]) - float(first["baseline_dinov2"]), 6),
                "rounds": max_rounds,
                "selected_image_path": last["selected_image_path"],
                "selected_prompt": last["selected_prompt"],
            }
        )
    return summary_rows


def _policy_summary(run_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    for row in run_rows:
        grouped.setdefault(str(row["method_id"]), []).append(row)
    summary_rows: list[dict[str, Any]] = []
    for method_id, rows in sorted(grouped.items()):
        baseline_clip_values = [float(row["baseline_clip"]) for row in rows]
        final_clip_values = [float(row["final_best_clip"]) for row in rows]
        clip_gain_values = [float(row["clip_gain"]) for row in rows]
        baseline_dino_values = [float(row["baseline_dinov2"]) for row in rows]
        final_dino_values = [float(row["final_best_dinov2"]) for row in rows]
        dino_gain_values = [float(row["dinov2_gain"]) for row in rows]
        baseline_clip_ci = _bootstrap_mean_ci(baseline_clip_values, seed=1000 + len(rows))
        final_clip_ci = _bootstrap_mean_ci(final_clip_values, seed=2000 + len(rows))
        clip_gain_ci = _bootstrap_mean_ci(clip_gain_values, seed=3000 + len(rows))
        baseline_dino_ci = _bootstrap_mean_ci(baseline_dino_values, seed=4000 + len(rows))
        final_dino_ci = _bootstrap_mean_ci(final_dino_values, seed=5000 + len(rows))
        dino_gain_ci = _bootstrap_mean_ci(dino_gain_values, seed=6000 + len(rows))
        summary_rows.append(
            {
                "method_id": method_id,
                "method_label": rows[0]["method_label"],
                "runs": len(rows),
                "mean_baseline_clip": round(_safe_mean(baseline_clip_values), 6),
                "mean_final_best_clip": round(_safe_mean(final_clip_values), 6),
                "ci_low_baseline_clip": round(baseline_clip_ci[0], 6),
                "ci_high_baseline_clip": round(baseline_clip_ci[1], 6),
                "ci_low_final_best_clip": round(final_clip_ci[0], 6),
                "ci_high_final_best_clip": round(final_clip_ci[1], 6),
                "mean_clip_gain": round(_safe_mean(clip_gain_values), 6),
                "std_clip_gain": round(_safe_std(clip_gain_values), 6),
                "ci_low_clip_gain": round(clip_gain_ci[0], 6),
                "ci_high_clip_gain": round(clip_gain_ci[1], 6),
                "mean_baseline_dinov2": round(_safe_mean(baseline_dino_values), 6),
                "mean_final_best_dinov2": round(_safe_mean(final_dino_values), 6),
                "ci_low_baseline_dinov2": round(baseline_dino_ci[0], 6),
                "ci_high_baseline_dinov2": round(baseline_dino_ci[1], 6),
                "ci_low_final_best_dinov2": round(final_dino_ci[0], 6),
                "ci_high_final_best_dinov2": round(final_dino_ci[1], 6),
                "mean_dinov2_gain": round(_safe_mean(dino_gain_values), 6),
                "std_dinov2_gain": round(_safe_std(dino_gain_values), 6),
                "ci_low_dinov2_gain": round(dino_gain_ci[0], 6),
                "ci_high_dinov2_gain": round(dino_gain_ci[1], 6),
            }
        )
    return summary_rows


def _build_curve_figure(curve_summary: list[dict[str, Any]], output_path: Path) -> None:
    width = 1180
    height = 780
    left = 92
    right = 42
    top_y = 150
    gap = 86
    panel_height = 245
    plot_width = width - left - right
    bottom_y = top_y + panel_height + gap
    checkpoints = [0, 1, 3, 5]
    methods = list(dict.fromkeys(row["method_id"] for row in curve_summary))
    palette = {
        "prompt_best_of_budget": "#8b5e34",
        "prompt_modifier_search": "#7c3aed",
        "no_update_resampling": "#1d4ed8",
        "stablesteering_best": "#15803d",
    }
    by_method = {
        method_id: {int(row["round_index"]): row for row in curve_summary if row["method_id"] == method_id}
        for method_id in methods
    }
    baseline_clip = float(curve_summary[0]["mean_baseline_clip"])
    baseline_dino = float(curve_summary[0]["mean_baseline_dinov2"])
    all_clip = [baseline_clip] + [float(row["mean_best_so_far_clip"]) for row in curve_summary]
    all_dino = [baseline_dino] + [float(row["mean_best_so_far_dinov2"]) for row in curve_summary]
    all_clip_ci = [baseline_clip] + [float(row["ci_low_best_so_far_clip"]) for row in curve_summary] + [float(row["ci_high_best_so_far_clip"]) for row in curve_summary]
    all_dino_ci = [baseline_dino] + [float(row["ci_low_best_so_far_dinov2"]) for row in curve_summary] + [float(row["ci_high_best_so_far_dinov2"]) for row in curve_summary]
    clip_lo, clip_hi = min(all_clip_ci) - 0.015, max(all_clip_ci) + 0.015
    dino_lo, dino_hi = min(all_dino_ci) - 0.025, max(all_dino_ci) + 0.025
    group_width = 184
    bar_width = 34
    intra_gap = 12
    start_x = left + 72

    def y_pos(value: float, y0: float, lo: float, hi: float) -> float:
        if hi == lo:
            return y0 + panel_height / 2
        return y0 + (1 - ((value - lo) / (hi - lo))) * panel_height

    def bar_x(group_index: int, method_index: int) -> float:
        group_left = start_x + group_index * group_width
        offset = method_index * (bar_width + intra_gap)
        return group_left + offset

    checkpoint_labels = {0: "Baseline", 1: "Round 1", 3: "Round 3", 5: "Final"}

    def ci_keys(value_key: str) -> tuple[str, str]:
        suffix = value_key.removeprefix("mean_")
        return (f"ci_low_{suffix}", f"ci_high_{suffix}")

    def draw_panel(y0: int, lo: float, hi: float, baseline: float, value_key: str, title: str) -> str:
        svg_local = ""
        svg_local += f'  <text class="panel" x="{left}" y="{y0 - 20}">{title}</text>\n'
        svg_local += f'  <line class="axis" x1="{left}" y1="{y0}" x2="{left}" y2="{y0 + panel_height}"/>\n'
        svg_local += f'  <line class="axis" x1="{left}" y1="{y0 + panel_height}" x2="{left + plot_width}" y2="{y0 + panel_height}"/>\n'
        low_key, high_key = ci_keys(value_key)
        for step in range(5):
            value = lo + ((hi - lo) * step / 4)
            y = y_pos(value, y0, lo, hi)
            svg_local += f'  <line class="grid" x1="{left}" y1="{y:.1f}" x2="{left + plot_width}" y2="{y:.1f}"/>\n'
            svg_local += f'  <text class="tick" x="{left - 12}" y="{y + 4:.1f}" text-anchor="end">{value:.3f}</text>\n'
        for group_index, checkpoint in enumerate(checkpoints):
            group_left = start_x + group_index * group_width - 20
            group_center = group_left + ((len(methods) * bar_width + (len(methods) - 1) * intra_gap) / 2) + 20
            svg_local += f'  <text class="group" x="{group_center:.1f}" y="{y0 + panel_height + 28}" text-anchor="middle">{checkpoint_labels[checkpoint]}</text>\n'
            for method_index, method_id in enumerate(methods):
                if checkpoint == 0:
                    value = baseline
                    ci_low = baseline
                    ci_high = baseline
                else:
                    row = by_method[method_id][checkpoint]
                    value = float(row[value_key])
                    ci_low = float(row[low_key])
                    ci_high = float(row[high_key])
                x = bar_x(group_index, method_index)
                y = y_pos(value, y0, lo, hi)
                height_px = (y0 + panel_height) - y
                color = palette.get(method_id, "#222222")
                svg_local += f'  <rect x="{x:.1f}" y="{y:.1f}" width="{bar_width}" height="{height_px:.1f}" rx="3" fill="{color}" opacity="0.92"/>\n'
                err_x = x + (bar_width / 2)
                err_low_y = y_pos(ci_low, y0, lo, hi)
                err_high_y = y_pos(ci_high, y0, lo, hi)
                svg_local += f'  <line class="error" x1="{err_x:.1f}" y1="{err_low_y:.1f}" x2="{err_x:.1f}" y2="{err_high_y:.1f}"/>\n'
                svg_local += f'  <line class="error" x1="{err_x - 7:.1f}" y1="{err_low_y:.1f}" x2="{err_x + 7:.1f}" y2="{err_low_y:.1f}"/>\n'
                svg_local += f'  <line class="error" x1="{err_x - 7:.1f}" y1="{err_high_y:.1f}" x2="{err_x + 7:.1f}" y2="{err_high_y:.1f}"/>\n'
                svg_local += f'  <text class="value" x="{x + bar_width / 2:.1f}" y="{y - 8:.1f}" text-anchor="middle">{value:.3f}</text>\n'
        return svg_local

    svg = f"""<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}" role="img" aria-labelledby="title desc">
  <title id="title">Budget-matched direct baseline comparison at selected checkpoints</title>
  <desc id="desc">Two-panel grouped bar chart comparing direct baselines and StableSteering at baseline, round 1, round 3, and final under a shared 20-image budget.</desc>
  <style>
    .bg {{ fill: #fbfaf6; }}
    .axis {{ stroke: #475467; stroke-width: 2.1; }}
    .grid {{ stroke: #e2d8c8; stroke-width: 1.0; }}
    .title {{ font: 700 29px Georgia, 'Times New Roman', serif; fill: #1f2937; }}
    .subtitle {{ font: 16px Georgia, 'Times New Roman', serif; fill: #334155; }}
    .tick {{ font: 14px Georgia, 'Times New Roman', serif; fill: #334155; }}
    .panel {{ font: 700 18px Georgia, 'Times New Roman', serif; fill: #1f2937; }}
    .legend {{ font: 14px Georgia, 'Times New Roman', serif; fill: #1f2937; }}
    .group {{ font: 700 15px Georgia, 'Times New Roman', serif; fill: #334155; }}
    .value {{ font: 12px Georgia, 'Times New Roman', serif; fill: #1f2937; }}
    .error {{ stroke: #111827; stroke-width: 1.6; }}
  </style>
  <rect class="bg" width="{width}" height="{height}"/>
  <text class="title" x="70" y="50">Budget-Matched Direct Baselines at Selected Checkpoints</text>
  <text class="subtitle" x="70" y="77">Bars show mean best-so-far recovery at baseline, round 1, round 3, and final under the same 20-image budget; error bars show 95% bootstrap confidence intervals.</text>
"""
    svg += draw_panel(top_y, clip_lo, clip_hi, baseline_clip, "mean_best_so_far_clip", "CLIP cosine to target")
    svg += draw_panel(bottom_y, dino_lo, dino_hi, baseline_dino, "mean_best_so_far_dinov2", "DINOv2 cosine to target")
    legend_x = 742
    legend_y = 110
    for index, method_id in enumerate(methods):
        color = palette.get(method_id, "#222222")
        label = next(iter(by_method[method_id].values()))["method_label"]
        y = legend_y + (index * 25)
        svg += f'  <rect x="{legend_x}" y="{y - 12}" width="22" height="14" rx="2" fill="{color}"/>\n'
        svg += f'  <text class="legend" x="{legend_x + 30}" y="{y}">{label}</text>\n'
    svg += "</svg>\n"
    _write_text(output_path, svg)


def _build_examples_figure(
    *,
    output_path: Path,
    targets: list[OracleTarget],
    best_examples: dict[tuple[str, str], dict[str, Any]],
) -> None:
    methods = ["prompt_best_of_budget", "prompt_modifier_search", "stablesteering_best"]
    labels = {
        "prompt_best_of_budget": "Prompt-only best",
        "prompt_modifier_search": "Prompt-rewrite best",
        "stablesteering_best": "StableSteering best",
    }
    card_width = 240
    card_height = 260
    padding = 18
    columns = 4
    width = padding + columns * (card_width + padding)
    height = padding + len(targets) * (card_height + 70)
    canvas = Image.new("RGB", (width, height), "#fbfaf6")
    draw = ImageDraw.Draw(canvas)
    body_font = _font(14)
    for row_index, target in enumerate(targets):
        y = padding + row_index * (card_height + 70)
        target_path = Path(best_examples[(target.id, "target")]["image_path"])
        target_image = ImageOps.fit(Image.open(target_path).convert("RGB"), (card_width, card_height), method=Image.Resampling.LANCZOS)
        x = padding
        canvas.paste(target_image, (x, y + 24))
        draw.rectangle([x, y + 24, x + card_width, y + 24 + card_height], outline="#d2c5b3", width=2)
        draw.multiline_text((x + 6, y), f"{target.label}\nTarget", fill="#1f1b17", font=body_font, spacing=3)
        for col_index, method_id in enumerate(methods, start=1):
            entry = best_examples[(target.id, method_id)]
            image = ImageOps.fit(Image.open(Path(entry["image_path"])).convert("RGB"), (card_width, card_height), method=Image.Resampling.LANCZOS)
            x = padding + col_index * (card_width + padding)
            canvas.paste(image, (x, y + 24))
            draw.rectangle([x, y + 24, x + card_width, y + 24 + card_height], outline="#d2c5b3", width=2)
            draw.multiline_text(
                (x + 6, y),
                f"{labels[method_id]}\nCLIP {entry['clip']:.3f} | DINO {entry['dinov2']:.3f}",
                fill="#1f1b17",
                font=body_font,
                spacing=3,
            )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(output_path)


def _analysis_markdown(policy_summary: list[dict[str, Any]], suite: dict[str, Any]) -> str:
    ordered = sorted(policy_summary, key=lambda row: float(row["mean_final_best_clip"]), reverse=True)
    dataset = suite.get("dataset", {})
    method_count = len(suite.get("methods", []))
    target_count = len(suite.get("targets", []))
    repeats = int(suite.get("repeats_per_target", 1))
    max_rounds = int(suite.get("max_rounds", 0))
    candidates_per_round = int(suite.get("fixed_conditions", {}).get("candidate_count", 0))
    total_runs = method_count * target_count * repeats
    total_candidates = total_runs * max_rounds * candidates_per_round
    lines = [
        "# Budget-Matched Direct Baseline Comparison",
        "",
        "This bundle compares four methods under the same visible candidate budget.",
        "",
        "## Dataset and scope",
        "",
        f"- dataset: `{dataset.get('name', 'unspecified')}`",
        f"- source: `{dataset.get('source', 'unspecified')}`",
        f"- split: `{dataset.get('split', 'unspecified')}`",
        f"- selected targets: `{dataset.get('selected_target_count', target_count)}`",
        f"- caption field used as the prompt: `{dataset.get('caption_field', 'unspecified')}`",
        f"- repeats per target: `{repeats}`",
        f"- methods compared: `{method_count}`",
        f"- total runs: `{total_runs}`",
        f"- rounds per run: `{max_rounds}`",
        f"- candidates per round: `{candidates_per_round}`",
        f"- total generated candidates: `{total_candidates}`",
        "",
        "## Headline results",
        "",
    ]
    for row in ordered:
        lines.append(
            f"- `{row['method_id']}`: final CLIP `{row['mean_final_best_clip']:.3f}` "
            f"(95% CI `{row['ci_low_final_best_clip']:.3f}` to `{row['ci_high_final_best_clip']:.3f}`, gain `{row['mean_clip_gain']:+.3f}`), "
            f"final DINOv2 `{row['mean_final_best_dinov2']:.3f}` "
            f"(95% CI `{row['ci_low_final_best_dinov2']:.3f}` to `{row['ci_high_final_best_dinov2']:.3f}`, gain `{row['mean_dinov2_gain']:+.3f}`)"
        )
    lines.extend(
        [
            "",
            "## Exact final values",
            "",
            "| method | runs | final CLIP (mean, 95% CI) | final DINOv2 (mean, 95% CI) |",
            "| --- | ---: | ---: | ---: |",
        ]
    )
    for row in ordered:
        lines.append(
            f"| {row['method_label']} | {row['runs']} | "
            f"{row['mean_final_best_clip']:.3f} ({row['ci_low_final_best_clip']:.3f}, {row['ci_high_final_best_clip']:.3f}) | "
            f"{row['mean_final_best_dinov2']:.3f} ({row['ci_low_final_best_dinov2']:.3f}, {row['ci_high_final_best_dinov2']:.3f}) |"
        )
    lines.extend(
        [
            "",
            "## Interpretation",
            "",
            "- `prompt_best_of_budget` answers whether simple seed search under the same budget is sufficient.",
            "- `prompt_modifier_search` is a direct but heuristic prompt-editing baseline: it rewrites the prompt through a fixed library of textual modifiers rather than through latent steering.",
            "- `no_update_resampling` asks whether diversity alone is enough without state updates.",
            "- `stablesteering_best` tests whether the current best loop uses the same budget more effectively.",
            "- Confidence intervals are bootstrapped over run-level final outcomes.",
            "",
            "This comparison is stronger than the earlier workflow pilot because all methods now consume the same visible candidate budget. It is still conservative: the prompt-rewrite arm is heuristic rather than a full language-model prompt optimizer.",
            "",
            f"Targets: `{target_count}`; repeats per target: `{repeats}`; total method runs: `{total_runs}`.",
        ]
    )
    return "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--suite",
        type=Path,
        default=_paper_root() / "protocols" / "budget_matched_direct_baselines_suite.yaml",
        help="Path to the locked protocol YAML.",
    )
    parser.add_argument("--output-dir", type=Path, default=_results_root(), help="Where to write the result bundle.")
    parser.add_argument("--backend", default="diffusers", help="Generation backend to use.")
    args = parser.parse_args()

    suite = _read_yaml(args.suite)
    output_dir = args.output_dir
    if output_dir.exists():
        shutil.rmtree(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy2(args.suite, output_dir / "protocol_snapshot.yaml")

    config = _strategy_config_from_suite(suite)
    methods = _methods_from_suite(suite)
    targets = _load_targets(suite)
    metric_specs = _metric_specs_from_suite(suite)
    metric_objects = _build_metric_objects(metric_specs, str(suite["oracle_model"]))
    generator = build_generation_engine(
        backend=args.backend,
        artifacts_dir=output_dir / "scratch_artifacts",
        num_inference_steps=config.num_inference_steps,
    )
    baseline_sampler = Orchestrator(repository=JsonRepository(data_dir=output_dir / "_tmp"), generator=generator).samplers[config.sampler]
    modifier_library = [str(item) for item in suite.get("prompt_rewrite_modifiers", [])]

    all_curve_rows: list[dict[str, Any]] = []
    best_examples: dict[tuple[str, str], dict[str, Any]] = {}

    for target in targets:
        target_dir = output_dir / "targets"
        target_name = Path(target.image_url.split("/")[-1]).name or f"{target.id}.jpg"
        target_path = target_dir / target_name
        _download(target.image_url, target_path)
        target_embeddings = {spec.short_name: metric_objects[spec.short_name].embed_image(target_path) for spec in metric_specs}
        best_examples[(target.id, "target")] = {"image_path": str(target_path), "clip": 0.0, "dinov2": 0.0}

        for repeat_index in range(int(suite.get("repeats_per_target", 1))):
            baseline_payload = _build_baseline_image(
                output_dir=output_dir,
                generator=generator,
                config=config,
                target=target,
                repeat_index=repeat_index,
                metric_specs=metric_specs,
                metric_objects=metric_objects,
                target_embeddings=target_embeddings,
            )
            for method in methods:
                if method.id == "prompt_best_of_budget":
                    curve_rows, final_payload = _run_prompt_best_of_budget(
                        output_dir=output_dir,
                        generator=generator,
                        config=config,
                        target=target,
                        repeat_index=repeat_index,
                        metric_specs=metric_specs,
                        metric_objects=metric_objects,
                        target_embeddings=target_embeddings,
                        baseline_payload=baseline_payload,
                        max_rounds=int(suite["max_rounds"]),
                    )
                elif method.id == "prompt_modifier_search":
                    curve_rows, final_payload = _run_prompt_modifier_search(
                        output_dir=output_dir,
                        generator=generator,
                        config=config,
                        target=target,
                        repeat_index=repeat_index,
                        metric_specs=metric_specs,
                        metric_objects=metric_objects,
                        target_embeddings=target_embeddings,
                        baseline_payload=baseline_payload,
                        max_rounds=int(suite["max_rounds"]),
                        modifier_library=modifier_library,
                    )
                elif method.id == "no_update_resampling":
                    curve_rows, final_payload = _run_no_update_resampling(
                        output_dir=output_dir,
                        generator=generator,
                        sampler=baseline_sampler,
                        config=config,
                        target=target,
                        repeat_index=repeat_index,
                        metric_specs=metric_specs,
                        metric_objects=metric_objects,
                        target_embeddings=target_embeddings,
                        baseline_payload=baseline_payload,
                        max_rounds=int(suite["max_rounds"]),
                    )
                elif method.id == "stablesteering_best":
                    curve_rows, final_payload = _run_stablesteering_best(
                        output_dir=output_dir,
                        generator=generator,
                        config=config,
                        target=target,
                        repeat_index=repeat_index,
                        metric_specs=metric_specs,
                        metric_objects=metric_objects,
                        target_embeddings=target_embeddings,
                        baseline_payload=baseline_payload,
                        max_rounds=int(suite["max_rounds"]),
                    )
                else:
                    raise ValueError(f"Unsupported method id: {method.id}")
                all_curve_rows.extend(curve_rows)
                current_best = best_examples.get((target.id, method.id))
                final_scores = final_payload["final_scores"]
                if current_best is None or (final_scores["clip"], final_scores["dinov2"]) > (current_best["clip"], current_best["dinov2"]):
                    best_examples[(target.id, method.id)] = {
                        "image_path": final_payload["final_image_path"],
                        "clip": final_scores["clip"],
                        "dinov2": final_scores["dinov2"],
                    }

    tables_dir = output_dir / "tables"
    analysis_dir = output_dir / "analysis"
    figures_dir = output_dir / "figures"
    curve_summary = _curve_summary(all_curve_rows)
    run_summary = _run_summary(all_curve_rows, methods, int(suite["max_rounds"]))
    policy_summary = _policy_summary(run_summary)
    _write_csv(tables_dir / "curve_summary.csv", curve_summary, list(curve_summary[0].keys()))
    _write_csv(tables_dir / "run_summary.csv", run_summary, list(run_summary[0].keys()))
    _write_csv(tables_dir / "policy_summary.csv", policy_summary, list(policy_summary[0].keys()))
    curve_figure = figures_dir / "budget_matched_direct_baselines_curve.svg"
    _build_curve_figure(curve_summary, curve_figure)
    examples_figure = figures_dir / "budget_matched_direct_baselines_examples.png"
    _build_examples_figure(output_path=examples_figure, targets=targets, best_examples=best_examples)
    analysis_md = _analysis_markdown(policy_summary, suite)
    _write_text(analysis_dir / "analysis_summary.md", analysis_md)
    _markdown_to_html("Budget-Matched Direct Baseline Comparison", analysis_md, analysis_dir / "analysis_summary.html")
    _write_text(
        output_dir / "README.md",
        "\n".join(
            [
                "# Budget-Matched Direct Baseline Comparison",
                "",
                "This bundle compares prompt-only seed search, heuristic prompt rewriting, no-update resampling, and StableSteering under the same candidate budget.",
                "",
                "Primary outputs:",
                "",
                "- `tables/policy_summary.csv`",
                "- `analysis/analysis_summary.md`",
                "- `figures/budget_matched_direct_baselines_curve.svg`",
                "- `figures/budget_matched_direct_baselines_examples.png`",
                "",
                "The comparison is direct and budget-matched, but still conservative: the prompt-rewrite arm is heuristic rather than a full language-model prompt optimizer.",
                "",
            ]
        ),
    )
    _write_json(
        output_dir / "manifest.json",
        {
            "suite_name": suite["suite_name"],
            "description": suite["description"],
            "methods": [method.__dict__ for method in methods],
            "targets": [target.__dict__ for target in targets],
            "dataset": suite.get("dataset", {}),
            "repeats_per_target": int(suite["repeats_per_target"]),
            "max_rounds": int(suite["max_rounds"]),
            "artifacts": {
                "curve_summary": str(tables_dir / "curve_summary.csv"),
                "run_summary": str(tables_dir / "run_summary.csv"),
                "policy_summary": str(tables_dir / "policy_summary.csv"),
                "curve_figure": str(curve_figure),
                "examples_figure": str(examples_figure),
                "analysis_summary": str(analysis_dir / "analysis_summary.md"),
            },
        },
    )


if __name__ == "__main__":
    main()
