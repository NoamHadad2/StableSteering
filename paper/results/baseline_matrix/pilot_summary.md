# Pilot Baseline Matrix Summary

This note summarizes the executed minimal baseline matrix bundle under `paper/results/baseline_matrix/`.

## Run scope

- prompts: `3`
- policies: `3`
- independent repeats per prompt-policy cell: `3`
- completed runs: `27`
- completed rounds: `36`
- candidate images: `144`

Policies:

1. `prompt_only_manual`
2. `no_update_random_sampling`
3. `stablesteering_default`

## Safe observations

- the bounded runner completed all planned runs on the real Diffusers backend
- the StableSteering default policy is the only policy in this pilot that performs a feedback update and follow-up round
- the repeated pilot preserved workflow-level counts across the three repeats in every prompt-policy cell:
  - prompt-only manual iteration: always `1` round, `0` feedback events
  - no-update random sampling: always `1` round, `0` feedback events
  - StableSteering default steering loop: always `2` rounds, `1` feedback event
- the bundle now includes per-run trace reports, run summaries, and CSV tables that can be reused for paper-facing analysis
- the next budget-normalized check should isolate seed-policy effects under matched budgets rather than support any image-quality conclusion

## Appendix-style sanity-check note

- `130/144` candidates passed all lightweight visual checks
- `14/144` candidates were flagged only on the `has_edge_detail` heuristic
- those flags are concentrated in the portrait prompt and should be treated as a weak screening signal, not as a human-quality judgment

## What the repeated pilot adds

- it adds a small repeatability extension beyond the earlier one-shot pilot
- it supports a narrow claim of stable workflow counts under three independent repeats per prompt-policy cell
- it does not support significance language
- it does not support claims about human-perceived quality or final-image superiority

## What this pilot does not prove

- it does not establish statistical significance
- it does not establish superiority over prompt-only workflows
- it does not replace a broader repeated-run robustness study
- it does not replace a broader prompt suite or a fuller evaluation protocol
