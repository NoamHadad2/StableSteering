# Baseline Matrix Results

This directory contains the paper-facing minimal baseline comparison matrix and its derived appendix-style analysis layer.

What it measures:

- prompt-only manual iteration as a one-round prompt-render proxy
- no-update random sampling without feedback-driven steering
- the StableSteering default loop with one feedback update and a follow-up round

Shared settings are described in `protocol_snapshot.yaml`. Policy-specific overrides are recorded in the same snapshot and in `manifest.json`.

Current run count: 27 across 3 prompts.

Current aggregate summary: 36 rounds, 144 candidate images, and 14 candidates flagged by the lightweight visual checks.

Key outputs:

- `manifest.json`
- `protocol_snapshot.yaml`
- `tables/baseline_summary.csv`
- `tables/repeat_summary.csv`
- `tables/runs.csv`
- `tables/rounds.csv`
- `tables/candidates.csv`
- `analysis/cell_summary.csv`
- `analysis/policy_summary.csv`
- `analysis/analysis_summary.md`
- `analysis/analysis_summary.html`
- `runs/<run_id>/summary.json`
- `runs/<run_id>/trace_report.html`

This runner is intentionally bounded: it uses a tiny illustrative prompt suite, isolated per-run runtime directories, and conservative comparison policies. It is a bridge from the paper package to a concrete empirical scaffold, not a full benchmark campaign.
