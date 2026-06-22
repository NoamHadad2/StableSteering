"""Compare how fast and how reliably steering strategies converge.

This study uses the convergence signal added in ``app/engine/convergence.py``
to answer a concrete research question:

    Given a synthetic user with a fixed hidden target in steering space, which
    (sampler, updater) combinations reach a settled state in the fewest rounds,
    and how often do they converge within a fixed round budget?

It is GPU-free: it drives the orchestrator with the deterministic mock backend
(the same one the test suite uses), so it runs on a laptop with no model
download. The same code also works against the real Diffusers backend by
swapping the generator, if image-level results are wanted later.

Outputs (under ``output/convergence_comparison/`` by default):
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


DEFAULT_SAMPLERS = ["random_local", "line_search", "spherical_cover"]
DEFAULT_UPDATERS = ["winner_average", "bradley_terry_preference"]
DEFAULT_SEEDS = [0, 1, 2]

RESULT_FIELDS = [
    "sampler",
    "updater",
    "seed",
    "rounds_run",
    "converged",
    "rounds_to_convergence",
    "final_distance_to_target",
    "final_quiet_streak",
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

    ratings: dict[str, float] = {}
    for candidate in candidates:
        distance = _distance(candidate.z, target)
        ratings[candidate.id] = round(5.0 / (1.0 + distance), 4)
    return ratings


def run_session(
    orchestrator: Orchestrator,
    *,
    sampler: str,
    updater: str,
    seed: int,
    max_rounds: int,
    candidate_count: int,
    steering_dimension: int,
    trust_radius: float,
    convergence_patience: int,
    convergence_min_delta: float,
) -> dict:
    """Drive one synthetic session and return its convergence outcome row."""

    config = StrategyConfig(
        sampler=sampler,
        updater=updater,
        feedback_mode="scalar_rating",
        candidate_count=candidate_count,
        steering_dimension=steering_dimension,
        trust_radius=trust_radius,
        convergence_patience=convergence_patience,
        convergence_min_delta=convergence_min_delta,
    )
    experiment = orchestrator.create_experiment(
        ExperimentCreate(name=f"{sampler}+{updater}#{seed}", description="convergence study", config=config)
    )
    session = orchestrator.create_session(
        SessionCreate(experiment_id=experiment.id, prompt="A synthetic convergence study prompt")
    )
    target = _synthetic_target(seed, steering_dimension)

    rounds_run = 0
    report = orchestrator.get_session_convergence(session.id)
    for _ in range(max_rounds):
        round_response = orchestrator.generate_round(session.id)
        rounds_run += 1
        ratings = _rate_candidates(round_response.candidate_metadata, target)
        orchestrator.submit_feedback(
            round_response.round_id,
            FeedbackRequest(feedback_type="scalar_rating", payload={"ratings": ratings}),
        )
        report = orchestrator.get_session_convergence(session.id)
        if report.converged:
            break  # early stopping: the steering loop has settled

    final_session = orchestrator.get_session(session.id)
    return {
        "sampler": sampler,
        "updater": updater,
        "seed": seed,
        "rounds_run": rounds_run,
        "converged": report.converged,
        "rounds_to_convergence": report.rounds_to_convergence if report.converged else "",
        "final_distance_to_target": round(_distance(final_session.current_z, target), 4),
        "final_quiet_streak": report.quiet_streak,
    }


def run_comparison(
    output_dir: Path,
    *,
    samplers: list[str] | None = None,
    updaters: list[str] | None = None,
    seeds: list[int] | None = None,
    max_rounds: int = 12,
    candidate_count: int = 5,
    steering_dimension: int = 5,
    trust_radius: float = 0.55,
    convergence_patience: int = 2,
    convergence_min_delta: float = 0.04,
) -> tuple[list[dict], list[dict]]:
    """Run the strategy grid, write results.csv + findings.md, return the data."""

    samplers = samplers or DEFAULT_SAMPLERS
    updaters = updaters or DEFAULT_UPDATERS
    seeds = seeds or DEFAULT_SEEDS
    output_dir.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory(prefix="convergence_study_") as workdir:
        work = Path(workdir)
        orchestrator = Orchestrator(
            repository=JsonRepository(work / "data"),
            generator=MockGenerationEngine(work / "data" / "artifacts"),
            trace_recorder=TraceRecorder(work / "data" / "traces"),
        )
        rows: list[dict] = []
        for sampler in samplers:
            for updater in updaters:
                for seed in seeds:
                    rows.append(
                        run_session(
                            orchestrator,
                            sampler=sampler,
                            updater=updater,
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
    _write_findings(output_dir / "findings.md", summary, rows, max_rounds=max_rounds)
    return rows, summary


def _summarize(rows: list[dict]) -> list[dict]:
    """Aggregate per (sampler, updater) strategy."""

    groups: dict[tuple[str, str], list[dict]] = {}
    for row in rows:
        groups.setdefault((row["sampler"], row["updater"]), []).append(row)

    summary: list[dict] = []
    for (sampler, updater), group in groups.items():
        converged_rows = [r for r in group if r["converged"]]
        rtc_values = [int(r["rounds_to_convergence"]) for r in converged_rows]
        summary.append(
            {
                "sampler": sampler,
                "updater": updater,
                "sessions": len(group),
                "pct_converged": round(100.0 * len(converged_rows) / len(group), 1),
                "mean_rounds_to_convergence": round(sum(rtc_values) / len(rtc_values), 2) if rtc_values else None,
                "mean_final_distance": round(sum(r["final_distance_to_target"] for r in group) / len(group), 4),
                "mean_rounds_run": round(sum(r["rounds_run"] for r in group) / len(group), 2),
            }
        )

    summary.sort(
        key=lambda item: (
            -item["pct_converged"],
            item["mean_rounds_to_convergence"] if item["mean_rounds_to_convergence"] is not None else 1e9,
        )
    )
    return summary


def _write_results_csv(path: Path, rows: list[dict]) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=RESULT_FIELDS)
        writer.writeheader()
        writer.writerows(rows)


def _write_findings(path: Path, summary: list[dict], rows: list[dict], *, max_rounds: int) -> None:
    lines: list[str] = []
    lines.append("# Convergence comparison of steering strategies\n")
    lines.append(
        "Synthetic study: a synthetic user with a fixed hidden target in steering space "
        f"rates candidates by closeness, over a budget of {max_rounds} rounds per session, "
        "on the deterministic mock backend (no GPU). Convergence is detected by "
        "`app/engine/convergence.py`.\n"
    )
    lines.append("## Per-strategy summary\n")
    lines.append("| Sampler | Updater | Sessions | % converged | Mean rounds-to-convergence | Mean final distance | Mean rounds run |")
    lines.append("|---|---|---:|---:|---:|---:|---:|")
    for item in summary:
        rtc = item["mean_rounds_to_convergence"]
        rtc_text = f"{rtc:.2f}" if rtc is not None else "—"
        lines.append(
            f"| {item['sampler']} | {item['updater']} | {item['sessions']} | "
            f"{item['pct_converged']:.1f}% | {rtc_text} | {item['mean_final_distance']:.4f} | "
            f"{item['mean_rounds_run']:.2f} |"
        )
    lines.append("")

    best = summary[0] if summary else None
    if best is not None:
        rtc = best["mean_rounds_to_convergence"]
        rtc_text = f"{rtc:.2f} rounds" if rtc is not None else "n/a"
        lines.append("## Interpretation\n")
        lines.append(
            f"- **Fastest / most reliable to settle:** `{best['sampler']}` + `{best['updater']}` "
            f"({best['pct_converged']:.0f}% converged, mean {rtc_text}).\n"
            "- Lower *mean final distance* means the settled steering vector ended up closer to the "
            "synthetic user's hidden target, so % converged should be read together with it: a strategy "
            "can settle quickly without reaching the target.\n"
            "- Strategies that never reach the patience threshold show `—` and run the full round budget, "
            "indicating an unsettled (still-exploring) trajectory under this synthetic user.\n"
        )

    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    output_dir = Path("output/convergence_comparison")
    rows, summary = run_comparison(output_dir)
    print(f"Ran {len(rows)} synthetic sessions across {len(summary)} strategies.")
    print(f"Wrote {output_dir / 'results.csv'} and {output_dir / 'findings.md'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
