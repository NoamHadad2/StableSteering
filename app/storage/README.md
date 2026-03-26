# Storage Folder

This folder contains persistence code.

## Files

- `repository.py`
  JSON-backed repository for experiments, sessions, rounds, and trace-related directories. It creates the storage layout and loads/saves persisted state.

- `__init__.py`
  Package marker.

## Storage layout

The repository writes to subdirectories under `data/`, including:

- `experiments/`
- `sessions/`
- `rounds/`
- `artifacts/`
- `traces/`
