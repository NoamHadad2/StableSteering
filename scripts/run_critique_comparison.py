"""Does structured critique speed up steering convergence?

This study uses the new ``critique_rating`` feedback mode and the
``critique_weighted_preference`` updater (both added alongside this script) to
answer a concrete research question:

    Given a synthetic user with a fixed hidden target in steering space, does
    pairing each rating with structured reason tags (and an updater that
    consumes them) reach the target in fewer rounds than plain scalar ratings?

It compares two end-to-end strategies:

  * Baseline: ``scalar_rating`` + ``winner_average`` (tags absent)
  * Critique:  ``critique_rating`` + ``critique_weighted_preference`` (tags used)

Both arms see the *same* synthetic preferences, so any difference comes from the
critique signal actually changing the steering trajectory — not from noise.

It is GPU-free: it drives the orchestrator with the deterministic mock backend,
the same one the test suite uses. Outputs (under
``output/critique_comparison/`` by default):
  * ``results.csv``   - one row per simulated session
  * ``findings.md``   - per-strategy summary table plus a short interpretation
"""

from __future__ import annotations

import csv
import math
import random
import tempfile
from pathlib import Path

from app.core.schema import ExperimentCreate, FeedbackRequest, SessionCreate, StrategyConfig
from app.engine.generation import MockGenerationEngine
from app.engine.orchestrator import Orchestrator
from app.storage.repository import JsonRepository
from app.core.tracing import TraceRecorder
from app.updaters.critique_weighted_pref import NEGATIVE_TAGS, POSITIVE_TAGS


# The two arms under comparison: (label, feedback_mode, updater).
ARMS = [
    ("baseline_scalar", "scalar_rating", "winner_average"),
    ("critique_weighted", "critique_rating", "critique_weighted_preference"),
]
DEFAULT_SAMPLERS = ["random_local", "line_search", "spherical_cover"]
DEFAULT_SEEDS = [0, 1, 2]

# A close candidate earns positive tags, a far one earns negative tags.
_POSITIVE_TAGS = sorted(POSITIVE_TAGS)
_NEGATIVE_TAGS = sorted(NEGATIVE_TAGS)

RESULT_FIELDS = [
    "arm",
    "sampler",
    "seed",
    "rounds_run",
    "converged",
    "rounds_to_convergence",
    "final_distance_to_target",
]


def _distance(left: list[float], right: list[float]) -> float:
    width = max(len(left), len(right))
    total = 0.0
    for index in range(width):
        a = left[index] if index < len(left) else 0.0
        b = right[index] if index < len(right) else 0.0
        total += (a - b) ** 2
    return math.sqrt(total)


def _synthetic_target(seed: int, dimension: int) -> list[float]:
    """A fixed hidden preference point the synthetic user steers toward."""

    rng = random.Random(seed)
    return [rng.uniform(-0.3, 0.3) for _ in range(dimension)]


def _rate_candidates(candidates, target: list[float]) -> dict[str, float]:
    """Score each candidate by closeness to the hidden target (5 = perfect)."""

    return {candidate.id: round(5.0 / (1.0 + _distance(candidate.z, target)), 4) for candidate in candidates}


def _critique_tags(candidates, target: list[float]) -> dict[str, list[str]]:
    """Emit reason tags consistent with the hidden target.

    Candidates nearer the target than the round's median distance get positive
    tags; the rest get negative tags. This is the synthetic analogue of a user
    explaining *why* a candidate is good or bad.
    """

    distances = {candidate.id: _distance(candidate.z, target) for candidate in candidates}
    median = sorted(distances.values())[len(distances) // 2]
    tags: dict[str, list[str]] = {}
    for candidate in candidates:
        if distances[candidate.id] <= median:
            tags[candidate.id] = _POSITIVE_TAGS[:2]
        else:
            tags[candidate.id] = _NEGATIVE_TAGS[:1]
    return tags


def run_session(
    orchestrator: Orchestrator,
    *,
    arm: str,
    feedback_mode: str,
    updater: str,
    sampler: str,
    seed: int,
    max_rounds: int,
    candidate_count: int,
    steering_dimension: int,
    trust_radius: float,
    convergence_patience: int,
    convergence_min_delta: float,
) -> dict:
    """Drive one synthetic session for a given arm and return its outcome row."""

    config = StrategyConfig(
        sampler=sampler,
        updater=updater,
        feedback_mode=feedback_mode,
        candidate_count=candidate_count,
        steering_dimension=steering_dimension,
        trust_radius=trust_radius,
        convergence_patience=convergence_patience,
        convergence_min_delta=convergence_min_delta,
    )
    experiment = orchestrator.create_experiment(
        ExperimentCreate(name=f"{arm}/{sampler}#{seed}", description="critique study", config=config)
    )
    session = orchestrator.create_session(
        SessionCreate(experiment_id=experiment.id, prompt="A synthetic critique study prompt")
    )
    target = _synthetic_target(seed, steering_dimension)

    rounds_run = 0
    report = orchestrator.get_session_convergence(session.id)
    for _ in range(max_rounds):
        round_response = orchestrator.generate_round(session.id)
        rounds_run += 1
        ratings = _rate_candidates(round_response.candidate_metadata, target)
        if feedback_mode == "critique_rating":
            payload = {
                "ratings": ratings,
                "critique_tags": _critique_tags(round_response.candidate_metadata, target),
            }
        else:
            payload = {"ratings": ratings}
        orchestrator.submit_feedback(
            round_response.round_id,
            FeedbackRequest(feedback_type=feedback_mode, payload=payload),
        )
        report = orchestrator.get_session_convergence(session.id)
        if report.converged:
            break  # early stopping: the steering loop has settled

    final_session = orchestrator.get_session(session.id)
    return {
        "arm": arm,
        "sampler": sampler,
        "seed": seed,
        "rounds_run": rounds_run,
        "converged": report.converged,
        "rounds_to_convergence": report.rounds_to_convergence if report.converged else "",
        "final_distance_to_target": round(_distance(final_session.current_z, target), 4),
    }


def run_comparison(
    output_dir: Path,
    *,
    samplers: list[str] | None = None,
    seeds: list[int] | None = None,
    max_rounds: int = 12,
    candidate_count: int = 5,
    steering_dimension: int = 5,
    trust_radius: float = 0.55,
    convergence_patience: int = 2,
    convergence_min_delta: float = 0.04,
) -> tuple[list[dict], list[dict]]:
    """Run both arms across the sampler/seed grid, write CSV + findings."""

    samplers = samplers or DEFAULT_SAMPLERS
    seeds = seeds or DEFAULT_SEEDS
    output_dir.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory(prefix="critique_study_") as workdir:
        work = Path(workdir)
        orchestrator = Orchestrator(
            repository=JsonRepository(work / "data"),
            generator=MockGenerationEngine(work / "data" / "artifacts"),
            trace_recorder=TraceRecorder(work / "data" / "traces"),
        )
        rows: list[dict] = []
        for arm, feedback_mode, updater in ARMS:
            for sampler in samplers:
                for seed in seeds:
                    rows.append(
                        run_session(
                            orchestrator,
                            arm=arm,
                            feedback_mode=feedback_mode,
                            updater=updater,
                            sampler=sampler,
                            seed=seed,
                            max_rounds=max_rounds,
                            candidate_count=candidate_count,
                            steering_dimension=steering_dimension,
                            trust_radius=trust_radius,
                            convergence_patience=convergence_patience,
                            convergence_min_delta=convergence_min_delta,
                        )
                    )

    summary = _summarize(rows)
    _write_results_csv(output_dir / "results.csv", rows)
    _write_findings(output_dir / "findings.md", summary, max_rounds=max_rounds)
    return rows, summary


def _summarize(rows: list[dict]) -> list[dict]:
    """Aggregate per arm."""

    groups: dict[str, list[dict]] = {}
    for row in rows:
        groups.setdefault(row["arm"], []).append(row)

    summary: list[dict] = []
    for arm, group in groups.items():
        converged_rows = [r for r in group if r["converged"]]
        rtc_values = [int(r["rounds_to_convergence"]) for r in converged_rows]
        summary.append(
            {
                "arm": arm,
                "sessions": len(group),
                "pct_converged": round(100.0 * len(converged_rows) / len(group), 1),
                "mean_rounds_to_convergence": round(sum(rtc_values) / len(rtc_values), 2) if rtc_values else None,
                "mean_final_distance": round(sum(r["final_distance_to_target"] for r in group) / len(group), 4),
            }
        )

    summary.sort(
        key=lambda item: (
            item["mean_rounds_to_convergence"] if item["mean_rounds_to_convergence"] is not None else 1e9,
            item["mean_final_distance"],
        )
    )
    return summary


def _write_results_csv(path: Path, rows: list[dict]) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=RESULT_FIELDS)
        writer.writeheader()
        writer.writerows(rows)


def _write_findings(path: Path, summary: list[dict], *, max_rounds: int) -> None:
    lines: list[str] = []
    lines.append("# Does structured critique speed up steering convergence?\n")
    lines.append(
        "Synthetic study: a synthetic user with a fixed hidden target rates candidates by closeness "
        f"over a budget of {max_rounds} rounds, on the deterministic mock backend (no GPU). Two arms "
        "see the same preferences — the critique arm additionally tags each candidate, and the "
        "`critique_weighted_preference` updater uses those tags to steer. Convergence is detected by "
        "`app/engine/convergence.py`.\n"
    )
    lines.append("## Per-arm summary\n")
    lines.append("| Arm | Sessions | % converged | Mean rounds-to-convergence | Mean final distance |")
    lines.append("|---|---:|---:|---:|---:|")
    for item in summary:
        rtc = item["mean_rounds_to_convergence"]
        rtc_text = f"{rtc:.2f}" if rtc is not None else "—"
        lines.append(
            f"| {item['arm']} | {item['sessions']} | {item['pct_converged']:.1f}% | "
            f"{rtc_text} | {item['mean_final_distance']:.4f} |"
        )
    lines.append("")

    lines.append("## Interpretation\n")
    by_arm = {item["arm"]: item for item in summary}
    baseline = by_arm.get("baseline_scalar")
    critique = by_arm.get("critique_weighted")
    if baseline and critique:
        b_rtc = baseline["mean_rounds_to_convergence"]
        c_rtc = critique["mean_rounds_to_convergence"]
        if b_rtc is not None and c_rtc is not None:
            faster = "fewer" if c_rtc < b_rtc else "more"
            lines.append(
                f"- The critique arm reached a settled state in a mean of {c_rtc:.2f} rounds vs "
                f"{b_rtc:.2f} for the tag-blind baseline — {faster} rounds when reasons are supplied.\n"
                f"- Mean final distance to the hidden target: critique {critique['mean_final_distance']:.4f} "
                f"vs baseline {baseline['mean_final_distance']:.4f} (lower is closer).\n"
                "- Because both arms consume identical ratings, any gap is attributable to the critique "
                "tags actually moving the steering vector through `critique_weighted_preference`.\n"
            )

    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    output_dir = Path("output/critique_comparison")
    rows, summary = run_comparison(output_dir)
    print(f"Ran {len(rows)} synthetic sessions across {len(summary)} arms.")
    print(f"Wrote {output_dir / 'results.csv'} and {output_dir / 'findings.md'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
