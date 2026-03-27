# Baseline Matrix Results

This directory contains the paper-facing minimal baseline comparison matrix.

What it measures:

- prompt-only manual iteration as a one-round prompt-render proxy
- no-update random sampling without feedback-driven steering
- the StableSteering default loop with one feedback update and a follow-up round

Shared settings are described in `protocol_snapshot.yaml`. Policy-specific overrides are recorded in the same snapshot and in `manifest.json`.

Current run count: 27 across 3 prompts.

Current aggregate summary: 54 rounds, 270 candidate images, and 23 candidates flagged by the lightweight visual checks.

Key outputs:

- `manifest.json`
- `protocol_snapshot.yaml`
- `tables/baseline_summary.csv`
- `tables/repeat_summary.csv`
- `tables/runs.csv`
- `tables/rounds.csv`
- `tables/candidates.csv`
- `runs/<run_id>/summary.json`
- `runs/<run_id>/trace_report.html`

This runner is intentionally bounded: it uses a tiny prompt suite, isolated per-run runtime directories, and conservative comparison policies. It is a bridge from the paper package to a concrete empirical scaffold, not a full benchmark campaign.
