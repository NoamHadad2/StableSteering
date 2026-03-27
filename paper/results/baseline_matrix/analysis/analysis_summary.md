# Repeated Bundle Analysis

This appendix-style note summarizes the repeated bundle under `paper/results/baseline_matrix/`.

## Scope

- prompts: `3`
- policies: `3`
- repeated runs per prompt-policy cell: `3`
- completed runs represented in the bundle: `27`
- rounds represented in the bundle: `36`
- candidate rows represented in the bundle: `144`

## What the derived tables show

- `no_update_random_sampling`: 1.0 rounds/run, 0.0 feedback events/run, 5.0 candidates/run, 5.0 candidates/round, per-candidate selection rate omitted because no selection signal is recorded
- `prompt_only_manual`: 1.0 rounds/run, 0.0 feedback events/run, 1.0 candidates/run, 1.0 candidates/round, per-candidate selection rate reported
- `stablesteering_default`: 2.0 rounds/run, 1.0 feedback events/run, 10.0 candidates/run, 5.0 candidates/round, per-candidate selection rate reported

## Conservative interpretation

- workflow counts are invariant within this bundle: `no_update_random_sampling` stays at 1.0 rounds/run and 0.0 feedback events/run; `prompt_only_manual` stays at 1.0 rounds/run and 0.0 feedback events/run; `stablesteering_default` stays at 2.0 rounds/run and 1.0 feedback events/run
- the analysis is descriptive only; it does not compare human preference, image quality, or statistical significance
- candidate-count differences reflect policy budget and interaction structure, so they should be read as workflow properties rather than superiority signals
- any policy without a recorded selection signal omits per-candidate selection rates by design

## Output artifacts

- `cell_summary.csv`
- `policy_summary.csv`
- `analysis_summary.md`
- `analysis_summary.html`

Source tables remain in `paper/results/baseline_matrix/tables/`.