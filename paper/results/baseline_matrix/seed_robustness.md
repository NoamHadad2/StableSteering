# Seed Repeatability Note

This note summarizes the narrow repeatability signal supported by the repeated minimal baseline matrix.

## Scope

- prompts: `3`
- policies: `3`
- independent repeats per prompt-policy cell: `3`
- total runs: `27`

Source table:

- [tables/repeat_summary.csv](E:\Projects\StableSteering\paper\results\baseline_matrix\tables\repeat_summary.csv)

## Safe observations

- every prompt-only manual cell completed exactly `1` round per run with `0` feedback events
- every no-update random sampling cell completed exactly `1` round per run with `0` feedback events
- every StableSteering default cell completed exactly `2` rounds per run with `1` feedback event
- the observed standard deviation for `rounds per run` is `0.0` in every prompt-policy cell
- the observed standard deviation for `feedback events per run` is `0.0` in every prompt-policy cell

## What this supports

- a narrow claim that the bounded pilot is stable at the workflow-count level across three independent repeats
- stronger confidence that the pilot bundle is reproducible as an executed artifact package

## What this does not support

- any statistical-significance claim
- any claim that StableSteering produces better final images than the controls
- any claim that image quality is stable across seeds in a human-evaluated sense
- any claim that the portrait-prompt artifact flags reflect meaningful quality differences
- any claim about matched-budget seed-policy effects, which still need a separate budget-normalized slice

## Visual-check note

- the lightweight flags remain concentrated in the portrait prompt
- those flags come from weak artifact-screening heuristics, not human judgments
- for aggregate counts, see [pilot_summary.md](E:\Projects\StableSteering\paper\results\baseline_matrix\pilot_summary.md)
