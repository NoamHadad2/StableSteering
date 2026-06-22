# Fixed-Sampler Updater Ablation

## Goal

Measure how the steering-loop updater changes workflow behavior when the sampler and the rest of the runtime budget are held fixed.

## What is held constant

- backend/model
- prompt subset
- sampler
- seed policy
- candidate count
- round budget
- image size
- guidance scale
- inference steps
- repeat count

## What changes

- `winner_copy`
- `winner_average`
- `linear_preference`

## Why this exists

The paper claims modularity across samplers and updaters, but the current empirical package only exercises one default updater. This ablation is the smallest experiment that strengthens the modularity claim without implying a full algorithm benchmark.

## Expected output

- results bundle under `paper/results/updater_ablation/`
- repeated per-run summaries and trace reports
- appendix-style derived analysis under `paper/results/updater_ablation/analysis/`

## Claim boundary

- supports a bounded modularity comparison only
- does not establish that one updater is best in general
- does not replace broader prompt coverage or a normalized benchmark suite
