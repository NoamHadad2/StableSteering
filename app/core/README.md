# Core Folder

This folder contains shared runtime primitives used across the app.

## Files

- `config.py`
  Central settings model. Defines data directories, backend selection, GPU/runtime policy, Hugging Face model defaults, and trace paths.

- `schema.py`
  Pydantic data models for experiments, sessions, rounds, candidates, feedback, replay, and API payloads.

- `logging.py`
  Rich-backed backend logging setup with request-id support.

- `tracing.py`
  Trace recorder that persists backend and frontend events into JSONL-style files under `data/traces/`.

- `__init__.py`
  Package marker.

## Why it matters

Most modules import from `core/`. If a behavior feels global, it is probably defined here.
