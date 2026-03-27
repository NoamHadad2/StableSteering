# Minimal Baseline Protocol

## Goal

This protocol defines the smallest comparison needed to move the paper from a platform demonstration toward a modest empirical comparison.

## What this protocol measures

- whether prompt-only manual iteration behaves differently from an explicit steering loop
- whether no-update sampling is distinguishable from feedback-driven steering
- whether the StableSteering default loop provides a cleaner end-to-end workflow with preserved artifacts

## Fixed settings

- model/backend: `runwayml/stable-diffusion-v1-5` on the Diffusers backend
- image size: `512x512`
- candidate count: `5`
- guidance scale: `7.0`
- denoising steps: `20`
- feedback mode: `scalar_rating`
- seed policy: `fixed-per-round`
- stopping rule: five rounds

## Baseline overrides

The runner applies small baseline-specific overrides so the comparison stays bounded while still using the real code paths:

- `prompt_only_manual`
  - `candidate_count=1`
  - `sampler=random_local`
  - `updater=winner_copy`
  - `seed_policy=fixed-per-round`
- `no_update_random_sampling`
  - `candidate_count=5`
  - `sampler=random_local`
  - `updater=winner_copy`
  - `seed_policy=fixed-per-round`
- `stablesteering_default`
  - `candidate_count=5`
  - `sampler=exploit_orthogonal`
  - `updater=winner_average`
  - `seed_policy=fixed-per-candidate`

## Prompt suite

The prompt suite is intentionally small:

- product hero shot
- portrait / character
- landscape / environment

Each prompt is accompanied by a negative prompt and a locked session configuration.

## Baselines

1. Prompt-only manual iteration
2. No-update random sampling
3. StableSteering default steering loop

## Outputs

The paper-facing output bundle should land under `paper/results/baseline_matrix/` and include:

- `manifest.json`
- `README.md`
- `protocol_snapshot.yaml`
- `runs/`
- `tables/`
- `figures/`

## What this protocol does not claim

- it does not claim that StableSteering is best
- it does not claim statistical significance before results exist
- it does not claim a full benchmark suite
- it does not replace broader prompt coverage or robustness analysis

## Execution note

The current runner script executes the bounded comparison, writes the paper-facing result tables, and preserves the raw runtime bundle under `paper/results/baseline_matrix/`. It is intentionally small and conservative, not a full benchmark campaign.
