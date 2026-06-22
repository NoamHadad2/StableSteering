from __future__ import annotations

import csv
from pathlib import Path

from scripts.run_convergence_comparison import RESULT_FIELDS, run_comparison


def test_run_comparison_produces_results_and_findings(tmp_path: Path) -> None:
    output_dir = tmp_path / "study"
    samplers = ["random_local"]
    updaters = ["winner_average", "bradley_terry_preference"]
    seeds = [0, 1]

    rows, summary = run_comparison(
        output_dir,
        samplers=samplers,
        updaters=updaters,
        seeds=seeds,
        max_rounds=5,
    )

    # One row per (sampler x updater x seed) session.
    assert len(rows) == len(samplers) * len(updaters) * len(seeds)
    # One summary entry per (sampler x updater) strategy.
    assert len(summary) == len(samplers) * len(updaters)

    results_csv = output_dir / "results.csv"
    findings_md = output_dir / "findings.md"
    assert results_csv.exists()
    assert findings_md.exists()

    with results_csv.open(encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        assert reader.fieldnames == RESULT_FIELDS
        csv_rows = list(reader)
    assert len(csv_rows) == len(rows)

    findings_text = findings_md.read_text(encoding="utf-8")
    assert "Per-strategy summary" in findings_text
    assert "Mean rounds-to-convergence" in findings_text


def test_run_comparison_rows_have_expected_shape(tmp_path: Path) -> None:
    rows, _ = run_comparison(
        tmp_path / "study",
        samplers=["spherical_cover"],
        updaters=["winner_average"],
        seeds=[0],
        max_rounds=6,
    )
    row = rows[0]
    assert set(row.keys()) == set(RESULT_FIELDS)
    assert isinstance(row["converged"], bool)
    assert 1 <= row["rounds_run"] <= 6
