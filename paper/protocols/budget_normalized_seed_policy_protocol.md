# Budget-Normalized Seed-Policy Slice

## Goal

Measure whether seed policy changes workflow behavior under matched budgets.

## What is held constant

- backend/model
- prompt subset
- sampler
- updater
- candidate count
- round budget
- image size
- guidance scale
- inference steps
- repeat count

## What changes

- `fixed-per-round`
- `fixed-per-candidate`

## Why this exists

The current repeated pilot shows workflow-count repeatability, but it does not isolate seed-policy effects under matched budgets. This slice is the smallest additional experiment that addresses that gap without turning the paper into a broad benchmark campaign.

## Expected output

- results bundle under `paper/results/seed_policy_slice/`
- repeated per-run summaries and trace reports
- appendix-style derived analysis under `paper/results/seed_policy_slice/analysis/`

## Claim boundary

- supports workflow-level comparison only
- does not support image-quality superiority claims
- does not replace a broader prompt suite
