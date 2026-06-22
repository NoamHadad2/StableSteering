# Engine Folder

This folder contains the main application logic.

## Files

- `generation.py`
  Generation backend selection and implementation. Includes the real Diffusers-backed generator, the test-only mock generator, image-size parsing, prepared-model resolution, and runtime diagnostics.

- `orchestrator.py`
  Coordinates experiment creation, session creation, round generation, feedback submission, replay export, lifecycle validation, and trace emission.

- `__init__.py`
  Package marker.

## Key idea

The engine layer keeps route handlers thin. API endpoints call into the orchestrator instead of implementing lifecycle rules directly.
