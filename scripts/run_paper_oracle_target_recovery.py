from __future__ import annotations

import argparse
import csv
import json
import shutil
import urllib.parse
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import markdown
import torch
import yaml
from PIL import Image, ImageDraw, ImageFont, ImageOps
from transformers import CLIPModel, CLIPProcessor

from app.core.schema import ExperimentCreate, FeedbackRequest, FeedbackType, SessionCreate, StrategyConfig
from app.engine.generation import build_generation_engine
from app.engine.orchestrator import Orchestrator
from app.storage.repository import JsonRepository


@dataclass(frozen=True)
class OracleTarget:
    id: str
    label: str
    image_url: str
    caption: str
    negative_prompt: str
    attribution: str


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _paper_root() -> Path:
    return _repo_root() / "paper"


def _results_root() -> Path:
    return _paper_root() / "results" / "oracle_target_recovery"


def _write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    _write_text(path, json.dumps(payload, indent=2, sort_keys=False))


def _write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fieldnames})


def _read_yaml(path: Path) -> dict[str, Any]:
    payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"Expected YAML mapping in {path}")
    return payload


def _download(url: str, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists():
        return
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/135.0.0.0 Safari/537.36"
            )
        },
    )
    with urllib.request.urlopen(request) as response, destination.open("wb") as handle:
        shutil.copyfileobj(response, handle)


class ClipOracle:
    def __init__(self, model_id: str, device: str | None = None) -> None:
        if device is None:
            device = "cuda" if torch.cuda.is_available() else "cpu"
        self.model_id = model_id
        self.device = device
        self.model = CLIPModel.from_pretrained(model_id).to(device)
        self.model.eval()
        self.processor = CLIPProcessor.from_pretrained(model_id)

    def embed_image(self, image_path: Path) -> torch.Tensor:
        image = Image.open(image_path).convert("RGB")
        inputs = self.processor(images=image, return_tensors="pt")
        inputs = {key: value.to(self.device) for key, value in inputs.items()}
        with torch.no_grad():
            features = self.model.get_image_features(**inputs)
        if not isinstance(features, torch.Tensor):
            if hasattr(features, "image_embeds"):
                features = features.image_embeds
            elif hasattr(features, "pooler_output"):
                features = features.pooler_output
            elif hasattr(features, "last_hidden_state"):
                features = features.last_hidden_state[:, 0, :]
            else:
                raise TypeError(f"Unsupported CLIP image feature output type: {type(features)!r}")
        features = features / features.norm(dim=-1, keepdim=True)
        return features[0].detach().cpu()

    @staticmethod
    def cosine(left: torch.Tensor, right: torch.Tensor) -> float:
        return float(torch.dot(left, right).item())


def _load_targets(suite: dict[str, Any]) -> list[OracleTarget]:
    targets: list[OracleTarget] = []
    for record in suite.get("targets", []):
        targets.append(
            OracleTarget(
                id=str(record["id"]),
                label=str(record["label"]),
                image_url=str(record["image_url"]),
                caption=str(record["caption"]),
                negative_prompt=str(record.get("negative_prompt", "")),
                attribution=str(record.get("attribution", "")),
            )
        )
    if not targets:
        raise ValueError("Target suite must contain at least one target.")
    return targets


def _strategy_config_from_suite(suite: dict[str, Any]) -> StrategyConfig:
    payload = dict(suite.get("fixed_conditions", {}))
    image_size = payload.get("image_size", "512x512")
    if isinstance(image_size, list) and len(image_size) == 2:
        payload["image_size"] = f"{image_size[0]}x{image_size[1]}"
    return StrategyConfig.model_validate(payload)


def _copy_trace_report(runtime_trace_report: Path, run_root: Path) -> Path:
    destination = run_root / "trace_report.html"
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(runtime_trace_report, destination)
    return destination


def _font(size: int):
    try:
        return ImageFont.truetype("arial.ttf", size)
    except OSError:
        return ImageFont.load_default()


def _artifact_path(runtime_root: Path, public_path: str | None) -> Path:
    if not public_path:
        raise ValueError("Candidate image path missing.")
    return runtime_root / "artifacts" / Path(public_path).name


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
      main {{ max-width: 980px; margin: 0 auto; padding: 28px 18px 48px; }}
      article {{ background: #fffdfa; border: 1px solid #d9cdbc; border-radius: 18px; padding: 34px 38px 42px; }}
      h1, h2, h3 {{ line-height: 1.2; }}
      p, li {{ line-height: 1.68; font-size: 1.03rem; text-align: justify; text-justify: inter-word; }}
      figure {{ margin: 1.4rem auto; text-align: center; }}
      figure img {{ max-width: 100%; border: 1px solid #d9cdbc; border-radius: 12px; background: white; }}
      figcaption {{ margin-top: 0.7rem; color: #40352b; }}
      table {{ width: 100%; border-collapse: collapse; margin: 1rem 0 1.3rem; }}
      th, td {{ border: 1px solid #d9cdbc; padding: 0.7rem 0.78rem; text-align: left; vertical-align: top; }}
      th {{ background: #f2e8da; }}
    </style>
  </head>
  <body>
    <main><article>{body}</article></main>
  </body>
</html>
"""
    _write_text(output_path, html_payload)


def _build_contact_sheet(
    *,
    rows: list[dict[str, Any]],
    target_paths: dict[str, Path],
    output_path: Path,
) -> None:
    card_width = 260
    card_height = 300
    padding = 20
    columns = 4
    title_height = 44
    row_height = card_height + padding
    width = padding + (columns * (card_width + padding))
    height = padding + (len(rows) * row_height) + 10
    canvas = Image.new("RGB", (width, height), "#fbfaf6")
    draw = ImageDraw.Draw(canvas)
    title_font = _font(18)
    body_font = _font(14)

    for row_index, row in enumerate(rows):
        y = padding + (row_index * row_height)
        target_image = Image.open(target_paths[row["target_id"]]).convert("RGB")
        baseline_image = Image.open(Path(row["baseline_image_path"])).convert("RGB")
        first_best_image = Image.open(Path(row["first_round_best_image_path"])).convert("RGB")
        final_image = Image.open(Path(row["final_best_image_path"])).convert("RGB")
        images = [target_image, baseline_image, first_best_image, final_image]
        labels = [
            f"{row['target_label']}\nTarget",
            f"Baseline\n{row['baseline_score']:.3f}",
            f"Round 1 best\n{row['first_round_best_score']:.3f}",
            f"Round {row['max_rounds']} best\n{row['final_best_score']:.3f}",
        ]
        for column, (image, label) in enumerate(zip(images, labels, strict=True)):
            x = padding + (column * (card_width + padding))
            thumb = ImageOps.fit(image, (card_width, card_height - title_height), method=Image.Resampling.LANCZOS)
            canvas.paste(thumb, (x, y + title_height))
            draw.rectangle([x, y, x + card_width, y + card_height], outline="#d2c5b3", width=2)
            draw.multiline_text((x + 10, y + 8), label, fill="#1f1b17", font=body_font, spacing=3)
        draw.text((padding, y - 2), row["target_label"], fill="#1f1b17", font=title_font)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(output_path)


def _build_convergence_svg(curve_rows: list[dict[str, Any]], output_path: Path) -> None:
    width = 1100
    height = 620
    left = 90
    right = 60
    top = 70
    bottom = 80
    plot_width = width - left - right
    plot_height = height - top - bottom
    rounds = sorted({int(row["round_index"]) for row in curve_rows})
    scores = [float(row["mean_best_score"]) for row in curve_rows]
    baseline = [float(row["mean_baseline_score"]) for row in curve_rows]
    if not rounds:
        raise ValueError("No curve rows available for convergence figure.")
    min_score = min(min(scores), min(baseline))
    max_score = max(max(scores), max(baseline))
    margin = max(0.02, (max_score - min_score) * 0.1)
    y_min = min_score - margin
    y_max = max_score + margin

    def x_position(round_index: int) -> float:
        if len(rounds) == 1:
            return left + plot_width / 2
        return left + ((round_index - min(rounds)) / (max(rounds) - min(rounds))) * plot_width

    def y_position(score: float) -> float:
        if y_max == y_min:
            return top + plot_height / 2
        return top + (1 - ((score - y_min) / (y_max - y_min))) * plot_height

    mean_points = " ".join(f"{x_position(r):.1f},{y_position(s):.1f}" for r, s in zip(rounds, scores, strict=True))
    base_points = " ".join(f"{x_position(r):.1f},{y_position(s):.1f}" for r, s in zip(rounds, baseline, strict=True))
    y_ticks = [y_min + ((y_max - y_min) * step / 4) for step in range(5)]

    output = f"""<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}" role="img" aria-labelledby="title desc">
  <title id="title">Oracle target-recovery convergence</title>
  <desc id="desc">Average best candidate similarity to the hidden target image across steering rounds, with the round-one baseline score shown as a reference line.</desc>
  <style>
    .bg {{ fill: #fbfaf6; }}
    .axis {{ stroke: #475467; stroke-width: 2.2; }}
    .grid {{ stroke: #d8cfbf; stroke-width: 1.2; }}
    .mean {{ fill: none; stroke: #8b4513; stroke-width: 4; }}
    .base {{ fill: none; stroke: #5b7da6; stroke-width: 3; stroke-dasharray: 10 8; }}
    .tick {{ font: 15px Georgia, 'Times New Roman', serif; fill: #344054; }}
    .title {{ font: 700 28px Georgia, 'Times New Roman', serif; fill: #1f2937; }}
    .label {{ font: 700 18px Georgia, 'Times New Roman', serif; fill: #1f2937; }}
    .legend {{ font: 15px Georgia, 'Times New Roman', serif; fill: #1f2937; }}
    .dot {{ fill: #8b4513; }}
  </style>
  <rect class="bg" width="{width}" height="{height}"/>
  <text class="title" x="70" y="46">Oracle Target-Recovery Convergence</text>
  <line class="axis" x1="{left}" y1="{top}" x2="{left}" y2="{top + plot_height}"/>
  <line class="axis" x1="{left}" y1="{top + plot_height}" x2="{left + plot_width}" y2="{top + plot_height}"/>
"""
    for tick in y_ticks:
        y = y_position(tick)
        output += f'  <line class="grid" x1="{left}" y1="{y:.1f}" x2="{left + plot_width}" y2="{y:.1f}"/>\n'
        output += f'  <text class="tick" x="{left - 12}" y="{y + 5:.1f}" text-anchor="end">{tick:.3f}</text>\n'
    for round_index in rounds:
        x = x_position(round_index)
        output += f'  <line class="grid" x1="{x:.1f}" y1="{top}" x2="{x:.1f}" y2="{top + plot_height}"/>\n'
        output += f'  <text class="tick" x="{x:.1f}" y="{top + plot_height + 26}" text-anchor="middle">{round_index}</text>\n'
    output += f'  <polyline class="base" points="{base_points}"/>\n'
    output += f'  <polyline class="mean" points="{mean_points}"/>\n'
    for round_index, score in zip(rounds, scores, strict=True):
        output += f'  <circle class="dot" cx="{x_position(round_index):.1f}" cy="{y_position(score):.1f}" r="5"/>\n'
    output += f"""
  <text class="label" x="{left + plot_width / 2:.1f}" y="{height - 20}" text-anchor="middle">Round index</text>
  <text class="label" transform="translate(24,{top + plot_height / 2:.1f}) rotate(-90)" text-anchor="middle">CLIP cosine to target</text>
  <line class="mean" x1="{width - 260}" y1="100" x2="{width - 200}" y2="100"/>
  <text class="legend" x="{width - 188}" y="105">Mean best candidate score</text>
  <line class="base" x1="{width - 260}" y1="132" x2="{width - 200}" y2="132"/>
  <text class="legend" x="{width - 188}" y="137">Mean round-one baseline score</text>
</svg>
"""
    _write_text(output_path, output)


def _run_target(
    *,
    output_dir: Path,
    suite: dict[str, Any],
    target: OracleTarget,
    oracle: ClipOracle,
    backend: str,
) -> dict[str, Any]:
    config = _strategy_config_from_suite(suite)
    run_root = output_dir / "runs" / target.id
    runtime_root = run_root / "runtime"
    repository = JsonRepository(data_dir=runtime_root)
    generator = build_generation_engine(
        backend=backend,
        artifacts_dir=repository.artifacts_dir,
        num_inference_steps=config.num_inference_steps,
    )
    orchestrator = Orchestrator(repository=repository, generator=generator)
    target_dir = output_dir / "targets"
    suffix = Path(urllib.parse.urlparse(target.image_url).path).suffix or ".jpg"
    target_path = target_dir / f"{target.id}{suffix}"
    _download(target.image_url, target_path)
    target_embedding = oracle.embed_image(target_path)

    experiment = orchestrator.create_experiment(
        ExperimentCreate(
            name=f"Oracle target recovery / {target.label}",
            description=f"Oracle-driven target recovery experiment for {target.id}",
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

    max_rounds = int(suite.get("max_rounds", 10))
    round_rows: list[dict[str, Any]] = []
    candidate_rows: list[dict[str, Any]] = []
    baseline_image_path: Path | None = None
    baseline_score: float | None = None
    first_round_best_score: float | None = None
    first_round_best_image_path: Path | None = None
    best_overall_score = -1.0
    best_overall_path: Path | None = None
    final_best_image_path: Path | None = None

    for round_index in range(1, max_rounds + 1):
        orchestrator.generate_round(session.id)
        round_obj = orchestrator.get_session_rounds(session.id)[-1]
        scored_candidates: list[dict[str, Any]] = []
        for candidate in round_obj.candidates:
            image_path = _artifact_path(runtime_root, candidate.image_path)
            image_embedding = oracle.embed_image(image_path)
            score = oracle.cosine(target_embedding, image_embedding)
            record = {
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
                "oracle_clip_score": round(score, 6),
                "selected": False,
                "carried_forward": bool(candidate.generation_params.get("carried_forward", False)),
                "baseline_prompt": bool(candidate.generation_params.get("baseline_prompt", False)),
            }
            candidate_rows.append(record)
            scored_candidates.append(record)

            if record["baseline_prompt"]:
                baseline_image_path = image_path
                baseline_score = score
            if score > best_overall_score:
                best_overall_score = score
                best_overall_path = image_path

        winner = max(scored_candidates, key=lambda row: row["oracle_clip_score"])
        winner["selected"] = True
        best_round_score = float(winner["oracle_clip_score"])
        final_best_image_path = Path(winner["image_path"])
        if round_index == 1:
            first_round_best_score = best_round_score
            first_round_best_image_path = Path(winner["image_path"])

        best_seen = max(float(row["oracle_clip_score"]) for row in candidate_rows if row["target_id"] == target.id)
        round_rows.append(
            {
                "target_id": target.id,
                "target_label": target.label,
                "session_id": session.id,
                "round_id": round_obj.id,
                "round_index": round_index,
                "winner_candidate_id": winner["candidate_id"],
                "winner_sampler_role": winner["sampler_role"],
                "best_candidate_score": round(best_round_score, 6),
                "best_seen_score": round(best_seen, 6),
                "baseline_score": round(baseline_score or 0.0, 6),
                "candidate_count": len(scored_candidates),
            }
        )

        if round_index < max_rounds:
            orchestrator.submit_feedback(
                round_obj.id,
                FeedbackRequest(
                    feedback_type=FeedbackType.winner_only,
                    payload={"winner_candidate_id": winner["candidate_id"]},
                    critique_text="Oracle winner selected by target-image embedding similarity.",
                ),
            )

    trace_report_path = orchestrator.generate_trace_report(session.id)
    copied_report = _copy_trace_report(trace_report_path, run_root)
    summary = {
        "target_id": target.id,
        "target_label": target.label,
        "target_path": str(target_path),
        "target_attribution": target.attribution,
        "session_id": session.id,
        "experiment_id": experiment.id,
        "trace_report": str(copied_report.relative_to(output_dir)),
        "runtime_root": str(runtime_root.relative_to(output_dir)),
        "max_rounds": max_rounds,
        "baseline_score": round(baseline_score or 0.0, 6),
        "first_round_best_score": round(first_round_best_score or 0.0, 6),
        "final_best_score": round(round_rows[-1]["best_candidate_score"], 6),
        "best_overall_score": round(best_overall_score, 6),
        "delta_baseline_to_final": round(round_rows[-1]["best_candidate_score"] - (baseline_score or 0.0), 6),
        "delta_first_round_best_to_final": round(round_rows[-1]["best_candidate_score"] - (first_round_best_score or 0.0), 6),
        "baseline_image_path": str(baseline_image_path) if baseline_image_path else "",
        "first_round_best_image_path": str(first_round_best_image_path) if first_round_best_image_path else "",
        "final_best_image_path": str(final_best_image_path) if final_best_image_path else "",
        "best_overall_image_path": str(best_overall_path) if best_overall_path else "",
    }
    _write_json(run_root / "summary.json", summary)
    return {
        "summary": summary,
        "round_rows": round_rows,
        "candidate_rows": candidate_rows,
        "target_path": target_path,
    }


def _build_analysis(output_dir: Path, target_rows: list[dict[str, Any]], round_rows: list[dict[str, Any]]) -> None:
    analysis_root = output_dir / "analysis"
    rounds_by_index: dict[int, list[dict[str, Any]]] = {}
    for row in round_rows:
        rounds_by_index.setdefault(int(row["round_index"]), []).append(row)

    curve_rows: list[dict[str, Any]] = []
    for round_index in sorted(rounds_by_index):
        rows = rounds_by_index[round_index]
        mean_best = sum(float(row["best_candidate_score"]) for row in rows) / len(rows)
        mean_best_seen = sum(float(row["best_seen_score"]) for row in rows) / len(rows)
        mean_baseline = sum(float(row["baseline_score"]) for row in rows) / len(rows)
        curve_rows.append(
            {
                "round_index": round_index,
                "mean_best_score": round(mean_best, 6),
                "mean_best_seen_score": round(mean_best_seen, 6),
                "mean_baseline_score": round(mean_baseline, 6),
            }
        )

    _write_csv(
        analysis_root / "round_curve.csv",
        curve_rows,
        ["round_index", "mean_best_score", "mean_best_seen_score", "mean_baseline_score"],
    )
    _build_convergence_svg(curve_rows, analysis_root / "oracle_convergence.svg")

    target_paths = {row["target_id"]: Path(row["target_path"]) for row in target_rows}
    _build_contact_sheet(
        rows=target_rows,
        target_paths=target_paths,
        output_path=analysis_root / "oracle_progression_contact_sheet.png",
    )

    final_mean = sum(float(row["final_best_score"]) for row in target_rows) / len(target_rows)
    baseline_mean = sum(float(row["baseline_score"]) for row in target_rows) / len(target_rows)
    delta_mean = sum(float(row["delta_baseline_to_final"]) for row in target_rows) / len(target_rows)
    markdown_summary = (
        "# Oracle Target-Recovery Analysis\n\n"
        "This bundle measures how closely StableSteering can recover a held-out real target image when initialized only from a manually written caption.\n\n"
        "## Scope\n\n"
        f"- targets: `{len(target_rows)}`\n"
        f"- rounds per target: `{max(int(row['max_rounds']) for row in target_rows)}`\n"
        f"- candidates per round: `4`\n"
        "## Aggregate summary\n\n"
        f"- mean round-one baseline similarity: `{baseline_mean:.3f}`\n"
        f"- mean round-ten best-candidate similarity: `{final_mean:.3f}`\n"
        f"- mean improvement from baseline to round ten: `{delta_mean:.3f}`\n\n"
        "## Target-level summary\n\n"
        "| target | baseline | round 1 best | round 10 best | delta baseline -> round 10 |\n"
        "| --- | ---: | ---: | ---: | ---: |\n"
        + "\n".join(
            f"| {row['target_label']} | {float(row['baseline_score']):.3f} | {float(row['first_round_best_score']):.3f} | {float(row['final_best_score']):.3f} | {float(row['delta_baseline_to_final']):.3f} |"
            for row in target_rows
        )
        + "\n\n"
        "## Interpretation boundary\n\n"
        "- The oracle selects candidates using CLIP image-embedding similarity to the hidden target.\n"
        "- This is a target-recovery proxy task, not a human-quality judgment.\n"
        "- Improvement should therefore be interpreted as recovery in oracle space rather than broad visual superiority.\n\n"
        "## Figures\n\n"
        "![Oracle convergence](oracle_convergence.svg)\n\n"
        "![Oracle progression contact sheet](oracle_progression_contact_sheet.png)\n"
    )
    _write_text(analysis_root / "analysis_summary.md", markdown_summary)
    _markdown_to_html("Oracle Target-Recovery Analysis", markdown_summary, analysis_root / "analysis_summary.html")

    figures_root = _paper_root() / "figures"
    shutil.copy2(analysis_root / "oracle_convergence.svg", figures_root / "figure_7_oracle_convergence.svg")
    shutil.copy2(
        analysis_root / "oracle_progression_contact_sheet.png",
        figures_root / "figure_8_oracle_target_recovery_examples.png",
    )


def _build_readme(target_rows: list[dict[str, Any]], round_rows: list[dict[str, Any]], candidate_rows: list[dict[str, Any]]) -> str:
    return (
        "# Oracle Target-Recovery Results\n\n"
        "This directory contains the oracle-based steering study in which a hidden real target image is paired with a manually written caption.\n\n"
        "Protocol summary:\n\n"
        "- the generator sees only the caption and negative prompt\n"
        "- the oracle sees the hidden target image\n"
        "- each round selects the candidate with highest CLIP image similarity to the target\n"
        "- steering runs for 10 rounds per target\n\n"
        f"Current bundle summary: {len(target_rows)} targets, {len(round_rows)} rounds, and {len(candidate_rows)} candidate rows.\n"
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Run oracle-based target-recovery steering study.")
    parser.add_argument(
        "--suite",
        type=Path,
        default=_paper_root() / "protocols" / "oracle_target_suite.yaml",
        help="Path to the oracle target suite YAML.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=_results_root(),
        help="Output directory for the oracle target-recovery bundle.",
    )
    parser.add_argument(
        "--backend",
        choices=["diffusers", "mock", "auto"],
        default="diffusers",
        help="Generation backend to use.",
    )
    args = parser.parse_args()

    suite = _read_yaml(args.suite)
    output_dir = args.output_dir
    output_dir.mkdir(parents=True, exist_ok=True)
    _write_text(output_dir / "protocol_snapshot.yaml", yaml.safe_dump(suite, sort_keys=False, allow_unicode=False))

    targets = _load_targets(suite)
    oracle = ClipOracle(str(suite.get("oracle_model", "openai/clip-vit-base-patch32")))

    target_rows: list[dict[str, Any]] = []
    round_rows: list[dict[str, Any]] = []
    candidate_rows: list[dict[str, Any]] = []
    for target in targets:
        result = _run_target(output_dir=output_dir, suite=suite, target=target, oracle=oracle, backend=args.backend)
        target_row = dict(result["summary"])
        target_row["target_path"] = str(result["target_path"])
        target_rows.append(target_row)
        round_rows.extend(result["round_rows"])
        candidate_rows.extend(result["candidate_rows"])

    tables_dir = output_dir / "tables"
    _write_csv(
        tables_dir / "targets.csv",
        target_rows,
        [
            "target_id",
            "target_label",
            "target_path",
            "target_attribution",
            "session_id",
            "experiment_id",
            "max_rounds",
            "baseline_score",
            "first_round_best_score",
            "final_best_score",
            "best_overall_score",
            "delta_baseline_to_final",
            "delta_first_round_best_to_final",
            "baseline_image_path",
            "first_round_best_image_path",
            "final_best_image_path",
            "best_overall_image_path",
            "trace_report",
            "runtime_root",
        ],
    )
    _write_csv(
        tables_dir / "rounds.csv",
        round_rows,
        [
            "target_id",
            "target_label",
            "session_id",
            "round_id",
            "round_index",
            "winner_candidate_id",
            "winner_sampler_role",
            "best_candidate_score",
            "best_seen_score",
            "baseline_score",
            "candidate_count",
        ],
    )
    _write_csv(
        tables_dir / "candidates.csv",
        candidate_rows,
        [
            "target_id",
            "target_label",
            "session_id",
            "round_id",
            "round_index",
            "candidate_id",
            "candidate_index",
            "sampler_role",
            "seed",
            "image_path",
            "oracle_clip_score",
            "selected",
            "carried_forward",
            "baseline_prompt",
        ],
    )

    manifest = {
        "suite_name": suite.get("suite_name", "oracle_target_recovery"),
        "description": suite.get("description", ""),
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "target_count": len(target_rows),
        "round_count": len(round_rows),
        "candidate_count": len(candidate_rows),
        "mean_baseline_score": round(sum(float(row["baseline_score"]) for row in target_rows) / len(target_rows), 6),
        "mean_final_best_score": round(sum(float(row["final_best_score"]) for row in target_rows) / len(target_rows), 6),
        "mean_delta_baseline_to_final": round(
            sum(float(row["delta_baseline_to_final"]) for row in target_rows) / len(target_rows),
            6,
        ),
        "oracle_model": str(suite.get("oracle_model", "openai/clip-vit-base-patch32")),
    }
    _write_json(output_dir / "manifest.json", manifest)
    _build_analysis(output_dir, target_rows, round_rows)
    _write_text(output_dir / "README.md", _build_readme(target_rows, round_rows, candidate_rows))
    print(f"Wrote oracle target-recovery bundle to {output_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
