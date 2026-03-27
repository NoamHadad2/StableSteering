# Repeated Bundle Analysis

This appendix-style note summarizes the repeated bundle under `paper/results/seed_policy_slice/`.

## Scope

- prompts: `3`
- policies: `2`
- repeated runs per prompt-policy cell: `3`
- completed runs represented in the bundle: `18`
- rounds represented in the bundle: `36`
- candidate rows represented in the bundle: `180`

## What the derived tables show

- `seed_fixed_per_candidate`: 2.0 rounds/run, 1.0 feedback events/run, 10.0 candidates/run, 5.0 candidates/round, per-candidate selection rate reported
- `seed_fixed_per_round`: 2.0 rounds/run, 1.0 feedback events/run, 10.0 candidates/run, 5.0 candidates/round, per-candidate selection rate reported

## Conservative interpretation

- workflow counts are invariant within this bundle: `seed_fixed_per_candidate` stays at 2.0 rounds/run and 1.0 feedback events/run; `seed_fixed_per_round` stays at 2.0 rounds/run and 1.0 feedback events/run
- the analysis is descriptive only; it does not compare human preference, image quality, or statistical significance
- candidate-count differences reflect policy budget and interaction structure, so they should be read as workflow properties rather than superiority signals

## Output artifacts

- `cell_summary.csv`
- `policy_summary.csv`
- `analysis_summary.md`
- `analysis_summary.html`

Source tables remain in `paper/results/seed_policy_slice/tables/`.