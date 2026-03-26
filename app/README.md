# App Folder

This folder contains the running StableSteering application.

## Structure

- `main.py`
  FastAPI entry point. Builds app state, exposes HTML pages and JSON APIs, accepts frontend trace events, serves runtime diagnostics, and renders saved session trace reports.

- `frontend_trace.py`
  Shared schema for browser-submitted trace events.

- `bootstrap/`
  Startup and model-preparation helpers.

- `core/`
  Shared configuration, schemas, logging, and tracing utilities.

- `engine/`
  The orchestration and image-generation layer.

- `feedback/`
  Feedback normalization logic.

- `frontend/`
  HTML templates and static browser assets.

- `samplers/`
  Candidate proposal strategies.

- `storage/`
  Local SQLite persistence plus artifact/trace directories.

- `updaters/`
  Steering-state update strategies.

## Runtime flow

1. `main.py` creates the FastAPI app and runtime services.
2. `frontend/` renders the prompt-first setup page, including the editable per-session YAML block.
3. `engine/orchestrator.py` coordinates experiment, session, round, baseline or incumbent carry-forward, and feedback lifecycle.
4. `engine/generation.py` resolves the active generation backend and applies the per-session generation settings.
5. `storage/repository.py` persists experiments, sessions, rounds, artifacts, and trace data references.
6. `frontend/` submits async jobs, shows progress, and posts browser events back to the backend.
