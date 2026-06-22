# Updaters Folder

This folder contains steering-state update strategies.

## Files

- `base.py`
  Shared update helpers and common behavior.

- `winner_copy.py`
  Copies the winning candidate state directly.

- `winner_average.py`
  Moves the incumbent toward the winning candidate by averaging.

- `linear_pref.py`
  Applies a stronger linear move toward the selected winner.

- `__init__.py`
  Package marker.

## Role in the system

Updaters consume normalized feedback and decide how the incumbent steering vector changes after each round.
