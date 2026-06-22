# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
# Install
python -m pip install -e .[dev,inference]

# Download model weights (runwayml/stable-diffusion-v1-5 into models/hf_cache/)
python scripts/setup_huggingface.py

# Run the dev server (GPU required by default)
python scripts/run_dev.py

# Backend tests (uses mock generator, no GPU needed)
python -m pytest

# Run a single test file
python -m pytest tests/test_feedback.py

# Browser (Playwright) tests — requires npm install first
npm install
npm run test:e2e:chrome

# Headed debug mode for browser tests
npm run test:e2e:debug

# Real GPU smoke test
python scripts/smoke_real_diffusers.py
```

## Architecture

StableSteering is a FastAPI app for iterative preference-guided image generation. The core loop: user submits a text prompt → candidates are generated via Stable Diffusion → user provides feedback → steering state (an embedding vector) is updated → next round of candidates is generated from the updated state.

**Key layers:**

- `app/main.py` — FastAPI app, all routes, Jinja2 template helpers. Two async routes (`/rounds/next/async`, `/feedback/async`) return job handles; synchronous variants exist for tests.
- `app/engine/orchestrator.py` — Central coordinator: manages experiments, sessions, rounds. Owns the `JsonRepository` for persistence and selects samplers/updaters based on session config.
- `app/engine/generation.py` — `GenerationEngine` interface with a real Diffusers backend and a mock backend for tests. `build_generation_engine()` reads `settings.generation_backend`.
- `app/core/config.py` — `Settings` via pydantic-settings with `STABLE_STEERING_` env prefix. Key flags: `enforce_gpu_runtime` (default `True`), `allow_test_mock_backend` (default `False`), `generation_backend` (default `"diffusers"`).
- `app/core/schema.py` — All Pydantic models: `Experiment`, `Session`, `Round`, `Candidate`, `FeedbackRequest`, etc.
- `app/samplers/` — One file per sampler strategy (e.g. `line_search.py`, `spherical_cover.py`). Each extends `base.py`. Samplers propose the next set of steering vectors.
- `app/updaters/` — One file per preference model (e.g. `bradley_terry_pref.py`, `softmax_pref.py`). Each extends `base.py`. Updaters shift the steering vector based on user feedback.
- `app/storage/repository.py` — `JsonRepository`: SQLite-free JSON file persistence under `data/`. Stores experiments, sessions, rounds, candidates.
- `app/core/tracing.py` — `TraceRecorder` collects backend and frontend events; generates per-session HTML trace reports.
- `app/core/jobs.py` — `AsyncJobManager` runs blocking generation/feedback calls in a thread pool and tracks job state.
- `app/feedback/normalization.py` — Normalizes the five feedback modes (`scalar_rating`, `pairwise`, `top_k`, `winner_only`, `approve_reject`) into a uniform format before updaters process them.
- `app/frontend/templates/` — Jinja2 HTML templates (`index.html`, `setup.html`, `session.html`, `replay.html`, `diagnostics.html`).

**Test setup:** Tests inject a mock orchestrator and trace recorder into `app.state` before the lifespan starts (see `tests/conftest.py`). The GPU runtime guard is bypassed by setting `STABLE_STEERING_ALLOW_TEST_MOCK_BACKEND=true` and `STABLE_STEERING_ENFORCE_GPU_RUNTIME=false`.

**Configuration:** Per-session strategy config is a YAML block edited on `/setup`. `app/core/config_yaml.py` handles parsing and rendering. Global runtime settings come from env vars or `.env`.

**Scripts:** `scripts/` contains paper experiment runners (`run_paper_*.py`), figure builders (`build_*.py`), and the dev server launcher (`run_dev.py`). Paper assets land in `output/`.
