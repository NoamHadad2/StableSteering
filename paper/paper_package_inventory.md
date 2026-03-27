# Paper Package Inventory

This file lists the next reproducibility artifacts the paper package should describe or eventually add.

## Highest-priority missing package pieces

1. Repeated-seed robustness outputs for the baseline matrix
2. Analysis notebook or summary script for paper tables and figures
3. Broader baseline matrix beyond the minimal comparison

## Present package pieces

- `paper/protocols/minimal_baseline_prompt_suite.yaml`
- `paper/protocols/minimal_baseline_protocol.md`
- `paper/results/baseline_matrix/README.md`
- `paper/results/baseline_matrix/manifest.json`
- `paper/results/baseline_matrix/tables/`
- `scripts/run_paper_minimal_baseline_matrix.py`

## Proposed future files

- `paper/results/seed_robustness/`
- `paper/results/updater_ablation/`
- `paper/analysis/baseline_matrix_summary.ipynb`
- `scripts/run_paper_seed_robustness.py`
- `scripts/run_paper_updater_ablation.py`

## Scope note

The prompt suite, protocol bundle, executed minimal matrix, and runner now exist as concrete paper artifacts. The remaining missing links are robustness runs, analysis-ready summaries, and a broader comparison sweep.
