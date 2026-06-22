from __future__ import annotations

import argparse
import csv
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.core.schema import ExperimentCreate, FeedbackRequest, FeedbackType, SessionCreate, StrategyConfig
from app.engine.generation import build_generation_engine
from app.engine.orchestrator import Orchestrator
from app.storage.repository import JsonRepository
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
    description: str


def _results_root() -> Path:
    return _paper_root() / "results" / "sampler_feedback_comparison"


def _load_policy_suite(path: Path) -> tuple[dict[str, Any], list[Any], list[Policy]]:
    suite = _read_yaml(path)
    target_suite_path = Path(suite["target_suite_path"])
    if not target_suite_path.is_absolute():
        target_suite_path = Path(__file__).resolve().parents[1] / target_suite_path
    target_suite = _read_yaml(target_suite_path)
    targets = _load_targets(target_suite)

    policies: list[Policy] = []
    for slice_id, key in (("sampler_slice", "sampler_policies"), ("feedback_slice", "feedback_policies")):
        for record in suite.get(key, []):
            policies.append(
                Policy(
                    slice_id=slice_id,
                    id=str(record["id"]),
                    label=str(record["label"]),
                    sampler=str(record["sampler"]),
                    updater=str(record["updater"]),
                    feedback_mode=str(record["feedback_mode"]),
                    description=str(record.get("description", "")),
                )
            )
    return suite, targets, policies


def _strategy_config(suite: dict[str, Any], policy: Policy) -> StrategyConfig:
    payload = dict(suite.get("shared_conditions", {}))
    payload.update(
        {
            "sampler": policy.sampler,
            "updater": policy.updater,
            "feedback_mode": policy.feedback_mode,
        }
    )
    return StrategyConfig.model_validate(payload)


def _feedback_request(feedback_mode: str, ordered_scores: list[dict[str, Any]]) -> FeedbackRequest:
    winner_id = ordered_scores[0]["candidate_id"]
    feedback_type = FeedbackType(feedback_mode)
    if feedback_type == FeedbackType.winner_only:
        payload = {"winner_candidate_id": winner_id}
    elif feedback_type == FeedbackType.scalar_rating:
        ratings = {
            row["candidate_id"]: max(1, 5 - index)
            for index, row in enumerate(ordered_scores)
        }
        payload = {"ratings": ratings}
    elif feedback_type == FeedbackType.top_k:
        payload = {"ranking": [row["candidate_id"] for row in ordered_scores]}
    elif feedback_type == FeedbackType.pairwise:
        payload = {
            "winner_candidate_id": winner_id,
            "loser_candidate_id": ordered_scores[-1]["candidate_id"],
        }
    elif feedback_type == FeedbackType.approve_reject:
        approvals = {
            row["candidate_id"]: index < max(1, len(ordered_scores) // 2)
            for index, row in enumerate(ordered_scores)
        }
        approvals[winner_id] = True
        payload = {"winner_candidate_id": winner_id, "approvals": approvals}
    else:
        raise ValueError(f"Unsupported feedback mode: {feedback_mode}")
    return FeedbackRequest(feedback_type=feedback_type, payload=payload)


def _write_curve_svg(rows: list[dict[str, Any]], output_path: Path, title: str) -> None:
    width = 1100
    height = 620
    left = 90
    right = 70
    top = 80
    bottom = 80
    plot_width = width - left - right
    plot_height = height - top - bottom
    round_indices = sorted({int(row["round_index"]) for row in rows})
    values = [float(row["mean_best_score"]) for row in rows] + [float(row["mean_baseline_score"]) for row in rows]
    min_score = min(values)
    max_score = max(values)
    margin = max(0.02, (max_score - min_score) * 0.1)
    min_score -= margin
    max_score += margin

    def x_coord(round_index: int) -> float:
        if len(round_indices) == 1:
            return left + (plot_width / 2)
        return left + ((round_index - round_indices[0]) / (round_indices[-1] - round_indices[0])) * plot_width

    def y_coord(score: float) -> float:
        return top + ((max_score - score) / (max_score - min_score)) * plot_height

    palette = ["#b24c1a", "#1f6f8b", "#2d6a4f", "#7c3aed", "#b7791f", "#b83280"]
    policy_order = sorted({row["policy_label"] for row in rows})
    color_map = {policy: palette[index % len(palette)] for index, policy in enumerate(policy_order)}
    baseline_value = float(rows[0]["mean_baseline_score"])
    baseline_y = y_coord(baseline_value)

    svg_lines = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        '<rect width="100%" height="100%" fill="#fbfaf6"/>',
        f'<text x="{left}" y="42" font-size="28" font-family="Georgia, serif" fill="#1f1b17">{title}</text>',
        f'<text x="{left}" y="64" font-size="16" font-family="Georgia, serif" fill="#4b3f34">Mean oracle similarity by round</text>',
    ]
    for tick in range(6):
        value = min_score + ((max_score - min_score) * tick / 5)
        y = y_coord(value)
        svg_lines.append(f'<line x1="{left}" y1="{y:.2f}" x2="{left + plot_width}" y2="{y:.2f}" stroke="#e3d7c8" stroke-width="1"/>')
        svg_lines.append(
            f'<text x="{left - 12}" y="{y + 5:.2f}" text-anchor="end" font-size="14" font-family="Georgia, serif" fill="#4b3f34">{value:.3f}</text>'
        )
    for round_index in round_indices:
        x = x_coord(round_index)
        svg_lines.append(f'<line x1="{x:.2f}" y1="{top}" x2="{x:.2f}" y2="{top + plot_height}" stroke="#efe5d8" stroke-width="1"/>')
        svg_lines.append(
            f'<text x="{x:.2f}" y="{top + plot_height + 28}" text-anchor="middle" font-size="14" font-family="Georgia, serif" fill="#4b3f34">{round_index}</text>'
        )
    svg_lines.append(f'<line x1="{left}" y1="{baseline_y:.2f}" x2="{left + plot_width}" y2="{baseline_y:.2f}" stroke="#6b5e53" stroke-dasharray="8 6" stroke-width="2"/>')
    svg_lines.append(
        f'<text x="{left + plot_width - 8}" y="{baseline_y - 8:.2f}" text-anchor="end" font-size="14" font-family="Georgia, serif" fill="#6b5e53">Mean baseline</text>'
    )

    for policy in policy_order:
        policy_rows = sorted(
            [row for row in rows if row["policy_label"] == policy],
            key=lambda row: int(row["round_index"]),
        )
        points = " ".join(f"{x_coord(int(row['round_index'])):.2f},{y_coord(float(row['mean_best_score'])):.2f}" for row in policy_rows)
        color = color_map[policy]
        svg_lines.append(f'<polyline points="{points}" fill="none" stroke="{color}" stroke-width="4" stroke-linecap="round" stroke-linejoin="round"/>')
        for row in policy_rows:
            x = x_coord(int(row["round_index"]))
            y = y_coord(float(row["mean_best_score"]))
            svg_lines.append(f'<circle cx="{x:.2f}" cy="{y:.2f}" r="5" fill="{color}" stroke="#fbfaf6" stroke-width="2"/>')

    legend_x = left + plot_width - 240
    legend_y = top + 14
    svg_lines.append(f'<rect x="{legend_x}" y="{legend_y}" width="220" height="{30 + (len(policy_order) * 24)}" rx="14" fill="#fffdfa" stroke="#d8cbb9"/>')
    for index, policy in enumerate(policy_order):
        y = legend_y + 24 + (index * 22)
        color = color_map[policy]
        svg_lines.append(f'<line x1="{legend_x + 14}" y1="{y}" x2="{legend_x + 34}" y2="{y}" stroke="{color}" stroke-width="4" stroke-linecap="round"/>')
        svg_lines.append(f'<text x="{legend_x + 42}" y="{y + 5}" font-size="13" font-family="Georgia, serif" fill="#1f1b17">{policy}</text>')

    svg_lines.append("</svg>")
    _write_text(output_path, "\n".join(svg_lines))


def _run_policy(
    *,
    output_dir: Path,
    suite: dict[str, Any],
    policy: Policy,
    target: Any,
    oracle: ClipOracle,
    backend: str,
) -> dict[str, Any]:
    run_root = output_dir / "runs" / policy.slice_id / policy.id / target.id
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
    target_embedding = oracle.embed_image(target_path)

    experiment = orchestrator.create_experiment(
        ExperimentCreate(
            name=f"{policy.label} oracle comparison",
            description=f"{policy.slice_id} / {policy.id} / {target.id}",
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
    best_seen_score = -1.0
    baseline_score = None
    final_best_image_path = ""
    first_round_best_image_path = ""
    baseline_image_path = ""

    for round_index in range(1, int(suite["max_rounds"]) + 1):
        round_response = orchestrator.generate_round(session.id)
        round_obj = orchestrator.get_session_rounds(session.id)[-1]

        scored_candidates: list[dict[str, Any]] = []
        for candidate in round_response.candidate_metadata:
            image_path = _artifact_path(runtime_root, candidate.image_path)
            score = oracle.cosine(target_embedding, oracle.embed_image(image_path))
            scored_candidates.append(
                {
                    "candidate_id": candidate.id,
                    "candidate_index": candidate.candidate_index,
                    "sampler_role": candidate.sampler_role,
                    "score": score,
                    "image_path": str(image_path),
                }
            )
            candidate_rows.append(
                {
                    "slice_id": policy.slice_id,
                    "policy_id": policy.id,
                    "policy_label": policy.label,
                    "target_id": target.id,
                    "target_label": target.label,
                    "session_id": session.id,
                    "round_id": round_obj.id,
                    "round_index": round_index,
                    "candidate_id": candidate.id,
                    "candidate_index": candidate.candidate_index,
                    "sampler_role": candidate.sampler_role,
                    "score": round(score, 6),
                    "image_path": str(image_path),
                }
            )

        scored_candidates.sort(key=lambda row: (-row["score"], row["candidate_id"]))
        round_best = scored_candidates[0]
        best_seen_score = max(best_seen_score, round_best["score"])
        if baseline_score is None:
            baseline_candidate = next(row for row in scored_candidates if row["candidate_index"] == 0)
            baseline_score = baseline_candidate["score"]
            baseline_image_path = baseline_candidate["image_path"]
            first_round_best_image_path = round_best["image_path"]
        final_best_image_path = round_best["image_path"]

        round_rows.append(
            {
                "slice_id": policy.slice_id,
                "policy_id": policy.id,
                "policy_label": policy.label,
                "target_id": target.id,
                "target_label": target.label,
                "session_id": session.id,
                "round_id": round_obj.id,
                "round_index": round_index,
                "winner_candidate_id": round_best["candidate_id"],
                "best_candidate_score": round(round_best["score"], 6),
                "best_seen_score": round(best_seen_score, 6),
                "baseline_score": round(baseline_score, 6),
                "feedback_mode": policy.feedback_mode,
                "sampler": policy.sampler,
                "updater": policy.updater,
            }
        )

        if round_index < int(suite["max_rounds"]):
            request = _feedback_request(policy.feedback_mode, scored_candidates)
            orchestrator.submit_feedback(round_obj.id, request)

    trace_report = _copy_trace_report(orchestrator.generate_trace_report(session.id), run_root)
    run_summary = {
        "slice_id": policy.slice_id,
        "policy_id": policy.id,
        "policy_label": policy.label,
        "target_id": target.id,
        "target_label": target.label,
        "sampler": policy.sampler,
        "updater": policy.updater,
        "feedback_mode": policy.feedback_mode,
        "max_rounds": int(suite["max_rounds"]),
        "baseline_score": round(baseline_score or 0.0, 6),
        "final_best_score": round(best_seen_score, 6),
        "delta_baseline_to_final": round(best_seen_score - (baseline_score or 0.0), 6),
        "baseline_image_path": baseline_image_path,
        "first_round_best_image_path": first_round_best_image_path,
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
                "sampler": group[0]["sampler"],
                "updater": group[0]["updater"],
                "feedback_mode": group[0]["feedback_mode"],
                "target_count": len(group),
                "mean_baseline_score": round(sum(float(row["baseline_score"]) for row in group) / len(group), 6),
                "mean_final_best_score": round(sum(float(row["final_best_score"]) for row in group) / len(group), 6),
                "mean_delta_baseline_to_final": round(sum(float(row["delta_baseline_to_final"]) for row in group) / len(group), 6),
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
                "mean_best_score": round(sum(float(row["best_candidate_score"]) for row in group) / len(group), 6),
                "mean_baseline_score": round(sum(float(row["baseline_score"]) for row in group) / len(group), 6),
            }
        )
    rows.sort(key=lambda row: (row["policy_label"], row["round_index"]))
    return rows


def _build_readme(manifest: dict[str, Any]) -> str:
    return (
        "# Sampler and Feedback Comparison Results\n\n"
        "This bundle compares distinct sampling strategies and preference-model variants under a shared oracle target-recovery protocol.\n\n"
        f"- targets: `{manifest['target_count']}`\n"
        f"- policies: `{manifest['policy_count']}`\n"
        f"- runs: `{manifest['run_count']}`\n"
        f"- rounds: `{manifest['round_count']}`\n"
        f"- candidate rows: `{manifest['candidate_count']}`\n\n"
        "Comparison slices:\n\n"
        "- sampler slice: fixed updater and feedback mode, varying sampler family\n"
        "- feedback-model slice: fixed sampler, varying updater and feedback representation\n\n"
        "Key outputs:\n\n"
        "- `manifest.json`\n"
        "- `tables/policy_summary.csv`\n"
        "- `tables/runs.csv`\n"
        "- `tables/rounds.csv`\n"
        "- `analysis/analysis_summary.md`\n"
        "- `analysis/sampler_slice_curve.svg`\n"
        "- `analysis/feedback_slice_curve.svg`\n"
    )


def _build_analysis(
    *,
    output_dir: Path,
    policy_summaries: list[dict[str, Any]],
    round_rows: list[dict[str, Any]],
) -> None:
    analysis_dir = output_dir / "analysis"
    analysis_dir.mkdir(parents=True, exist_ok=True)
    sampler_rows = [row for row in policy_summaries if row["slice_id"] == "sampler_slice"]
    feedback_rows = [row for row in policy_summaries if row["slice_id"] == "feedback_slice"]
    sampler_curve = _curve_rows(round_rows, "sampler_slice")
    feedback_curve = _curve_rows(round_rows, "feedback_slice")

    _write_csv(analysis_dir / "sampler_curve.csv", sampler_curve, ["slice_id", "policy_label", "round_index", "mean_best_score", "mean_baseline_score"])
    _write_csv(analysis_dir / "feedback_curve.csv", feedback_curve, ["slice_id", "policy_label", "round_index", "mean_best_score", "mean_baseline_score"])
    _write_curve_svg(sampler_curve, analysis_dir / "sampler_slice_curve.svg", "Sampler Slice: Oracle Target-Recovery")
    _write_curve_svg(feedback_curve, analysis_dir / "feedback_slice_curve.svg", "Feedback-Model Slice: Oracle Target-Recovery")

    summary = (
        "# Sampler and Feedback Comparison Analysis\n\n"
        "## Sampler slice\n\n"
        "| policy | final best | delta baseline -> final |\n"
        "| --- | ---: | ---: |\n"
        + "\n".join(
            f"| {row['policy_label']} | {row['mean_final_best_score']:.3f} | {row['mean_delta_baseline_to_final']:.3f} |"
            for row in sampler_rows
        )
        + "\n\n"
        "## Feedback-model slice\n\n"
        "| policy | updater | feedback | final best | delta baseline -> final |\n"
        "| --- | --- | --- | ---: | ---: |\n"
        + "\n".join(
            f"| {row['policy_label']} | `{row['updater']}` | `{row['feedback_mode']}` | {row['mean_final_best_score']:.3f} | {row['mean_delta_baseline_to_final']:.3f} |"
            for row in feedback_rows
        )
        + "\n\n"
        "## Figures\n\n"
        "![Sampler slice curve](sampler_slice_curve.svg)\n\n"
        "![Feedback slice curve](feedback_slice_curve.svg)\n"
    )
    _write_text(analysis_dir / "analysis_summary.md", summary)
    _markdown_to_html("Sampler and Feedback Comparison Analysis", summary, analysis_dir / "analysis_summary.html")


def main() -> int:
    parser = argparse.ArgumentParser(description="Compare sampler families and feedback-model variants under oracle target recovery.")
    parser.add_argument(
        "--suite",
        type=Path,
        default=_paper_root() / "protocols" / "sampler_feedback_comparison_suite.yaml",
        help="Path to the locked comparison suite YAML.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=_results_root(),
        help="Directory where the comparison bundle will be written.",
    )
    parser.add_argument(
        "--backend",
        choices=["auto", "diffusers", "mock"],
        default="auto",
        help="Generation backend to use.",
    )
    parser.add_argument(
        "--max-targets",
        type=int,
        default=3,
        help="Maximum number of targets from the suite to evaluate.",
    )
    args = parser.parse_args()

    suite, targets, policies = _load_policy_suite(args.suite)
    targets = targets[: max(1, min(args.max_targets, len(targets)))]
    output_dir = args.output_dir
    output_dir.mkdir(parents=True, exist_ok=True)
    oracle = ClipOracle(str(suite["oracle_model"]))

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
                oracle=oracle,
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
            "slice_id",
            "policy_id",
            "policy_label",
            "target_id",
            "target_label",
            "sampler",
            "updater",
            "feedback_mode",
            "max_rounds",
            "baseline_score",
            "final_best_score",
            "delta_baseline_to_final",
            "baseline_image_path",
            "first_round_best_image_path",
            "final_best_image_path",
            "target_path",
            "trace_report",
        ],
    )
    _write_csv(
        tables_dir / "rounds.csv",
        round_rows,
        [
            "slice_id",
            "policy_id",
            "policy_label",
            "target_id",
            "target_label",
            "session_id",
            "round_id",
            "round_index",
            "winner_candidate_id",
            "best_candidate_score",
            "best_seen_score",
            "baseline_score",
            "feedback_mode",
            "sampler",
            "updater",
        ],
    )
    _write_csv(
        tables_dir / "candidates.csv",
        candidate_rows,
        [
            "slice_id",
            "policy_id",
            "policy_label",
            "target_id",
            "target_label",
            "session_id",
            "round_id",
            "round_index",
            "candidate_id",
            "candidate_index",
            "sampler_role",
            "score",
            "image_path",
        ],
    )
    policy_summaries = _policy_summary_rows(run_rows)
    _write_csv(
        tables_dir / "policy_summary.csv",
        policy_summaries,
        [
            "slice_id",
            "policy_id",
            "policy_label",
            "sampler",
            "updater",
            "feedback_mode",
            "target_count",
            "mean_baseline_score",
            "mean_final_best_score",
            "mean_delta_baseline_to_final",
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
    }
    _write_json(output_dir / "manifest.json", manifest)
    _write_text(output_dir / "README.md", _build_readme(manifest))
    _build_analysis(output_dir=output_dir, policy_summaries=policy_summaries, round_rows=round_rows)

    print(f"Wrote sampler/feedback comparison bundle to {output_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
