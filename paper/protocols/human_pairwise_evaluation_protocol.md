# Human Pairwise Evaluation Protocol

## Purpose

This protocol defines a small human-facing pairwise evaluation layer for StableSteering.

Its goal is not to replace the automated proxy studies. Its role is to provide a lightweight, auditable path for collecting human judgments over a fixed set of curated comparisons.

## Evaluation Question

Given the same prompt family, do human judges prefer the final StableSteering result over:

1. the prompt-only baseline render
2. a no-update random-sampling representative

## Comparison Set

The default package contains:

- 3 prompt families
- 2 pair types per prompt family
- 6 total image pairs

Each pair is built from existing paper artifacts under `paper/results/baseline_matrix/`.

## Judge Instructions

For each pair, answer:

> Which image better satisfies the prompt while remaining visually coherent?

If the judge cannot decide, they may mark:

- `tie`
- `invalid` if both images are clearly broken for the prompt

## Suggested Metadata

For each judgment, record:

- evaluator id
- pair id
- chosen side: `left`, `right`, `tie`, or `invalid`
- confidence: `1` to `5`
- optional notes

## Recommended Collection Practice

- randomize left/right placement once when building the package
- do not allow judges to see policy labels during annotation
- collect at least 3 raters before reporting any proportion as evidence
- report pairwise win rate with exact numerator and denominator
- keep the current paper conservative unless multiple raters are collected

## Interpretation Boundary

- this protocol is designed for a small pilot, not a publishable human-subjects study on its own
- if used in a paper, the manuscript should report the number of raters and explicitly state whether the results are exploratory
