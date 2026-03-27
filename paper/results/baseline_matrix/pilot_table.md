# Pilot Baseline Summary Table

| Policy | Runs | Completed | Avg. rounds/run | Avg. feedback/run |
|---|---:|---:|---:|---:|
| Prompt-only manual iteration | 9 | 9 | 1.0 | 0.0 |
| No-update random sampling | 9 | 9 | 1.0 | 0.0 |
| StableSteering default steering loop | 9 | 9 | 2.0 | 1.0 |

Caption:

Pilot workflow summary across prompt-only manual iteration, no-update random sampling, and the StableSteering default loop on a locked 3-prompt suite with three independent repeats per prompt-policy cell. The table shows a bounded workflow-comparison pilot with unequal interaction budgets, not a full benchmark.

Interpretation notes:

- `prompt_only_manual` is represented here as a one-round prompt-render proxy
- `no_update_random_sampling` is a no-feedback sampling control
- `stablesteering_default` is the only policy in the pilot that performs a feedback update and a follow-up round
- lightweight visual-check counts are intentionally omitted from this paper-facing table because they are weak artifact-screening heuristics, not human-quality scores
- for workflow-level repeatability, see `seed_robustness.md`
