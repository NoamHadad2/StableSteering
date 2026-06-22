from __future__ import annotations

import argparse
import csv
import html
import statistics
from collections import defaultdict
from pathlib import Path
from typing import Any


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _paper_root() -> Path:
    return _repo_root() / "paper"


def _results_root() -> Path:
    return _paper_root() / "results" / "baseline_matrix"


def _tables_root(results_dir: Path | None = None) -> Path:
    return (results_dir or _results_root()) / "tables"


def _analysis_root(results_dir: Path | None = None) -> Path:
    return (results_dir or _results_root()) / "analysis"


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def _write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fieldnames})


def _write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _safe_int(value: Any, default: int = 0) -> int:
    if value in {"", None}:
        return default
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _safe_float(value: Any, default: float = 0.0) -> float:
    if value in {"", None}:
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _rounded(value: float) -> float:
    return round(value, 3)


def _mean_std(values: list[float]) -> tuple[float, float]:
    if not values:
        return 0.0, 0.0
    if len(values) == 1:
        return values[0], 0.0
    return statistics.mean(values), statistics.pstdev(values)


def _group_rows(rows: list[dict[str, str]], key_fn) -> dict[str, list[dict[str, str]]]:
    grouped: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        grouped[key_fn(row)].append(row)
    return grouped


def _selection_rate_is_meaningful(baseline_id: str) -> bool:
    return baseline_id != "no_update_random_sampling"


def _build_cell_rows(
    runs: list[dict[str, str]],
    rounds: list[dict[str, str]],
    candidates: list[dict[str, str]],
) -> list[dict[str, Any]]:
    rounds_by_cell = _group_rows(rounds, lambda row: row["cell_id"])
    candidates_by_cell = _group_rows(candidates, lambda row: row["cell_id"])
    cells = _group_rows(runs, lambda row: row["cell_id"])

    rows: list[dict[str, Any]] = []
    for cell_id, cell_runs in cells.items():
        first_run = cell_runs[0]
        cell_rounds = rounds_by_cell.get(cell_id, [])
        cell_candidates = candidates_by_cell.get(cell_id, [])
        round_values = [_safe_float(run.get("rounds_completed")) for run in cell_runs]
        feedback_values = [_safe_float(run.get("feedback_events")) for run in cell_runs]
        candidate_counts_per_run = [
            float(sum(1 for row in cell_candidates if row.get("run_id") == run["run_id"]))
            for run in cell_runs
        ]
        candidates_per_round = [
            float(sum(1 for row in cell_candidates if row.get("round_id") == round_row["round_id"]))
            for round_row in cell_rounds
        ]

        mean_rounds_per_run, std_rounds_per_run = _mean_std(round_values)
        mean_feedback_per_run, std_feedback_per_run = _mean_std(feedback_values)
        mean_candidates_per_run, std_candidates_per_run = _mean_std(candidate_counts_per_run)
        mean_candidates_per_round, std_candidates_per_round = _mean_std(candidates_per_round)

        selected_candidate_count = sum(1 for row in cell_candidates if str(row.get("selected", "")).lower() == "true")
        failing_candidate_count = sum(
            1 for row in cell_candidates if str(row.get("failed_checks", "")).strip() not in {"", "[]"}
        )

        candidate_count = len(cell_candidates)
        run_count = len(cell_runs)
        round_count = len(cell_rounds)
        selection_meaningful = _selection_rate_is_meaningful(first_run["baseline_id"])

        rows.append(
            {
                "cell_id": cell_id,
                "prompt_id": first_run["prompt_id"],
                "prompt_label": first_run["prompt_label"],
                "baseline_id": first_run["baseline_id"],
                "baseline_label": first_run["baseline_label"],
                "run_count": run_count,
                "completed_run_count": sum(1 for run in cell_runs if run.get("status") == "completed"),
                "round_count": round_count,
                "feedback_event_count": sum(_safe_int(run.get("feedback_events")) for run in cell_runs),
                "candidate_count": candidate_count,
                "selected_candidate_count": selected_candidate_count,
                "failing_candidate_count": failing_candidate_count,
                "mean_rounds_per_run": _rounded(mean_rounds_per_run),
                "std_rounds_per_run": _rounded(std_rounds_per_run),
                "mean_feedback_events_per_run": _rounded(mean_feedback_per_run),
                "std_feedback_events_per_run": _rounded(std_feedback_per_run),
                "mean_candidates_per_run": _rounded(mean_candidates_per_run),
                "std_candidates_per_run": _rounded(std_candidates_per_run),
                "mean_candidates_per_round": _rounded(mean_candidates_per_round if round_count else 0.0),
                "std_candidates_per_round": _rounded(std_candidates_per_round),
                "selected_candidates_per_run": _rounded(selected_candidate_count / run_count) if run_count else 0.0,
                "selected_candidate_rate_per_candidate": (
                    _rounded(selected_candidate_count / candidate_count) if selection_meaningful and candidate_count else ""
                ),
                "failing_candidates_per_run": _rounded(failing_candidate_count / run_count) if run_count else 0.0,
                "failing_candidate_rate_per_candidate": _rounded(failing_candidate_count / candidate_count)
                if candidate_count
                else 0.0,
                "selection_rate_is_meaningful": selection_meaningful,
            }
        )

    rows.sort(key=lambda row: (row["prompt_id"], row["baseline_id"]))
    return rows


def _build_policy_rows(
    cell_rows: list[dict[str, Any]],
    runs: list[dict[str, str]],
    rounds: list[dict[str, str]],
    candidates: list[dict[str, str]],
) -> list[dict[str, Any]]:
    runs_by_policy = _group_rows(runs, lambda row: row["baseline_id"])
    cells_by_policy = _group_rows(cell_rows, lambda row: row["baseline_id"])
    rounds_by_policy = _group_rows(rounds, lambda row: row["baseline_id"])
    candidates_by_run = _group_rows(candidates, lambda row: row["run_id"])
    candidates_by_round = _group_rows(candidates, lambda row: row["round_id"])
    rounds_by_run = _group_rows(rounds, lambda row: row["run_id"])

    rows: list[dict[str, Any]] = []
    for baseline_id, policy_runs in runs_by_policy.items():
        policy_cells = cells_by_policy.get(baseline_id, [])
        candidate_count = sum(_safe_int(row.get("candidate_count")) for row in policy_cells)
        round_count = sum(_safe_int(row.get("round_count")) for row in policy_cells)
        selected_candidate_count = sum(_safe_int(row.get("selected_candidate_count")) for row in policy_cells)
        failing_candidate_count = sum(_safe_int(row.get("failing_candidate_count")) for row in policy_cells)
        run_round_values = [_safe_float(run.get("rounds_completed")) for run in policy_runs]
        run_feedback_values = [_safe_float(run.get("feedback_events")) for run in policy_runs]
        candidate_counts_per_run = [float(len(candidates_by_run.get(run["run_id"], []))) for run in policy_runs]
        candidates_per_round = [float(len(candidates_by_round.get(round_row["round_id"], []))) for round_row in rounds_by_policy.get(baseline_id, [])]

        mean_rounds_per_run, std_rounds_per_run = _mean_std(run_round_values)
        mean_feedback_per_run, std_feedback_per_run = _mean_std(run_feedback_values)
        mean_candidates_per_run, std_candidates_per_run = _mean_std(candidate_counts_per_run)
        mean_candidates_per_round, std_candidates_per_round = _mean_std(candidates_per_round)

        rows.append(
            {
                "baseline_id": baseline_id,
                "baseline_label": policy_runs[0]["baseline_label"],
                "prompt_count": len(policy_cells),
                "cell_count": len(policy_cells),
                "run_count": len(policy_runs),
                "completed_run_count": sum(1 for run in policy_runs if run.get("status") == "completed"),
                "round_count": round_count,
                "feedback_event_count": sum(_safe_int(run.get("feedback_events")) for run in policy_runs),
                "candidate_count": candidate_count,
                "selected_candidate_count": selected_candidate_count,
                "failing_candidate_count": failing_candidate_count,
                "mean_rounds_per_run": _rounded(mean_rounds_per_run),
                "std_rounds_per_run": _rounded(std_rounds_per_run),
                "mean_feedback_events_per_run": _rounded(mean_feedback_per_run),
                "std_feedback_events_per_run": _rounded(std_feedback_per_run),
                "mean_candidates_per_run": _rounded(mean_candidates_per_run),
                "std_candidates_per_run": _rounded(std_candidates_per_run),
                "mean_candidates_per_round": _rounded(mean_candidates_per_round),
                "std_candidates_per_round": _rounded(std_candidates_per_round),
                "selected_candidates_per_run": _rounded(selected_candidate_count / len(policy_runs)) if policy_runs else 0.0,
                "selected_candidate_rate_per_candidate": (
                    _rounded(selected_candidate_count / candidate_count)
                    if _selection_rate_is_meaningful(baseline_id) and candidate_count
                    else ""
                ),
                "failing_candidate_rate_per_candidate": _rounded(failing_candidate_count / candidate_count)
                if candidate_count
                else 0.0,
                "selection_rate_is_meaningful": _selection_rate_is_meaningful(baseline_id),
            }
        )

    rows.sort(key=lambda row: row["baseline_id"])
    return rows


def _markdown_table(rows: list[dict[str, Any]], columns: list[str]) -> str:
    header = "| " + " | ".join(columns) + " |"
    separator = "| " + " | ".join("---" if i == 0 else "---:" for i, _ in enumerate(columns)) + " |"
    lines = [header, separator]
    for row in rows:
        lines.append("| " + " | ".join(str(row.get(column, "")) for column in columns) + " |")
    return "\n".join(lines)


def _html_table(rows: list[dict[str, Any]], columns: list[str], title: str) -> str:
    head = "".join(f"<th>{html.escape(column)}</th>" for column in columns)
    body_rows = []
    for row in rows:
        cells = "".join(f"<td>{html.escape(str(row.get(column, '')))}</td>" for column in columns)
        body_rows.append(f"<tr>{cells}</tr>")
    body = "\n".join(body_rows)
    return f"""
      <section>
        <h2>{html.escape(title)}</h2>
        <div class="table-wrap">
          <table>
            <thead><tr>{head}</tr></thead>
            <tbody>{body}</tbody>
          </table>
        </div>
      </section>
    """


def _build_summary_markdown(results_dir: Path, cell_rows: list[dict[str, Any]], policy_rows: list[dict[str, Any]]) -> str:
    prompt_count = len({row["prompt_id"] for row in cell_rows})
    policy_count = len(policy_rows)
    run_count = sum(_safe_int(row.get("run_count")) for row in policy_rows)
    round_count = sum(_safe_int(row.get("round_count")) for row in policy_rows)
    candidate_count = sum(_safe_int(row.get("candidate_count")) for row in policy_rows)
    bundle_name = results_dir.name

    summary_lines = [
        "# Repeated Bundle Analysis",
        "",
        f"This appendix-style note summarizes the repeated bundle under `paper/results/{bundle_name}/`.",
        "",
        "## Scope",
        "",
        f"- prompts: `{prompt_count}`",
        f"- policies: `{policy_count}`",
        f"- repeated runs per prompt-policy cell: `3`",
        f"- completed runs represented in the bundle: `{run_count}`",
        f"- rounds represented in the bundle: `{round_count}`",
        f"- candidate rows represented in the bundle: `{candidate_count}`",
        "",
        "## What the derived tables show",
        "",
    ]

    for row in policy_rows:
        selection_note = (
            "per-candidate selection rate reported"
            if row["selection_rate_is_meaningful"]
            else "per-candidate selection rate omitted because no selection signal is recorded"
        )
        summary_lines.append(
            f"- `{row['baseline_id']}`: {row['mean_rounds_per_run']} rounds/run, "
            f"{row['mean_feedback_events_per_run']} feedback events/run, "
            f"{row['mean_candidates_per_run']} candidates/run, "
            f"{row['mean_candidates_per_round']} candidates/round, {selection_note}"
        )

    summary_lines.extend(
        ["", "## Conservative interpretation", ""]
    )
    if policy_rows:
        workflow_line = "; ".join(
            f"`{row['baseline_id']}` stays at {row['mean_rounds_per_run']} rounds/run and {row['mean_feedback_events_per_run']} feedback events/run"
            for row in policy_rows
        )
        summary_lines.append(f"- workflow counts are invariant within this bundle: {workflow_line}")
    summary_lines.extend(
        [
            "- the analysis is descriptive only; it does not compare human preference, image quality, or statistical significance",
            "- candidate-count differences reflect policy budget and interaction structure, so they should be read as workflow properties rather than superiority signals",
        ]
    )
    if any(not row["selection_rate_is_meaningful"] for row in policy_rows):
        summary_lines.append(
            "- any policy without a recorded selection signal omits per-candidate selection rates by design"
        )
    summary_lines.extend(
        [
            "",
            "## Output artifacts",
            "",
            "- `cell_summary.csv`",
            "- `policy_summary.csv`",
            "- `analysis_summary.md`",
            "- `analysis_summary.html`",
            "",
            f"Source tables remain in `paper/results/{bundle_name}/tables/`.",
        ]
    )
    return "\n".join(summary_lines)


def _build_summary_html(results_dir: Path, cell_rows: list[dict[str, Any]], policy_rows: list[dict[str, Any]]) -> str:
    bundle_name = results_dir.name
    policy_columns = [
        "baseline_id",
        "baseline_label",
        "run_count",
        "round_count",
        "candidate_count",
        "mean_rounds_per_run",
        "mean_feedback_events_per_run",
        "mean_candidates_per_run",
        "mean_candidates_per_round",
        "selected_candidates_per_run",
        "selected_candidate_rate_per_candidate",
        "failing_candidate_rate_per_candidate",
    ]
    cell_columns = [
        "cell_id",
        "prompt_id",
        "baseline_id",
        "run_count",
        "round_count",
        "candidate_count",
        "mean_rounds_per_run",
        "mean_feedback_events_per_run",
        "mean_candidates_per_run",
        "mean_candidates_per_round",
        "selected_candidates_per_run",
        "selected_candidate_rate_per_candidate",
        "failing_candidate_rate_per_candidate",
    ]
    bullets = [
        f"<li><code>{html.escape(str(row['baseline_id']))}</code> stays at {html.escape(str(row['mean_rounds_per_run']))} rounds/run and {html.escape(str(row['mean_feedback_events_per_run']))} feedback events/run.</li>"
        for row in policy_rows
    ]
    if not bullets:
        bullets = ["<li>No policy rows were found.</li>"]

    return f"""<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>StableSteering Analysis Summary</title>
    <style>
      :root {{
        color-scheme: light;
        --bg: #f4efe6;
        --panel: #fffdf8;
        --border: #d9cdbf;
        --text: #241d18;
        --muted: #6f5b48;
        --accent: #8a4f14;
      }}
      * {{ box-sizing: border-box; }}
      body {{ margin: 0; background: linear-gradient(180deg, #efe6d7, #faf7f1); color: var(--text); font-family: Georgia, "Times New Roman", serif; }}
      main {{ max-width: 1180px; margin: 0 auto; padding: 28px 18px 48px; }}
      .panel {{ background: rgba(255, 252, 247, 0.97); border: 1px solid var(--border); border-radius: 20px; box-shadow: 0 16px 36px rgba(73, 51, 25, 0.08); padding: 28px 28px 36px; }}
      h1, h2, h3 {{ font-family: "Segoe UI", system-ui, sans-serif; line-height: 1.2; }}
      p, li {{ line-height: 1.55; }}
      .meta {{ color: var(--muted); font-family: "Segoe UI", system-ui, sans-serif; }}
      a {{ color: var(--accent); }}
      .table-wrap {{ overflow-x: auto; margin: 12px 0 24px; }}
      table {{ border-collapse: collapse; width: 100%; min-width: 860px; }}
      th, td {{ border-top: 1px solid var(--border); padding: 8px 10px; text-align: left; vertical-align: top; }}
      th {{ position: sticky; top: 0; background: #fcf8f0; }}
      code {{ background: #f7f1e9; padding: 0.12rem 0.3rem; border-radius: 6px; }}
      @media (max-width: 760px) {{
        main {{ padding: 18px 12px 36px; }}
        .panel {{ padding: 20px 16px 28px; }}
      }}
    </style>
  </head>
  <body>
    <main>
      <div class="panel">
        <p class="meta">Derived from the repeated bundle in <code>paper/results/{html.escape(bundle_name)}/tables/</code>.</p>
        <h1>StableSteering Analysis Summary</h1>
        <p>This page is a conservative, workflow-focused summary. It deliberately avoids superiority language and treats candidate-budget differences as structural, not comparative.</p>
        <h2>Interpretation</h2>
        <ul>
          {''.join(bullets)}
          <li>This analysis is descriptive only and does not support image-quality or superiority claims.</li>
        </ul>
        <h2>Policy Summary</h2>
        {_html_table(policy_rows, policy_columns, "policy_summary.csv")}
        <h2>Cell Summary</h2>
        {_html_table(cell_rows, cell_columns, "cell_summary.csv")}
      </div>
    </main>
  </body>
</html>
"""


def main() -> int:
    parser = argparse.ArgumentParser(description="Build paper-facing analysis artifacts for the repeated baseline pilot.")
    parser.add_argument(
        "--results-dir",
        type=Path,
        default=_results_root(),
        help="Results directory that contains the repeated pilot tables/ folder.",
    )
    parser.add_argument(
        "--analysis-dir",
        type=Path,
        default=None,
        help="Directory where derived analysis artifacts will be written.",
    )
    args = parser.parse_args()

    results_dir = args.results_dir
    tables_dir = _tables_root(results_dir)
    analysis_dir = args.analysis_dir or _analysis_root(results_dir)
    analysis_dir.mkdir(parents=True, exist_ok=True)

    runs = _read_csv(tables_dir / "runs.csv")
    rounds = _read_csv(tables_dir / "rounds.csv")
    candidates = _read_csv(tables_dir / "candidates.csv")
    cell_rows = _build_cell_rows(runs, rounds, candidates)
    policy_rows = _build_policy_rows(cell_rows, runs, rounds, candidates)

    cell_columns = [
        "cell_id",
        "prompt_id",
        "prompt_label",
        "baseline_id",
        "baseline_label",
        "run_count",
        "completed_run_count",
        "round_count",
        "feedback_event_count",
        "candidate_count",
        "selected_candidate_count",
        "failing_candidate_count",
        "mean_rounds_per_run",
        "std_rounds_per_run",
        "mean_feedback_events_per_run",
        "std_feedback_events_per_run",
        "mean_candidates_per_run",
        "std_candidates_per_run",
        "mean_candidates_per_round",
        "std_candidates_per_round",
        "selected_candidates_per_run",
        "selected_candidate_rate_per_candidate",
        "failing_candidates_per_run",
        "failing_candidate_rate_per_candidate",
        "selection_rate_is_meaningful",
    ]
    policy_columns = [
        "baseline_id",
        "baseline_label",
        "prompt_count",
        "cell_count",
        "run_count",
        "completed_run_count",
        "round_count",
        "feedback_event_count",
        "candidate_count",
        "selected_candidate_count",
        "failing_candidate_count",
        "mean_rounds_per_run",
        "std_rounds_per_run",
        "mean_feedback_events_per_run",
        "std_feedback_events_per_run",
        "mean_candidates_per_run",
        "std_candidates_per_run",
        "mean_candidates_per_round",
        "std_candidates_per_round",
        "selected_candidates_per_run",
        "selected_candidate_rate_per_candidate",
        "failing_candidate_rate_per_candidate",
        "selection_rate_is_meaningful",
    ]

    _write_csv(analysis_dir / "cell_summary.csv", cell_rows, cell_columns)
    _write_csv(analysis_dir / "policy_summary.csv", policy_rows, policy_columns)

    summary_markdown = _build_summary_markdown(results_dir, cell_rows, policy_rows)
    _write_text(analysis_dir / "analysis_summary.md", summary_markdown)
    _write_text(analysis_dir / "analysis_summary.html", _build_summary_html(results_dir, cell_rows, policy_rows))

    print(
        {
            "analysis_dir": str(analysis_dir),
            "files": [
                "cell_summary.csv",
                "policy_summary.csv",
                "analysis_summary.md",
                "analysis_summary.html",
            ],
        }
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
