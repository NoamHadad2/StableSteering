from __future__ import annotations

import argparse
import csv
import json
import math
import statistics
import shutil
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml
from PIL import Image, ImageFilter, ImageStat

from app.core.schema import ExperimentCreate, FeedbackRequest, FeedbackType, SessionCreate, StrategyConfig
from app.engine.generation import build_generation_engine
from app.engine.orchestrator import Orchestrator
from app.storage.repository import JsonRepository


@dataclass(frozen=True)
class BaselineExecution:
    """One policy in the minimal baseline matrix."""

    id: str
    label: str
    description: str
    mode: str


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _paper_root() -> Path:
    return _repo_root() / "paper"


def _default_baseline_overrides() -> dict[str, dict[str, Any]]:
    return {
        "prompt_only_manual": {
            "candidate_count": 1,
            "sampler": "random_local",
            "updater": "winner_copy",
            "seed_policy": "fixed-per-round",
        },
        "no_update_random_sampling": {
            "candidate_count": 5,
            "sampler": "random_local",
            "updater": "winner_copy",
            "seed_policy": "fixed-per-round",
        },
        "stablesteering_default": {
            "candidate_count": 5,
            "sampler": "exploit_orthogonal",
            "updater": "winner_average",
            "seed_policy": "fixed-per-candidate",
        },
    }


def _infer_baseline_mode(baseline_id: str) -> str:
    if baseline_id == "prompt_only_manual":
        return "prompt_only_proxy"
    if baseline_id == "no_update_random_sampling":
        return "no_update"
    return "steering_loop"


def _default_baseline_specs() -> list[BaselineExecution]:
    return [
        BaselineExecution(
            id="prompt_only_manual",
            label="Prompt-only manual iteration",
            description="One-round prompt render proxy with no steering-state update.",
            mode="prompt_only_proxy",
        ),
        BaselineExecution(
            id="no_update_random_sampling",
            label="No-update random sampling",
            description="Candidates are sampled without a feedback-driven state update.",
            mode="no_update",
        ),
        BaselineExecution(
            id="stablesteering_default",
            label="StableSteering default steering loop",
            description="Prompt-first loop with one feedback update and a follow-up round.",
            mode="steering_loop",
        ),
    ]


def _baseline_specs_from_suite(suite: dict[str, Any]) -> list[BaselineExecution]:
    configured = suite.get("baselines")
    if isinstance(configured, list) and configured:
        baselines: list[BaselineExecution] = []
        for record in configured:
            if not isinstance(record, dict):
                raise ValueError("Each baseline entry must be a mapping.")
            baseline_id = str(record.get("id", "")).strip()
            if not baseline_id:
                raise ValueError("Each baseline entry must define a non-empty id.")
            baselines.append(
                BaselineExecution(
                    id=baseline_id,
                    label=str(record.get("label", baseline_id)),
                    description=str(record.get("description", "")),
                    mode=str(record.get("mode", _infer_baseline_mode(baseline_id))),
                )
            )
        return baselines
    return _default_baseline_specs()


def _read_yaml(path: Path) -> dict[str, Any]:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"Prompt suite YAML must parse to a mapping: {path}")
    return data


def _stable_slug(text: str) -> str:
    return "".join(character.lower() if character.isalnum() else "_" for character in text).strip("_")


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


def _read_csv(path: Path) -> list[dict[str, Any]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def _strategy_config_from_suite(suite: dict[str, Any], baseline_id: str) -> StrategyConfig:
    common = dict(suite.get("fixed_conditions", {}))
    overrides = dict(_default_baseline_overrides().get(baseline_id, {}))
    overrides.update(dict(suite.get("baseline_overrides", {}).get(baseline_id, {})))
    merged = {**common, **overrides}

    image_size = merged.get("image_size", "512x512")
    if isinstance(image_size, list) and len(image_size) == 2:
        merged["image_size"] = f"{image_size[0]}x{image_size[1]}"
    merged.pop("backend", None)
    merged.pop("stopping_rule", None)

    return StrategyConfig.model_validate(merged)


def _visual_metrics(path: Path) -> dict[str, Any] | None:
    if not path.exists() or path.suffix.lower() != ".png":
        return None

    with Image.open(path) as image:
        rgb = image.convert("RGB")
        grayscale = rgb.convert("L")
        width, height = rgb.size
        stat = ImageStat.Stat(rgb)
        gray_stat = ImageStat.Stat(grayscale)
        edge_image = grayscale.filter(ImageFilter.FIND_EDGES)
        edge_stat = ImageStat.Stat(edge_image)
        entropy = float(grayscale.entropy())
        channel_stddev = sum(stat.stddev) / len(stat.stddev)
        brightness = gray_stat.mean[0]
        edge_mean = edge_stat.mean[0]

    checks = {
        "readable": True,
        "expected_min_size": width >= 384 and height >= 384,
        "non_blank_entropy": entropy >= 4.0,
        "has_contrast": channel_stddev >= 25.0,
        "has_edge_detail": edge_mean >= 12.0,
    }
    return {
        "path": str(path),
        "width": width,
        "height": height,
        "entropy": round(entropy, 3),
        "channel_stddev": round(channel_stddev, 3),
        "brightness_mean": round(brightness, 3),
        "edge_mean": round(edge_mean, 3),
        "checks": checks,
        "passed_checks": sum(1 for value in checks.values() if value),
        "failed_checks": [name for name, value in checks.items() if not value],
    }


def _selected_candidate_id(round_payload: dict[str, Any], baseline_mode: str) -> str | None:
    candidates = round_payload.get("candidate_metadata", [])
    if not candidates:
        return None
    if baseline_mode == "prompt_only_proxy":
        return candidates[0]["id"]
    if baseline_mode == "no_update":
        return None
    if len(candidates) > 2:
        return candidates[2]["id"]
    return candidates[-1]["id"]


def _feedback_payload_for_round(round_payload: dict[str, Any], baseline_mode: str) -> dict[str, Any] | None:
    candidates = round_payload.get("candidate_metadata", [])
    if baseline_mode != "steering_loop" or len(candidates) < 2:
        return None

    chosen_index = 2 if len(candidates) > 2 else 1
    chosen_candidate = candidates[chosen_index]
    ratings = {candidate["id"]: 1 for candidate in candidates}
    ratings[chosen_candidate["id"]] = 5
    if candidates[0]["id"] != chosen_candidate["id"]:
        ratings[candidates[0]["id"]] = 4
    return {"ratings": ratings}


def _copy_trace_report(runtime_trace_report: Path, run_root: Path) -> Path:
    destination = run_root / "trace_report.html"
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(runtime_trace_report, destination)
    return destination


def _run_case(
    *,
    output_dir: Path,
    prompt_record: dict[str, Any],
    baseline: BaselineExecution,
    suite: dict[str, Any],
    backend: str,
    repeat_index: int = 0,
) -> dict[str, Any]:
    cell_id = f"{_stable_slug(prompt_record['id'])}__{baseline.id}"
    trial_id = f"r{repeat_index + 1}"
    run_id = f"{cell_id}__{trial_id}"
    run_root = output_dir / "runs" / run_id
    runtime_root = run_root / "runtime"
    repository = JsonRepository(data_dir=runtime_root)
    config = _strategy_config_from_suite(suite, baseline.id)
    generator = build_generation_engine(
        backend=backend,
        artifacts_dir=repository.artifacts_dir,
        num_inference_steps=config.num_inference_steps,
    )
    orchestrator = Orchestrator(repository=repository, generator=generator)

    experiment = orchestrator.create_experiment(
        ExperimentCreate(
            name=f"Minimal baseline {baseline.label} / {prompt_record['label']}",
            description=f"Paper runner case for {baseline.label} on prompt {prompt_record['id']}",
            config=config,
        )
    )
    session = orchestrator.create_session(
        SessionCreate(
            experiment_id=experiment.id,
            prompt=prompt_record["prompt"],
            negative_prompt=prompt_record.get("negative_prompt", ""),
        )
    )

    round_payloads: list[dict[str, Any]] = []
    candidate_rows: list[dict[str, Any]] = []
    round_rows: list[dict[str, Any]] = []
    feedback_events = 0
    selected_candidate_id: str | None = None

    first_round = orchestrator.generate_round(session.id)
    session_rounds = orchestrator.get_session_rounds(session.id)
    round_payloads.append(first_round.model_dump(mode="json"))

    if baseline.mode == "steering_loop":
        round_one = session_rounds[0]
        feedback_payload = _feedback_payload_for_round(first_round.model_dump(mode="json"), baseline.mode)
        if feedback_payload is not None:
            feedback = orchestrator.submit_feedback(
                round_one.id,
                FeedbackRequest(feedback_type=FeedbackType.scalar_rating, payload=feedback_payload),
            )
            feedback_events += 1
            selected_candidate_id = feedback.update_summary.get("winner_candidate_id")
            round_two = orchestrator.generate_round(session.id)
            round_payloads.append(round_two.model_dump(mode="json"))

    session_rounds = orchestrator.get_session_rounds(session.id)
    selected_candidate_id = selected_candidate_id or _selected_candidate_id(first_round.model_dump(mode="json"), baseline.mode)

    for round_obj in session_rounds:
        round_rows.append(
            {
                "run_id": run_id,
                "cell_id": cell_id,
                "trial_id": trial_id,
                "repeat_index": repeat_index,
                "prompt_id": prompt_record["id"],
                "prompt_label": prompt_record["label"],
                "baseline_id": baseline.id,
                "baseline_label": baseline.label,
                "session_id": session.id,
                "round_id": round_obj.id,
                "round_index": round_obj.round_index,
                "candidate_count": len(round_obj.candidates),
                "feedback_count": len(round_obj.feedback_events),
                "render_status": round_obj.render_status.value,
                "latency_ms": round_obj.latency_ms,
                "selected_candidate_id": selected_candidate_id or "",
            }
        )
        for candidate in round_obj.candidates:
            artifact_path = runtime_root / "artifacts" / Path(candidate.image_path or "").name if candidate.image_path else None
            metrics = _visual_metrics(artifact_path) if artifact_path is not None else None
            candidate_rows.append(
                {
                    "run_id": run_id,
                    "cell_id": cell_id,
                    "trial_id": trial_id,
                    "repeat_index": repeat_index,
                    "prompt_id": prompt_record["id"],
                    "prompt_label": prompt_record["label"],
                    "baseline_id": baseline.id,
                    "baseline_label": baseline.label,
                    "session_id": session.id,
                    "round_id": round_obj.id,
                    "round_index": round_obj.round_index,
                    "candidate_id": candidate.id,
                    "candidate_index": candidate.candidate_index,
                    "sampler_role": candidate.sampler_role,
                    "seed": candidate.seed,
                    "render_status": candidate.render_status.value,
                    "image_path": candidate.image_path or "",
                    "carried_forward": candidate.generation_params.get("carried_forward", False),
                    "selected": candidate.id == selected_candidate_id,
                    "z": json.dumps(candidate.z),
                    "generation_params": json.dumps(candidate.generation_params, sort_keys=True),
                    "entropy": metrics["entropy"] if metrics else "",
                    "channel_stddev": metrics["channel_stddev"] if metrics else "",
                    "brightness_mean": metrics["brightness_mean"] if metrics else "",
                    "edge_mean": metrics["edge_mean"] if metrics else "",
                    "passed_checks": metrics["passed_checks"] if metrics else "",
                    "failed_checks": json.dumps(metrics["failed_checks"]) if metrics else "",
                }
            )

    trace_report_path = orchestrator.generate_trace_report(session.id)
    copied_report = _copy_trace_report(trace_report_path, run_root)

    run_summary = {
        "run_id": run_id,
        "cell_id": cell_id,
        "trial_id": trial_id,
        "repeat_index": repeat_index,
        "prompt_id": prompt_record["id"],
        "prompt_label": prompt_record["label"],
        "baseline_id": baseline.id,
        "baseline_label": baseline.label,
        "session_id": session.id,
        "experiment_id": experiment.id,
        "rounds_completed": len(session_rounds),
        "feedback_events": feedback_events,
        "selected_candidate_id": selected_candidate_id,
        "trace_report": str(copied_report.relative_to(output_dir)),
        "runtime_root": str(runtime_root.relative_to(output_dir)),
        "config": config.model_dump(mode="json"),
        "policy_mode": baseline.mode,
        "status": "completed",
    }

    _write_json(run_root / "summary.json", run_summary)

    return {
        "run_summary": run_summary,
        "round_rows": round_rows,
        "candidate_rows": candidate_rows,
    }


def _build_readme(output_dir: Path, suite: dict[str, Any], manifest: dict[str, Any]) -> str:
    prompt_count = manifest["prompt_count"]
    run_count = manifest["run_count"]
    aggregate = manifest.get("aggregate", {})
    failing_count = aggregate.get("failing_candidate_count", 0)
    return (
        "# Baseline Matrix Results\n\n"
        "This directory contains the paper-facing minimal baseline comparison matrix.\n\n"
        "What it measures:\n\n"
        "- prompt-only manual iteration as a one-round prompt-render proxy\n"
        "- no-update random sampling without feedback-driven steering\n"
        "- the StableSteering default loop with one feedback update and a follow-up round\n\n"
        "Shared settings are described in `protocol_snapshot.yaml`. Policy-specific overrides are recorded in the same snapshot and in `manifest.json`.\n\n"
        f"Current run count: {run_count} across {prompt_count} prompts.\n\n"
        f"Current aggregate summary: {aggregate.get('total_rounds', 0)} rounds, {aggregate.get('total_candidates', 0)} candidate images, "
        f"and {failing_count} candidates flagged by the lightweight visual checks.\n\n"
        "Key outputs:\n\n"
        "- `manifest.json`\n"
        "- `protocol_snapshot.yaml`\n"
        "- `tables/baseline_summary.csv`\n"
        "- `tables/repeat_summary.csv`\n"
        "- `tables/runs.csv`\n"
        "- `tables/rounds.csv`\n"
        "- `tables/candidates.csv`\n"
        "- `runs/<run_id>/summary.json`\n"
        "- `runs/<run_id>/trace_report.html`\n\n"
        "This runner is intentionally bounded: it uses a tiny prompt suite, isolated per-run runtime directories, and conservative comparison policies. It is a bridge from the paper package to a concrete empirical scaffold, not a full benchmark campaign.\n"
    )


def _materialize_prompt_suite(output_dir: Path, suite: dict[str, Any]) -> None:
    protocol_snapshot = yaml.safe_dump(suite, sort_keys=False, allow_unicode=False)
    _write_text(output_dir / "protocol_snapshot.yaml", protocol_snapshot)


def _aggregate_rows(run_summaries: list[dict[str, Any]], round_rows: list[dict[str, Any]], candidate_rows: list[dict[str, Any]]) -> dict[str, Any]:
    failing_candidates = [row for row in candidate_rows if str(row.get("failed_checks", "")).strip() not in {"", "[]"}]
    total_rounds = sum(int(row["rounds_completed"]) for row in run_summaries)
    total_candidates = len(candidate_rows)
    return {
        "total_runs": len(run_summaries),
        "total_rounds": total_rounds,
        "total_candidates": total_candidates,
        "failing_candidate_count": len(failing_candidates),
        "selected_candidate_count": sum(1 for row in candidate_rows if str(row.get("selected", "")).lower() == "true" or row.get("selected") is True),
    }


def _baseline_summary_rows(run_rows: list[dict[str, Any]], candidate_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[str, dict[str, Any]] = {}
    for run in run_rows:
        key = str(run["baseline_id"])
        bucket = grouped.setdefault(
            key,
            {
                "baseline_id": run["baseline_id"],
                "baseline_label": run["baseline_label"],
                "run_count": 0,
                "completed_runs": 0,
                "total_rounds": 0,
                "total_feedback_events": 0,
                "selected_candidate_count": 0,
                "failing_candidate_count": 0,
            },
        )
        bucket["run_count"] += 1
        if str(run.get("status", "")) == "completed":
            bucket["completed_runs"] += 1
        bucket["total_rounds"] += int(run.get("rounds_completed", 0) or 0)
        bucket["total_feedback_events"] += int(run.get("feedback_events", 0) or 0)

    for candidate in candidate_rows:
        key = str(candidate["baseline_id"])
        bucket = grouped.setdefault(
            key,
            {
                "baseline_id": candidate["baseline_id"],
                "baseline_label": candidate["baseline_label"],
                "run_count": 0,
                "completed_runs": 0,
                "total_rounds": 0,
                "total_feedback_events": 0,
                "selected_candidate_count": 0,
                "failing_candidate_count": 0,
            },
        )
        if str(candidate.get("selected", "")).lower() == "true":
            bucket["selected_candidate_count"] += 1
        if str(candidate.get("failed_checks", "")).strip() not in {"", "[]"}:
            bucket["failing_candidate_count"] += 1

    rows = list(grouped.values())
    rows.sort(key=lambda row: row["baseline_id"])
    for row in rows:
        run_count = max(1, int(row["run_count"]))
        row["avg_rounds_per_run"] = round(float(row["total_rounds"]) / run_count, 3)
        row["avg_feedback_events_per_run"] = round(float(row["total_feedback_events"]) / run_count, 3)
    return rows


def _repeat_summary_rows(run_rows: list[dict[str, Any]], candidate_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[str, dict[str, Any]] = {}
    for run in run_rows:
        key = f"{run['baseline_id']}|{run['prompt_id']}"
        bucket = grouped.setdefault(
            key,
            {
                "baseline_id": run["baseline_id"],
                "baseline_label": run["baseline_label"],
                "prompt_id": run["prompt_id"],
                "prompt_label": run["prompt_label"],
                "seed_count": 0,
                "round_values": [],
                "feedback_values": [],
                "failing_candidate_count": 0,
            },
        )
        bucket["seed_count"] += 1
        bucket["round_values"].append(float(run.get("rounds_completed", 0) or 0))
        bucket["feedback_values"].append(float(run.get("feedback_events", 0) or 0))

    for candidate in candidate_rows:
        key = f"{candidate['baseline_id']}|{candidate['prompt_id']}"
        if key not in grouped:
            continue
        if str(candidate.get("failed_checks", "")).strip() not in {"", "[]"}:
            grouped[key]["failing_candidate_count"] += 1

    rows: list[dict[str, Any]] = []
    for bucket in grouped.values():
        round_values = bucket.pop("round_values")
        feedback_values = bucket.pop("feedback_values")
        bucket["mean_rounds_per_run"] = round(statistics.mean(round_values), 3) if round_values else 0.0
        bucket["std_rounds_per_run"] = round(statistics.pstdev(round_values), 3) if len(round_values) > 1 else 0.0
        bucket["mean_feedback_events_per_run"] = round(statistics.mean(feedback_values), 3) if feedback_values else 0.0
        bucket["std_feedback_events_per_run"] = round(statistics.pstdev(feedback_values), 3) if len(feedback_values) > 1 else 0.0
        rows.append(bucket)
    rows.sort(key=lambda row: (row["prompt_id"], row["baseline_id"]))
    return rows


def _finalize_existing_bundle(output_dir: Path, suite: dict[str, Any]) -> dict[str, Any]:
    tables_dir = output_dir / "tables"
    run_rows = _read_csv(tables_dir / "runs.csv")
    round_rows = _read_csv(tables_dir / "rounds.csv")
    candidate_rows = _read_csv(tables_dir / "candidates.csv")
    baseline_summary_rows = _baseline_summary_rows(run_rows, candidate_rows)
    _write_csv(
        tables_dir / "baseline_summary.csv",
        baseline_summary_rows,
        [
            "baseline_id",
            "baseline_label",
            "run_count",
            "completed_runs",
            "total_rounds",
            "avg_rounds_per_run",
            "total_feedback_events",
            "avg_feedback_events_per_run",
            "selected_candidate_count",
            "failing_candidate_count",
        ],
    )
    _write_csv(
        tables_dir / "repeat_summary.csv",
        _repeat_summary_rows(run_rows, candidate_rows),
        [
            "baseline_id",
            "baseline_label",
            "prompt_id",
            "prompt_label",
            "seed_count",
            "mean_rounds_per_run",
            "std_rounds_per_run",
            "mean_feedback_events_per_run",
            "std_feedback_events_per_run",
            "failing_candidate_count",
        ],
    )

    run_summaries: list[dict[str, Any]] = []
    for run_row in run_rows:
        runtime_root = Path(run_row["runtime_root"])
        run_dir = output_dir / runtime_root.parent
        summary_path = run_dir / "summary.json"
        if summary_path.exists():
            run_summaries.append(json.loads(summary_path.read_text(encoding="utf-8")))
        else:
            run_summaries.append(dict(run_row))

    aggregate = {
        "total_runs": len(run_rows),
        "total_rounds": len(round_rows),
        "total_candidates": len(candidate_rows),
        "failing_candidate_count": sum(1 for row in candidate_rows if str(row.get("failed_checks", "")).strip() not in {"", "[]"}),
        "selected_candidate_count": sum(1 for row in candidate_rows if str(row.get("selected", "")).lower() == "true"),
    }

    baselines = _baseline_specs_from_suite(suite)

    manifest = {
        "status": "completed" if not any(row.get("status") == "failed" for row in run_summaries) else "completed_with_errors",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "prompt_suite": suite.get("name", "minimal_baseline_prompt_suite"),
        "prompt_count": len(_read_csv(tables_dir / "prompts.csv")),
        "baseline_count": len({row["baseline_id"] for row in run_rows}),
        "run_count": len(run_rows),
        "backend": suite.get("fixed_conditions", {}).get("backend", "auto"),
        "output_dir": str(output_dir),
        "tables": {
            "prompts": str((tables_dir / "prompts.csv").relative_to(output_dir)),
            "baseline_summary": str((tables_dir / "baseline_summary.csv").relative_to(output_dir)),
            "repeat_summary": str((tables_dir / "repeat_summary.csv").relative_to(output_dir)),
            "runs": str((tables_dir / "runs.csv").relative_to(output_dir)),
            "rounds": str((tables_dir / "rounds.csv").relative_to(output_dir)),
            "candidates": str((tables_dir / "candidates.csv").relative_to(output_dir)),
        },
        "aggregate": aggregate,
        "runs": run_summaries,
        "errors": [row for row in run_rows if row.get("status") == "failed"],
        "notes": [
            f"{baseline.id} uses mode={baseline.mode}" for baseline in baselines
        ],
    }
    _write_json(output_dir / "manifest.json", manifest)
    _materialize_prompt_suite(output_dir, suite)
    _write_text(output_dir / "README.md", _build_readme(output_dir, suite, manifest))
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the StableSteering minimal baseline comparison matrix.")
    parser.add_argument(
        "--prompt-suite",
        type=Path,
        default=_paper_root() / "protocols" / "minimal_baseline_prompt_suite.yaml",
        help="Path to the locked prompt suite YAML.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=_paper_root() / "results" / "baseline_matrix",
        help="Directory where the paper-facing baseline matrix bundle will be written.",
    )
    parser.add_argument(
        "--backend",
        choices=["auto", "diffusers", "mock"],
        default="auto",
        help="Generation backend to use.",
    )
    parser.add_argument(
        "--reuse-existing",
        action="store_true",
        help="Rebuild the root manifest and README from an existing completed run bundle without rerunning experiments.",
    )
    parser.add_argument(
        "--max-prompts",
        type=int,
        default=3,
        help="Maximum number of prompts to run from the locked prompt suite.",
    )
    parser.add_argument(
        "--seed-repeats",
        type=int,
        default=1,
        help="How many repeated runs to execute per prompt-policy cell. Use 1 to preserve the current pilot size.",
    )
    args = parser.parse_args()

    suite = _read_yaml(args.prompt_suite)
    prompts = suite.get("prompts", [])
    if not isinstance(prompts, list) or not prompts:
        raise ValueError("The prompt suite must define a non-empty prompts list.")

    output_dir = args.output_dir
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "runs").mkdir(parents=True, exist_ok=True)
    (output_dir / "tables").mkdir(parents=True, exist_ok=True)
    (output_dir / "figures").mkdir(parents=True, exist_ok=True)

    if args.reuse_existing:
        manifest = _finalize_existing_bundle(output_dir, suite)
        print(json.dumps(manifest, indent=2))
        return 0 if manifest["status"] == "completed" else 1

    prompt_subset = prompts[: max(1, min(args.max_prompts, len(prompts)))]
    baselines = _baseline_specs_from_suite(suite)

    run_summaries: list[dict[str, Any]] = []
    round_rows: list[dict[str, Any]] = []
    candidate_rows: list[dict[str, Any]] = []
    errors: list[dict[str, Any]] = []

    for prompt_record in prompt_subset:
        if not isinstance(prompt_record, dict):
            raise ValueError("Each prompt entry in the suite must be a mapping.")
        for baseline in baselines:
            for repeat_index in range(max(1, args.seed_repeats)):
                try:
                    result = _run_case(
                        output_dir=output_dir,
                        prompt_record=prompt_record,
                        baseline=baseline,
                        suite=suite,
                        backend=args.backend,
                        repeat_index=repeat_index,
                    )
                    run_summaries.append(result["run_summary"])
                    round_rows.extend(result["round_rows"])
                    candidate_rows.extend(result["candidate_rows"])
                except Exception as exc:
                    errors.append(
                        {
                            "prompt_id": prompt_record.get("id"),
                            "baseline_id": baseline.id,
                            "baseline_label": baseline.label,
                            "repeat_index": repeat_index,
                            "error": str(exc),
                        }
                    )
                    run_summaries.append(
                        {
                            "run_id": f"{_stable_slug(str(prompt_record.get('id', 'prompt')))}__{baseline.id}__r{repeat_index + 1}",
                            "cell_id": f"{_stable_slug(str(prompt_record.get('id', 'prompt')))}__{baseline.id}",
                            "trial_id": f"r{repeat_index + 1}",
                            "repeat_index": repeat_index,
                            "prompt_id": prompt_record.get("id"),
                            "prompt_label": prompt_record.get("label"),
                            "baseline_id": baseline.id,
                            "baseline_label": baseline.label,
                            "status": "failed",
                            "error": str(exc),
                        }
                    )

    prompt_rows = [
        {
            "prompt_id": prompt_record.get("id", ""),
            "prompt_label": prompt_record.get("label", ""),
            "prompt": prompt_record.get("prompt", ""),
            "negative_prompt": prompt_record.get("negative_prompt", ""),
        }
        for prompt_record in prompt_subset
    ]

    tables_dir = output_dir / "tables"
    _write_csv(
        tables_dir / "prompts.csv",
        prompt_rows,
        ["prompt_id", "prompt_label", "prompt", "negative_prompt"],
    )
    _write_csv(
        tables_dir / "runs.csv",
        run_summaries,
        [
            "run_id",
            "cell_id",
            "trial_id",
            "repeat_index",
            "prompt_id",
            "prompt_label",
            "baseline_id",
            "baseline_label",
            "session_id",
            "experiment_id",
            "rounds_completed",
            "feedback_events",
            "selected_candidate_id",
            "trace_report",
            "runtime_root",
            "policy_mode",
            "status",
            "error",
        ],
    )
    _write_csv(
        tables_dir / "rounds.csv",
        round_rows,
        [
            "run_id",
            "cell_id",
            "trial_id",
            "repeat_index",
            "prompt_id",
            "prompt_label",
            "baseline_id",
            "baseline_label",
            "session_id",
            "round_id",
            "round_index",
            "candidate_count",
            "feedback_count",
            "render_status",
            "latency_ms",
            "selected_candidate_id",
        ],
    )
    _write_csv(
        tables_dir / "candidates.csv",
        candidate_rows,
        [
            "run_id",
            "cell_id",
            "trial_id",
            "repeat_index",
            "prompt_id",
            "prompt_label",
            "baseline_id",
            "baseline_label",
            "session_id",
            "round_id",
            "round_index",
            "candidate_id",
            "candidate_index",
            "sampler_role",
            "seed",
            "render_status",
            "image_path",
            "carried_forward",
            "selected",
            "z",
            "generation_params",
            "entropy",
            "channel_stddev",
            "brightness_mean",
            "edge_mean",
            "passed_checks",
            "failed_checks",
        ],
    )
    _write_csv(
        tables_dir / "repeat_summary.csv",
        _repeat_summary_rows(run_summaries, candidate_rows),
        [
            "baseline_id",
            "baseline_label",
            "prompt_id",
            "prompt_label",
            "seed_count",
            "mean_rounds_per_run",
            "std_rounds_per_run",
            "mean_feedback_events_per_run",
            "std_feedback_events_per_run",
            "failing_candidate_count",
        ],
    )
    _write_csv(
        tables_dir / "baseline_summary.csv",
        _baseline_summary_rows(run_summaries, candidate_rows),
        [
            "baseline_id",
            "baseline_label",
            "run_count",
            "completed_runs",
            "total_rounds",
            "avg_rounds_per_run",
            "total_feedback_events",
            "avg_feedback_events_per_run",
            "selected_candidate_count",
            "failing_candidate_count",
        ],
    )

    manifest = {
        "status": "completed" if not errors else "completed_with_errors",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "prompt_suite": suite.get("name", "minimal_baseline_prompt_suite"),
        "prompt_count": len(prompt_subset),
        "baseline_count": len(baselines),
        "run_count": len(run_summaries),
        "backend": args.backend,
        "output_dir": str(output_dir),
        "tables": {
            "prompts": str((tables_dir / "prompts.csv").relative_to(output_dir)),
            "baseline_summary": str((tables_dir / "baseline_summary.csv").relative_to(output_dir)),
            "repeat_summary": str((tables_dir / "repeat_summary.csv").relative_to(output_dir)),
            "runs": str((tables_dir / "runs.csv").relative_to(output_dir)),
            "rounds": str((tables_dir / "rounds.csv").relative_to(output_dir)),
            "candidates": str((tables_dir / "candidates.csv").relative_to(output_dir)),
        },
        "aggregate": _aggregate_rows(run_summaries, round_rows, candidate_rows),
        "runs": run_summaries,
        "errors": errors,
        "notes": [f"{baseline.id} uses mode={baseline.mode}" for baseline in baselines],
    }
    _write_json(output_dir / "manifest.json", manifest)
    _materialize_prompt_suite(output_dir, suite)
    _write_text(output_dir / "README.md", _build_readme(output_dir, suite, manifest))

    print(json.dumps(manifest, indent=2))
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
