# Budget-Matched Direct Baseline Comparison

This bundle compares four methods under the same visible candidate budget: `5` rounds and `4` candidates per round.

## Headline results

- `no_update_resampling`: final CLIP `0.881` (gain `+0.051`), final DINOv2 `0.556` (gain `+0.089`)
- `prompt_modifier_search`: final CLIP `0.875` (gain `+0.046`), final DINOv2 `0.498` (gain `+0.031`)
- `stablesteering_best`: final CLIP `0.873` (gain `+0.044`), final DINOv2 `0.553` (gain `+0.086`)
- `prompt_best_of_budget`: final CLIP `0.873` (gain `+0.044`), final DINOv2 `0.602` (gain `+0.135`)

## Interpretation

- `prompt_best_of_budget` answers whether simple seed search under the same budget is sufficient.
- `prompt_modifier_search` is a direct but heuristic prompt-editing baseline: it rewrites the prompt through a fixed library of textual modifiers rather than through latent steering.
- `no_update_resampling` asks whether diversity alone is enough without state updates.
- `stablesteering_best` tests whether the current best loop uses the same budget more effectively.

This comparison is stronger than the earlier workflow pilot because all methods now consume the same visible candidate budget. It is still conservative: the prompt-rewrite arm is heuristic rather than a full language-model prompt optimizer.

Targets: `3`; repeats per target: `2`; total method runs: `24`.
