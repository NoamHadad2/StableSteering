# Repeated Bundle Analysis

This appendix-style note summarizes the repeated bundle under `paper/results/updater_ablation/`.

## Scope

- prompts: `3`
- policies: `3`
- repeated runs per prompt-policy cell: `3`
- completed runs represented in the bundle: `27`
- rounds represented in the bundle: `54`
- candidate rows represented in the bundle: `270`

## What the derived tables show

- `updater_linear_preference`: 2.0 rounds/run, 1.0 feedback events/run, 10.0 candidates/run, 5.0 candidates/round, per-candidate selection rate reported
- `updater_winner_average`: 2.0 rounds/run, 1.0 feedback events/run, 10.0 candidates/run, 5.0 candidates/round, per-candidate selection rate reported
- `updater_winner_copy`: 2.0 rounds/run, 1.0 feedback events/run, 10.0 candidates/run, 5.0 candidates/round, per-candidate selection rate reported

## Conservative interpretation

- workflow counts are invariant within this bundle: `updater_linear_preference` stays at 2.0 rounds/run and 1.0 feedback events/run; `updater_winner_average` stays at 2.0 rounds/run and 1.0 feedback events/run; `updater_winner_copy` stays at 2.0 rounds/run and 1.0 feedback events/run
- the analysis is descriptive only; it does not compare human preference, image quality, or statistical significance
- candidate-count differences reflect policy budget and interaction structure, so they should be read as workflow properties rather than superiority signals

## Output artifacts

- `cell_summary.csv`
- `policy_summary.csv`
- `analysis_summary.md`
- `analysis_summary.html`

Source tables remain in `paper/results/updater_ablation/tables/`.