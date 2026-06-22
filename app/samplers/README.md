# Samplers Folder

This folder contains candidate proposal strategies.

## Files

- `base.py`
  Shared helper functions and common sampler behavior.

- `random_local.py`
  Baseline local sampler around the current steering state.

- `exploit_orthogonal.py`
  Mixes exploit-style movement with orthogonal exploration.

- `uncertainty.py`
  Uncertainty-guided proposal strategy.

- `__init__.py`
  Package marker.

## Role in the system

Samplers decide which candidate steering vectors are shown in the next round. They do not render images or update state.
