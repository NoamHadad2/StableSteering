# Budget-Matched Direct Baseline Comparison

This bundle compares prompt-only seed search, heuristic prompt rewriting, no-update resampling, and StableSteering under the same candidate budget.

Primary outputs:

- `tables/policy_summary.csv`
- `analysis/analysis_summary.md`
- `figures/budget_matched_direct_baselines_curve.svg`
- `figures/budget_matched_direct_baselines_examples.png`

The comparison is direct and budget-matched, but still conservative: the prompt-rewrite arm is heuristic rather than a full language-model prompt optimizer.
