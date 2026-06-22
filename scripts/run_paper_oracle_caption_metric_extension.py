from __future__ import annotations

import argparse
import json
import math
import random
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import markdown
import torch
import yaml
from PIL import Image
from torchvision.transforms import functional as TF

from app.bootstrap.experiment_models import (
    get_clip_components,
    get_dino_components,
    get_lpips_metric,
    get_siglip_components,
)
from app.core.schema import ExperimentCreate, FeedbackRequest, FeedbackType, SessionCreate, StrategyConfig
from app.engine.generation import build_generation_engine
from app.engine.orchestrator import Orchestrator
from app.storage.repository import JsonRepository
from run_paper_oracle_target_recovery import _artifact_path, _paper_root, _write_csv, _write_json, _write_text


@dataclass(frozen=True)
class TargetRecord:
    target_id: str
    label: str
    image_path: Path
    human_caption: str


@dataclass(frozen=True)
class MetricSpec:
    id: str
    short_name: str
    label: str
    kind: str
    higher_is_better: bool


class ClipMetric:
    def __init__(self, model_id: str, device: str = "cpu") -> None:
        self.processor = None
        self.model = None
        self.device = device
        self.model_id = model_id
        self._embedding_cache: dict[str, torch.Tensor] = {}
        self.model, self.processor = get_clip_components(model_id, device, local_only=False)

    def embed_image(self, image_path: Path) -> torch.Tensor:
        key = str(image_path)
        cached = self._embedding_cache.get(key)
        if cached is not None:
            return cached
        image = Image.open(image_path).convert("RGB")
        inputs = self.processor(images=image, return_tensors="pt")
        inputs = {name: value.to(self.device) for name, value in inputs.items()}
        with torch.no_grad():
            features = self.model.get_image_features(**inputs)
        if not isinstance(features, torch.Tensor):
            if hasattr(features, "image_embeds") and features.image_embeds is not None:
                features = features.image_embeds
            elif hasattr(features, "pooler_output") and features.pooler_output is not None:
                features = features.pooler_output
            elif hasattr(features, "last_hidden_state") and features.last_hidden_state is not None:
                features = features.last_hidden_state[:, 0, :]
            else:
                raise TypeError(f"Unsupported CLIP image feature output type: {type(features)!r}")
        features = features / features.norm(dim=-1, keepdim=True)
        cached = features[0].detach().cpu()
        self._embedding_cache[key] = cached
        return cached

    @staticmethod
    def score(candidate_embedding: torch.Tensor, target_embedding: torch.Tensor) -> float:
        return float(torch.dot(candidate_embedding, target_embedding).item())


class DINOv2Metric:
    def __init__(self, model_id: str, device: str = "cpu") -> None:
        self.processor, self.model = get_dino_components(model_id, device, local_only=False)
        self.device = device
        self._embedding_cache: dict[str, torch.Tensor] = {}

    def embed_image(self, image_path: Path) -> torch.Tensor:
        key = str(image_path)
        cached = self._embedding_cache.get(key)
        if cached is not None:
            return cached
        image = Image.open(image_path).convert("RGB")
        inputs = self.processor(images=image, return_tensors="pt")
        inputs = {name: value.to(self.device) for name, value in inputs.items()}
        with torch.no_grad():
            outputs = self.model(**inputs)
        if hasattr(outputs, "pooler_output") and outputs.pooler_output is not None:
            features = outputs.pooler_output
        else:
            features = outputs.last_hidden_state[:, 0, :]
        features = features / features.norm(dim=-1, keepdim=True)
        cached = features[0].detach().cpu()
        self._embedding_cache[key] = cached
        return cached

    @staticmethod
    def score(candidate_embedding: torch.Tensor, target_embedding: torch.Tensor) -> float:
        return float(torch.dot(candidate_embedding, target_embedding).item())


class SigLIPMetric:
    def __init__(self, model_id: str, device: str = "cpu") -> None:
        self.processor, self.model = get_siglip_components(model_id, device, local_only=False)
        self.device = device
        self._embedding_cache: dict[str, torch.Tensor] = {}

    def embed_image(self, image_path: Path) -> torch.Tensor:
        key = str(image_path)
        cached = self._embedding_cache.get(key)
        if cached is not None:
            return cached
        image = Image.open(image_path).convert("RGB")
        inputs = self.processor(images=image, return_tensors="pt")
        inputs = {name: value.to(self.device) for name, value in inputs.items()}
        with torch.no_grad():
            features = self.model.get_image_features(**inputs)
        if not isinstance(features, torch.Tensor):
            if hasattr(features, "image_embeds") and features.image_embeds is not None:
                features = features.image_embeds
            elif hasattr(features, "pooler_output") and features.pooler_output is not None:
                features = features.pooler_output
            elif hasattr(features, "last_hidden_state") and features.last_hidden_state is not None:
                features = features.last_hidden_state[:, 0, :]
            else:
                raise TypeError(f"Unsupported SigLIP image feature output type: {type(features)!r}")
        features = features / features.norm(dim=-1, keepdim=True)
        cached = features[0].detach().cpu()
        self._embedding_cache[key] = cached
        return cached

    @staticmethod
    def score(candidate_embedding: torch.Tensor, target_embedding: torch.Tensor) -> float:
        return float(torch.dot(candidate_embedding, target_embedding).item())


class LPIPSMetric:
    def __init__(self, model_id: str, device: str = "cpu") -> None:
        self.device = device
        self.net_name = model_id.replace("lpips-", "", 1)
        self.model = get_lpips_metric(self.net_name, device)
        self._tensor_cache: dict[str, torch.Tensor] = {}
        self.eval_size = 256

    def image_tensor(self, image_path: Path) -> torch.Tensor:
        key = str(image_path)
        cached = self._tensor_cache.get(key)
        if cached is not None:
            return cached
        image = Image.open(image_path).convert("RGB")
        image = TF.resize(image, [self.eval_size, self.eval_size], antialias=True)
        tensor = TF.to_tensor(image).unsqueeze(0).to(self.device)
        tensor = (tensor * 2.0) - 1.0
        self._tensor_cache[key] = tensor
        return tensor

    def score(self, candidate_tensor: torch.Tensor, target_tensor: torch.Tensor) -> float:
        with torch.no_grad():
            value = self.model(candidate_tensor, target_tensor)
        return float(value.reshape(-1)[0].item())


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _results_root() -> Path:
    return _paper_root() / "results" / "oracle_caption_metric_extension"


def _read_yaml(path: Path) -> dict[str, Any]:
    payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"Expected YAML mapping in {path}")
    return payload


def _read_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"Expected JSON object in {path}")
    return payload


def _bootstrap_mean_ci(values: list[float], *, seed: int = 0, samples: int = 3000) -> tuple[float, float]:
    if not values:
        return (0.0, 0.0)
    if len(values) == 1:
        return (values[0], values[0])
    rng = random.Random(seed)
    sample_means: list[float] = []
    count = len(values)
    for _ in range(samples):
        drawn = [values[rng.randrange(count)] for _ in range(count)]
        sample_means.append(sum(drawn) / count)
    sample_means.sort()
    return (sample_means[int(0.025 * samples)], sample_means[int(0.975 * samples)])


def _safe_mean(values: list[float]) -> float:
    return sum(values) / len(values) if values else 0.0


def _resolve_targets(suite: dict[str, Any]) -> list[TargetRecord]:
    manifest = _read_json(Path(str(suite["dataset_manifest"])))
    selected_ids = set(str(value) for value in suite.get("target_ids", []))
    rows: list[TargetRecord] = []
    for target in manifest.get("targets", []):
        target_id = str(target["target_id"])
        if selected_ids and target_id not in selected_ids:
            continue
        rows.append(
            TargetRecord(
                target_id=target_id,
                label=str(target.get("caption_0") or target.get("caption") or target_id),
                image_path=Path(str(target["image_path"])),
                human_caption=str(target.get("caption_0") or target.get("caption") or ""),
            )
        )
    if not rows:
        raise ValueError("No targets resolved from the manifest.")
    return rows


def _metric_specs_from_suite(suite: dict[str, Any]) -> list[MetricSpec]:
    specs: list[MetricSpec] = []
    for record in suite.get("evaluation_models", []):
        kind = str(record["kind"])
        specs.append(
            MetricSpec(
                id=str(record["id"]),
                short_name=str(record["short_name"]),
                label=str(record["label"]),
                kind=kind,
                higher_is_better=kind != "lpips",
            )
        )
    return specs


def _metric_objects(metric_specs: list[MetricSpec]) -> dict[str, Any]:
    metrics: dict[str, Any] = {}
    for spec in metric_specs:
        if spec.kind == "clip":
            metrics[spec.short_name] = ClipMetric(spec.id, device="cpu")
        elif spec.kind == "dinov2":
            metrics[spec.short_name] = DINOv2Metric(spec.id, device="cpu")
        elif spec.kind == "siglip":
            metrics[spec.short_name] = SigLIPMetric(spec.id, device="cpu")
        elif spec.kind == "lpips":
            metrics[spec.short_name] = LPIPSMetric(spec.id, device="cpu")
        else:
            raise ValueError(f"Unsupported metric kind: {spec.kind}")
    return metrics


def _metric_target_representations(targets: list[TargetRecord], metric_specs: list[MetricSpec], metric_objects: dict[str, Any]) -> dict[str, dict[str, Any]]:
    representations: dict[str, dict[str, Any]] = {}
    for target in targets:
        per_metric: dict[str, Any] = {}
        for spec in metric_specs:
            metric = metric_objects[spec.short_name]
            if spec.kind == "lpips":
                per_metric[spec.short_name] = metric.image_tensor(target.image_path)
            else:
                per_metric[spec.short_name] = metric.embed_image(target.image_path)
        representations[target.target_id] = per_metric
    return representations


def _strategy_config(suite: dict[str, Any]) -> StrategyConfig:
    payload = dict(suite.get("fixed_conditions", {}))
    return StrategyConfig.model_validate(payload)


def _oracle_score_rows(rows: list[dict[str, Any]], policy_id: str) -> list[dict[str, Any]]:
    def rescale(values: list[float], *, higher_is_better: bool) -> list[float]:
        if not values:
            return []
        if not higher_is_better:
            values = [-value for value in values]
        lo = min(values)
        hi = max(values)
        if hi - lo < 1e-8:
            return [1.0 for _ in values]
        return [(value - lo) / (hi - lo) for value in values]

    if policy_id == "clip_only":
        for row in rows:
            row["oracle_score"] = float(row["clip_score"])
        return rows

    if policy_id == "siglip_only":
        for row in rows:
            row["oracle_score"] = float(row["siglip_score"])
        return rows

    if policy_id != "multimetric_mix":
        raise ValueError(f"Unsupported oracle policy: {policy_id}")

    clip_scaled = rescale([float(row["clip_score"]) for row in rows], higher_is_better=True)
    siglip_scaled = rescale([float(row["siglip_score"]) for row in rows], higher_is_better=True)
    dino_scaled = rescale([float(row["dinov2_score"]) for row in rows], higher_is_better=True)
    lpips_scaled = rescale([float(row["lpips_score"]) for row in rows], higher_is_better=False)
    for row, clip_value, siglip_value, dino_value, lpips_value in zip(
        rows,
        clip_scaled,
        siglip_scaled,
        dino_scaled,
        lpips_scaled,
        strict=True,
    ):
        row["oracle_score"] = (0.35 * clip_value) + (0.30 * siglip_value) + (0.20 * dino_value) + (0.15 * lpips_value)
    return rows


def _feedback_request(rows: list[dict[str, Any]], critique_text: str) -> FeedbackRequest:
    sorted_rows = sorted(rows, key=lambda row: (-float(row["oracle_score"]), row["candidate_id"]))
    return FeedbackRequest(
        feedback_type=FeedbackType.winner_only,
        payload={"winner_candidate_id": sorted_rows[0]["candidate_id"]},
        critique_text=critique_text,
    )


def _run_one_condition(
    *,
    suite: dict[str, Any],
    output_dir: Path,
    slice_name: str,
    condition_id: str,
    condition_label: str,
    caption_text: str,
    oracle_policy: str,
    target: TargetRecord,
    repeat_index: int,
    metric_specs: list[MetricSpec],
    metric_objects: dict[str, Any],
    target_representations: dict[str, dict[str, Any]],
    backend: str,
) -> dict[str, Any]:
    config = _strategy_config(suite)
    runtime_root = output_dir / "runs" / slice_name / condition_id / target.target_id / f"repeat_{repeat_index + 1}" / "runtime"
    repository = JsonRepository(data_dir=runtime_root)
    generator = build_generation_engine(
        backend=backend,
        artifacts_dir=repository.artifacts_dir,
        num_inference_steps=config.num_inference_steps,
    )
    orchestrator = Orchestrator(repository=repository, generator=generator)
    experiment = orchestrator.create_experiment(
        ExperimentCreate(
            name=f"{slice_name}:{condition_id}",
            description=condition_label,
            config=config,
        )
    )
    session = orchestrator.create_session(
        SessionCreate(
            experiment_id=experiment.id,
            prompt=caption_text,
            negative_prompt=(
                "low detail, blur, distorted anatomy, extra limbs, malformed objects, text, watermark, logo, collage, frame"
            ),
        )
    )

    round_rows: list[dict[str, Any]] = []
    baseline_metrics: dict[str, float] | None = None
    final_metrics: dict[str, float] | None = None
    final_winner_image_path = ""
    for _round_index in range(int(suite[slice_name]["max_rounds"])):
        response = orchestrator.generate_round(session.id)
        scored_rows: list[dict[str, Any]] = []
        for candidate in response.candidate_metadata:
            candidate_path = _artifact_path(runtime_root, candidate.image_path)
            metric_values: dict[str, float] = {}
            for spec in metric_specs:
                target_value = target_representations[target.target_id][spec.short_name]
                metric = metric_objects[spec.short_name]
                if spec.kind == "lpips":
                    candidate_value = metric.image_tensor(candidate_path)
                    score = metric.score(candidate_value, target_value)
                else:
                    candidate_embedding = metric.embed_image(candidate_path)
                    score = metric.score(candidate_embedding, target_value)
                metric_values[f"{spec.short_name}_score"] = round(float(score), 6)
            scored_rows.append(
                {
                    "round_index": response.state_summary["round_index"],
                    "candidate_id": candidate.id,
                    "candidate_index": candidate.candidate_index,
                    "sampler_role": candidate.sampler_role,
                    "image_path": str(candidate_path),
                    **metric_values,
                }
            )
        _oracle_score_rows(scored_rows, oracle_policy)

        if baseline_metrics is None:
            baseline_row = next(
                (
                    row
                    for row, candidate in zip(scored_rows, response.candidate_metadata, strict=True)
                    if candidate.generation_params.get("baseline_prompt")
                ),
                scored_rows[0],
            )
            baseline_metrics = {key: float(value) for key, value in baseline_row.items() if key.endswith("_score")}

        feedback = _feedback_request(
            scored_rows,
            critique_text=f"Oracle policy {oracle_policy} selected the strongest candidate for hidden-target recovery.",
        )
        feedback_response = orchestrator.submit_feedback(response.round_id, feedback)
        winner_id = feedback_response.update_summary["winner_candidate_id"]
        winner_row = next(row for row in scored_rows if row["candidate_id"] == winner_id)
        final_metrics = {key: float(value) for key, value in winner_row.items() if key.endswith("_score")}
        final_winner_image_path = str(winner_row["image_path"])
        for row in scored_rows:
            round_rows.append(
                {
                    "slice_name": slice_name,
                    "condition_id": condition_id,
                    "condition_label": condition_label,
                    "target_id": target.target_id,
                    "target_label": target.label,
                    "prompt_text": caption_text,
                    "repeat_index": repeat_index + 1,
                    "winner_candidate_id": winner_id,
                    "winner_selected": row["candidate_id"] == winner_id,
                    **row,
                }
            )

    if baseline_metrics is None or final_metrics is None:
        raise RuntimeError("Oracle run did not produce baseline/final metrics.")
    return {
        "slice_name": slice_name,
        "condition_id": condition_id,
        "condition_label": condition_label,
        "target_id": target.target_id,
        "target_label": target.label,
        "prompt_text": caption_text,
        "repeat_index": repeat_index + 1,
        "max_rounds": int(suite[slice_name]["max_rounds"]),
        "baseline_image_path": "",
        "final_winner_image_path": final_winner_image_path,
        **{f"baseline_{name}": value for name, value in baseline_metrics.items()},
        **{f"final_{name}": value for name, value in final_metrics.items()},
        "round_rows": round_rows,
    }


def _summarize_slice(run_rows: list[dict[str, Any]], metric_specs: list[MetricSpec]) -> list[dict[str, Any]]:
    summary_rows: list[dict[str, Any]] = []
    conditions = sorted({(row["condition_id"], row["condition_label"]) for row in run_rows}, key=lambda item: item[0])
    for condition_id, condition_label in conditions:
        cell_rows = [row for row in run_rows if row["condition_id"] == condition_id]
        summary_row = {
            "condition_id": condition_id,
            "condition_label": condition_label,
            "run_count": len(cell_rows),
            "target_count": len({row["target_id"] for row in cell_rows}),
        }
        for spec in metric_specs:
            baseline_values = [float(row[f"baseline_{spec.short_name}_score"]) for row in cell_rows]
            final_values = [float(row[f"final_{spec.short_name}_score"]) for row in cell_rows]
            delta_values = [final - base for base, final in zip(baseline_values, final_values, strict=True)]
            ci_low, ci_high = _bootstrap_mean_ci(final_values, seed=hash((condition_id, spec.short_name)) % 100_000)
            delta_ci_low, delta_ci_high = _bootstrap_mean_ci(delta_values, seed=hash((condition_id, spec.short_name, "delta")) % 100_000)
            summary_row[f"mean_baseline_{spec.short_name}"] = round(_safe_mean(baseline_values), 6)
            summary_row[f"mean_final_{spec.short_name}"] = round(_safe_mean(final_values), 6)
            summary_row[f"mean_delta_{spec.short_name}"] = round(_safe_mean(delta_values), 6)
            summary_row[f"ci_low_final_{spec.short_name}"] = round(ci_low, 6)
            summary_row[f"ci_high_final_{spec.short_name}"] = round(ci_high, 6)
            summary_row[f"ci_low_delta_{spec.short_name}"] = round(delta_ci_low, 6)
            summary_row[f"ci_high_delta_{spec.short_name}"] = round(delta_ci_high, 6)
        summary_rows.append(summary_row)
    return summary_rows


def _markdown_to_html(title: str, markdown_text: str, output_path: Path) -> None:
    body = markdown.markdown(markdown_text, extensions=["extra", "tables", "sane_lists"], output_format="html5")
    html_payload = f"""<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>{title}</title>
    <style>
      body {{ margin: 0; background: #f3ece2; color: #201a15; font-family: Georgia, "Times New Roman", serif; }}
      main {{ max-width: 1020px; margin: 0 auto; padding: 28px 18px 48px; }}
      article {{ background: #fffdfa; border: 1px solid #d9cdbc; border-radius: 18px; padding: 34px 38px 42px; }}
      p, li {{ line-height: 1.65; font-size: 1.02rem; text-align: justify; }}
      table {{ width: 100%; border-collapse: collapse; margin: 1rem 0 1.3rem; }}
      th, td {{ border: 1px solid #d9cdbc; padding: 0.7rem 0.78rem; text-align: left; vertical-align: top; }}
      th {{ background: #f2e8da; }}
      code {{ font-family: "Consolas", monospace; }}
    </style>
  </head>
  <body>
    <main><article>{body}</article></main>
  </body>
</html>
"""
    _write_text(output_path, html_payload)


def _analysis_markdown(
    *,
    suite: dict[str, Any],
    caption_summary: list[dict[str, Any]],
    oracle_summary: list[dict[str, Any]],
    caption_artifact: dict[str, Any],
    experiment_target_count: int,
    run_count: int,
    round_count: int,
    candidate_row_count: int,
) -> str:
    caption_target_count = int(caption_artifact["target_count"])
    lines = [
        f"# {suite['suite_name']}",
        "",
        suite["description"],
        "",
        "## Dataset and Caption Artifact",
        "",
        f"- Caption artifact images: `{caption_target_count}` curated Flickr8k test examples",
        f"- Experiment subset: `{experiment_target_count}` selected target images",
        f"- Total runs: `{run_count}`",
        f"- Total rounds: `{round_count}`",
        f"- Total scored candidate rows: `{candidate_row_count}`",
        f"- Caption model: `{caption_artifact['caption_model']['id']}`",
        f"- Mean human prompt length: `{caption_artifact['mean_human_word_count']}` words",
        f"- Mean selected AI prompt length: `{caption_artifact['mean_ai_word_count']}` words",
        "",
        "## Caption-Source Slice",
        "",
        "| Condition | Final CLIP | Final SigLIP | Final DINOv2 | Final LPIPS |",
        "| --- | ---: | ---: | ---: | ---: |",
    ]
    for row in caption_summary:
        lines.append(
            f"| {row['condition_label']} | {row['mean_final_clip']:.3f} "
            f"([{row['ci_low_final_clip']:.3f}, {row['ci_high_final_clip']:.3f}]) | "
            f"{row['mean_final_siglip']:.3f} "
            f"([{row['ci_low_final_siglip']:.3f}, {row['ci_high_final_siglip']:.3f}]) | "
            f"{row['mean_final_dinov2']:.3f} "
            f"([{row['ci_low_final_dinov2']:.3f}, {row['ci_high_final_dinov2']:.3f}]) | "
            f"{row['mean_final_lpips']:.3f} "
            f"([{row['ci_low_final_lpips']:.3f}, {row['ci_high_final_lpips']:.3f}]) |"
        )
    lines.extend(
        [
            "",
            "## Oracle-Metric Slice",
            "",
            "| Condition | Final CLIP | Final SigLIP | Final DINOv2 | Final LPIPS |",
            "| --- | ---: | ---: | ---: | ---: |",
        ]
    )
    for row in oracle_summary:
        lines.append(
            f"| {row['condition_label']} | {row['mean_final_clip']:.3f} "
            f"([{row['ci_low_final_clip']:.3f}, {row['ci_high_final_clip']:.3f}]) | "
            f"{row['mean_final_siglip']:.3f} "
            f"([{row['ci_low_final_siglip']:.3f}, {row['ci_high_final_siglip']:.3f}]) | "
            f"{row['mean_final_dinov2']:.3f} "
            f"([{row['ci_low_final_dinov2']:.3f}, {row['ci_high_final_dinov2']:.3f}]) | "
            f"{row['mean_final_lpips']:.3f} "
            f"([{row['ci_low_final_lpips']:.3f}, {row['ci_high_final_lpips']:.3f}]) |"
        )
    lines.extend(
        [
            "",
            "## Notes",
            "",
            "- Higher is better for CLIP, SigLIP, and DINOv2.",
            "- Lower is better for LPIPS.",
            "- Confidence intervals are nonparametric bootstrap intervals over run-level means.",
        ]
    )
    return "\n".join(lines) + "\n"


def _bundle_readme_markdown(
    *,
    suite: dict[str, Any],
    caption_summary: list[dict[str, Any]],
    oracle_summary: list[dict[str, Any]],
    caption_artifact: dict[str, Any],
    experiment_target_count: int,
    run_count: int,
    round_count: int,
    candidate_row_count: int,
) -> str:
    best_caption = caption_summary[0]
    best_oracle = oracle_summary[0]
    lines = [
        f"# {suite['suite_name']}",
        "",
        suite["description"],
        "",
        "## Scope",
        "",
        f"- Caption artifact images: `{int(caption_artifact['target_count'])}` curated Flickr8k examples",
        f"- Experiment subset: `{experiment_target_count}` selected targets",
        f"- Total runs: `{run_count}`",
        f"- Total rounds: `{round_count}`",
        f"- Total scored candidate rows: `{candidate_row_count}`",
        f"- Caption model: `{caption_artifact['caption_model']['id']}`",
        "",
        "## Headline Results",
        "",
        f"- Strongest caption-source condition: `{best_caption['condition_label']}`",
        f"  - final CLIP: `{best_caption['mean_final_clip']:.3f}`",
        f"  - final SigLIP: `{best_caption['mean_final_siglip']:.3f}`",
        f"  - final DINOv2: `{best_caption['mean_final_dinov2']:.3f}`",
        f"  - final LPIPS: `{best_caption['mean_final_lpips']:.3f}`",
        f"- Strongest oracle-policy condition by CLIP: `{best_oracle['condition_label']}`",
        f"  - final CLIP: `{best_oracle['mean_final_clip']:.3f}`",
        f"  - final SigLIP: `{best_oracle['mean_final_siglip']:.3f}`",
        f"  - final DINOv2: `{best_oracle['mean_final_dinov2']:.3f}`",
        f"  - final LPIPS: `{best_oracle['mean_final_lpips']:.3f}`",
        "",
        "## Artifacts",
        "",
        "- `runs.csv`: run-level summary rows",
        "- `round_rows.csv`: candidate-level rows for every round",
        "- `tables/caption_source_summary.csv`: caption-source aggregate summary with bootstrap confidence intervals",
        "- `tables/oracle_policy_summary.csv`: oracle-policy aggregate summary with bootstrap confidence intervals",
        "- `analysis/analysis_summary.md`: paper-facing summary",
        "",
    ]
    return "\n".join(lines) + "\n"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run the caption-extended oracle recovery study.")
    parser.add_argument(
        "--suite",
        default=str(_repo_root() / "paper" / "protocols" / "oracle_caption_metric_extension_suite.yaml"),
        help="Protocol YAML for the caption-and-metric oracle study.",
    )
    parser.add_argument("--backend", default="diffusers", help="Generation backend to use.")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    suite = _read_yaml(Path(args.suite))
    output_dir = _results_root()
    output_dir.mkdir(parents=True, exist_ok=True)

    targets = _resolve_targets(suite)
    caption_artifact = _read_json(Path(str(suite["caption_artifact"])))
    caption_lookup = {row["target_id"]: row for row in caption_artifact["rows"]}
    metric_specs = _metric_specs_from_suite(suite)
    metric_objects = _metric_objects(metric_specs)
    target_representations = _metric_target_representations(targets, metric_specs, metric_objects)

    run_rows: list[dict[str, Any]] = []
    detail_rows: list[dict[str, Any]] = []

    caption_sources = suite["caption_source_slice"]["caption_sources"]
    for target in targets:
        caption_record = caption_lookup[target.target_id]
        captions_by_source = {
            "human_caption": target.human_caption,
            "blip_standard_caption": str(caption_record["standard_caption"]),
            "blip_detailed_caption": str(caption_record["selected_detailed_caption"]),
        }
        for source_id in caption_sources:
            result = _run_one_condition(
                suite=suite,
                output_dir=output_dir,
                slice_name="caption_source_slice",
                condition_id=source_id,
                condition_label=str(suite["caption_source_labels"][source_id]),
                caption_text=captions_by_source[source_id],
                oracle_policy=str(suite["caption_source_slice"]["oracle_policy"]),
                target=target,
                repeat_index=0,
                metric_specs=metric_specs,
                metric_objects=metric_objects,
                target_representations=target_representations,
                backend=args.backend,
            )
            run_rows.append({key: value for key, value in result.items() if key != "round_rows"})
            detail_rows.extend(result["round_rows"])

    oracle_policies = suite["oracle_metric_slice"]["oracle_policies"]
    oracle_caption_source = str(suite["oracle_metric_slice"]["caption_source"])
    for target in targets:
        caption_record = caption_lookup[target.target_id]
        captions_by_source = {
            "human_caption": target.human_caption,
            "blip_standard_caption": str(caption_record["standard_caption"]),
            "blip_detailed_caption": str(caption_record["selected_detailed_caption"]),
        }
        for policy_id in oracle_policies:
            result = _run_one_condition(
                suite=suite,
                output_dir=output_dir,
                slice_name="oracle_metric_slice",
                condition_id=policy_id,
                condition_label=str(suite["oracle_policy_labels"][policy_id]),
                caption_text=captions_by_source[oracle_caption_source],
                oracle_policy=policy_id,
                target=target,
                repeat_index=0,
                metric_specs=metric_specs,
                metric_objects=metric_objects,
                target_representations=target_representations,
                backend=args.backend,
            )
            run_rows.append({key: value for key, value in result.items() if key != "round_rows"})
            detail_rows.extend(result["round_rows"])

    caption_summary = _summarize_slice([row for row in run_rows if row["slice_name"] == "caption_source_slice"], metric_specs)
    oracle_summary = _summarize_slice([row for row in run_rows if row["slice_name"] == "oracle_metric_slice"], metric_specs)

    tables_dir = output_dir / "tables"
    analysis_dir = output_dir / "analysis"
    _write_csv(output_dir / "runs.csv", run_rows, list(run_rows[0].keys()))
    _write_csv(output_dir / "round_rows.csv", detail_rows, list(detail_rows[0].keys()))
    _write_csv(tables_dir / "caption_source_summary.csv", caption_summary, list(caption_summary[0].keys()))
    _write_csv(tables_dir / "oracle_policy_summary.csv", oracle_summary, list(oracle_summary[0].keys()))
    _write_json(output_dir / "manifest.json", {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "suite_name": suite["suite_name"],
        "target_count": len(targets),
        "run_count": len(run_rows),
        "round_row_count": len(detail_rows),
        "caption_artifact": str(suite["caption_artifact"]),
        "caption_model_id": caption_artifact["caption_model"]["id"],
    })
    analysis_markdown = _analysis_markdown(
        suite=suite,
        caption_summary=caption_summary,
        oracle_summary=oracle_summary,
        caption_artifact=caption_artifact,
        experiment_target_count=len(targets),
        run_count=len(run_rows),
        round_count=len(detail_rows) // int(suite["fixed_conditions"]["candidate_count"]),
        candidate_row_count=len(detail_rows),
    )
    _write_text(analysis_dir / "analysis_summary.md", analysis_markdown)
    _markdown_to_html(suite["suite_name"], analysis_markdown, analysis_dir / "analysis_summary.html")
    _write_text(
        output_dir / "README.md",
        _bundle_readme_markdown(
            suite=suite,
            caption_summary=caption_summary,
            oracle_summary=oracle_summary,
            caption_artifact=caption_artifact,
            experiment_target_count=len(targets),
            run_count=len(run_rows),
            round_count=len(detail_rows) // int(suite["fixed_conditions"]["candidate_count"]),
            candidate_row_count=len(detail_rows),
        ),
    )
    print(f"Wrote oracle caption extension results to {output_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
