# Sampler and Feedback Comparison Results

This bundle compares distinct sampling strategies and preference-model variants under a shared oracle target-recovery protocol.

- targets: `3`
- policies: `8`
- runs: `24`
- rounds: `120`
- candidate rows: `480`

Comparison slices:

- sampler slice: fixed updater and feedback mode, varying sampler family
- feedback-model slice: fixed sampler, varying updater and feedback representation

Key outputs:

- `manifest.json`
- `tables/policy_summary.csv`
- `tables/runs.csv`
- `tables/rounds.csv`
- `analysis/analysis_summary.md`
- `analysis/sampler_slice_curve.svg`
- `analysis/feedback_slice_curve.svg`
