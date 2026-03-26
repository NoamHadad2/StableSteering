# Storage Folder

This folder contains persistence code.

## Files

- `repository.py`
  SQLite-backed repository for experiments, sessions, and rounds. It also creates the local artifact and trace directories used by the rest of the app.

- `__init__.py`
  Package marker.

## Storage layout

The repository uses `data/stablesteering.db` for structured state and also manages filesystem directories under `data/`, including:

- `artifacts/`
- `traces/`
