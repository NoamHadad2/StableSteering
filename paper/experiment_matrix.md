# Experiment Matrix

## Purpose

This file defines the smallest experiment program needed to move from a systems/demo paper toward a stronger empirical paper.

## Current evidence already in repo

- one qualitative real example session
- one real backend smoke test
- backend and browser correctness tests
- an executed minimal baseline matrix bundle under `paper/results/baseline_matrix/`

This is enough for a bounded comparison scaffold, but not yet enough for broad comparative algorithm claims.

## Minimum baseline matrix

Use one narrow control-strategy comparison before any wider sweep:

1. `prompt-only` manual iteration
2. `no-update` random sampling
3. StableSteering default steering loop

Hold fixed:

- one model/backend
- one candidate budget
- one stopping rule
- one feedback mode
- one prompt suite
- one seed policy for the main comparison

This is the smallest comparison that answers the paper’s biggest missing question without turning the project into an uncontrolled benchmark campaign.

## Prompt suite recommendation

At minimum, include:

- product hero shot
- portrait / character
- landscape / environment

Optional phase-2 additions:

- object-centric studio shot
- style-sensitive artistic prompt

Each prompt should have:

- exact text prompt
- optional negative prompt
- session YAML
- stopping rule
- success criterion

## Metrics to report

- rounds to preferred result
- incumbent win rate
- within-session improvement rate
- candidate diversity proxy
- repeated-seed robustness
- user decision time
- user confidence, if added later

## Minimal paper-ready table set

Table 1:

- system capabilities by component

Table 2:

- benchmark prompt suite and configuration

Table 3:

- pilot comparative results across baselines and steering variants

## Controlled cycle-4 sweep

The broad cross-product sweep was too large to be paper-useful. A better first sweep is:

| ID | Config | Purpose |
|---|---|---|
| `B0` | `random_local`, `winner_average`, `scalar_rating`, `fixed-per-round`, `candidate_count=5`, `image_size=512x512`, `trust_radius=0.25`, `anchor_strength=0.35`, `guidance_scale=7.0`, `num_inference_steps=20`, `model_name=runwayml/stable-diffusion-v1-5` | Conservative baseline |
| `S1` | `B0` but `sampler=exploit_orthogonal` | More directed exploration |
| `S2` | `B0` but `sampler=axis_sweep` | Interpretable axis probing |
| `U1` | `B0` but `updater=winner_copy` | Stronger incumbent update |
| `R1` | `B0` but `seed_policy=fixed-per-candidate` | Robustness / noise sensitivity |

Use only the first 3 prompts for this sweep to keep cost bounded.

## Ranked experiment queue

1. Minimal baseline comparison matrix
2. Repeated-seed robustness check
3. Updater ablation on one fixed sampler

## Immediate implementation notes

1. Use the concrete protocol bundle in `paper/protocols/minimal_baseline_protocol.md` and `paper/protocols/minimal_baseline_prompt_suite.yaml` as the locked reference for the first comparison.
2. Refresh the scaffolded results directory with `scripts/run_paper_minimal_baseline_matrix.py` before any manual or automated execution work.
3. Add a corpus export script that writes one row per candidate and one row per feedback event.
4. Add one notebook or script that produces summary tables.
5. Keep `feedback_mode=scalar_rating` fixed in the first sweep to avoid confounding the comparison.
6. Use the checked-in motorcycle case-study config as the main steering-loop reference point.

## Current blocker summary

The minimal baseline matrix is now executed as a bounded bundle. The remaining blockers are robustness runs, broader prompt coverage, and an analysis notebook or summary script.
