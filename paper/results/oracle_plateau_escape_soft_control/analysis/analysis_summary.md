# Repeated-Seed Multi-Metric Oracle Analysis

This study repeats the oracle target-recovery protocol three times per target and evaluates the resulting trajectories under two pretrained image-embedding families.

## Scope

- targets: `3`
- repeats per target: `3`
- total runs: `9`
- total rounds: `90`

## Aggregate summary

- CLIP cosine: baseline `0.839`, final `0.878`, delta `0.039` (sd `0.022`)
- DINOv2 cosine: baseline `0.493`, final `0.590`, delta `0.097` (sd `0.090`)

## Target-level summary

| target | repeats | clip final (mean ± sd) | dinov2 final (mean ± sd) |
| --- | ---: | ---: | ---: |
| Black-and-white cat portrait | 3 | 0.877 ± 0.008 | 0.555 ± 0.104 |
| Mountain lake landscape | 3 | 0.850 ± 0.005 | 0.503 ± 0.048 |
| Red bicycle street photo | 3 | 0.906 ± 0.010 | 0.711 ± 0.016 |

## Interpretation boundary

- CLIP remains the oracle selection metric.
- DINOv2 is added as an independent evaluation metric rather than an oracle.
- Repeated seeds reduce the chance that the observed trend is a single-session artifact.
- The study is still a proxy target-recovery evaluation, not a human-preference study.

## Figure

![Repeated-seed multi-metric oracle convergence](oracle_multimetric_repeated.svg)
