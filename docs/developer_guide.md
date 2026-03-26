# Developer Guide

## 1. Purpose

This guide explains how the current StableSteering prototype is organized, how to run it locally, and how to extend it safely.

It is intended for developers who want to:

- run the app locally
- understand the code layout
- add new samplers or updaters
- change storage or generation behavior
- maintain test coverage while evolving the system

For a student-oriented conceptual walkthrough, start with [student_tutorial.md](E:\Projects\StableSteering\docs\student_tutorial.md).

## 2. Current Implementation Scope

The current implementation is a minimal research MVP with:

- a FastAPI backend
- a simple HTML/CSS/JS frontend
- SQLite-backed local persistence
- a GPU-only real Diffusers runtime by default
- deterministic mock SVG generation for tests only
- basic replay export
- asynchronous round-generation and feedback jobs with visible progress status
- rich backend logging and persisted trace events
- per-session HTML trace reports saved by the backend
- frontend trace capture and visible trace panels
- automated tests for feedback, lifecycle, tracing, and replay export
- a reusable real GPU-backed example-run generator for demos and teaching

It does not yet include:

- shared multi-user persistence beyond the local SQLite repository
- authentication
- multi-user coordination

## 3. Project Structure

Key directories:

- [app](E:\Projects\StableSteering\app)
  Main application code.

- [app/core](E:\Projects\StableSteering\app\core)
  Shared settings and Pydantic schemas.

- [app/engine](E:\Projects\StableSteering\app\engine)
  Generation and orchestration logic.

- [app/storage](E:\Projects\StableSteering\app\storage)
  SQLite repository implementation.

- [app/samplers](E:\Projects\StableSteering\app\samplers)
  Candidate proposal strategies.

- [app/updaters](E:\Projects\StableSteering\app\updaters)
  Steering-state update strategies.

- [app/feedback](E:\Projects\StableSteering\app\feedback)
  Feedback normalization logic.

- [app/frontend](E:\Projects\StableSteering\app\frontend)
  Jinja templates and static frontend assets.

- [tests](E:\Projects\StableSteering\tests)
  Automated tests.

- [scripts](E:\Projects\StableSteering\scripts)
  Convenience scripts such as the local dev launcher.

## 4. Local Development Setup

Install the project with development dependencies:

```bash
python -m pip install -e .[dev]
```

Install inference dependencies for the real Diffusers backend:

```bash
python -m pip install -e .[dev,inference]
```

Run the local server:

```bash
python scripts/run_dev.py
```

To prefer the real Diffusers backend after preparing model assets:

```bash
set STABLE_STEERING_GENERATION_BACKEND=diffusers
python scripts/run_dev.py
```

The real Diffusers path is GPU-only and explicitly targets `cuda`. The default
server runtime now requires that path and should fail fast when a CUDA-capable
GPU is not available.

Run the standalone real-model smoke test:

```bash
python scripts/smoke_real_diffusers.py
```

Generate the full example walkthrough bundle:

```bash
python scripts/create_real_e2e_example.py
```

Open:

```text
http://127.0.0.1:8000
```

Run the tests:

```bash
python -m pytest
```

Run browser tests:

```bash
npm install
npm run test:e2e:chrome
```

Run a headed single-worker debug session in Chrome:

```bash
npm run test:e2e:debug
```

Prepare Hugging Face assets:

```bash
python scripts/setup_huggingface.py
```

Inspect persisted trace files:

```text
data/traces/
```

Per-session run bundles live under:

```text
data/traces/sessions/<session_id>/
```

That bundle includes:

- `backend-events.jsonl`
- `frontend-events.jsonl`
- `report.html`

## 5. Runtime Flow

The current runtime flow is:

1. create an experiment
2. create a session from that experiment
3. request the next round
4. sampler proposes candidates
5. Diffusers renders candidate images on GPU
6. frontend displays the candidate images
7. frontend starts async jobs for round generation and feedback submission
8. users see progress and status while the job runs
9. frontend and backend trace the active flow
10. feedback is normalized and validated against the round
11. updater computes the next incumbent state
12. replay export exposes the persisted trajectory
13. the backend refreshes the saved HTML trace report for the session

When a prepared local model is available and the backend is set to `diffusers`,
the generation step uses a real Stable Diffusion pipeline, pins inference to
GPU, and applies a deterministic steering offset to `prompt_embeds` before
rendering. If the model or GPU requirements are not satisfied, startup fails.

## 5.1 Async API Endpoints

Long-running session actions are exposed as asynchronous job endpoints:

- `POST /sessions/{session_id}/rounds/next/async`
  Queues next-round generation and returns a job handle.

- `POST /rounds/{round_id}/feedback/async`
  Queues feedback application and returns a job handle.

- `GET /jobs/{job_id}`
  Returns the current job snapshot.

The async `POST` routes return:

- `job_id`
- `status_url`
- initial `state`

The job status payload includes:

- `state`
- `progress`
- `status_message`
- `result` when complete
- `error` when failed

Current job states are:

- `queued`
- `running`
- `succeeded`
- `failed`

## 5.2 Progress Behavior

The browser session view uses the async endpoints by default.

During round generation and feedback submission:

- the clicked action button is disabled
- a visible progress panel is shown
- the page polls `GET /jobs/{job_id}`
- `status_message` is rendered as human-readable progress text
- `progress` updates the progress bar
- the page refreshes automatically after success
- errors are shown inline if the job fails

This keeps the UI responsive while the real GPU-backed backend works in the background.

## 6. Core Extension Points

### 6.1 Add a sampler

To add a sampler:

1. create a new module under [app/samplers](E:\Projects\StableSteering\app\samplers)
2. implement `propose(session, seed) -> list[Candidate]`
3. register the sampler in [orchestrator.py](E:\Projects\StableSteering\app\engine\orchestrator.py)
4. add tests for deterministic behavior and output shape

### 6.2 Add an updater

To add an updater:

1. create a new module under [app/updaters](E:\Projects\StableSteering\app\updaters)
2. implement `update(session, candidates, feedback) -> (next_z, summary)`
3. register the updater in [orchestrator.py](E:\Projects\StableSteering\app\engine\orchestrator.py)
4. add tests for update behavior and edge cases

### 6.3 Evolve generation

To evolve the generation backend further:

1. keep the same high-level contract as [MockGenerationEngine](E:\Projects\StableSteering\app\engine\generation.py)
2. preserve deterministic testability by keeping the mock path available only in tests
3. avoid letting generation concerns leak into API routes
4. keep artifact paths stable enough for replay

Before running or extending the real generator, stage a compatible model snapshot locally with:

```bash
python scripts/setup_huggingface.py --model-id runwayml/stable-diffusion-v1-5 --output-root models
```

The setup script downloads the expected diffusers module directories and writes a local manifest so the prepared snapshot is easier to inspect and reuse.

The runtime contract is:

- `diffusers` means "use the real model on GPU"
- the default app runtime enforces `diffusers`
- runtime code never falls back to `mock`
- `mock` remains available only for explicitly constructed test harnesses that set `STABLE_STEERING_ALLOW_TEST_MOCK_BACKEND=true`

The current browser test contract is:

- `npm run test:e2e:chrome` covers the UI flow and replay export API smoke path
- `npm run test:e2e:debug` runs the same suite headed for interactive debugging
- `npm run test:e2e:real` provides an opt-in real-backend browser smoke path for CUDA-capable environments with prepared model assets

The current API quality contract is:

- JSON API errors use the structured `ApiError` payload shape
- replay exports include explicit schema and app versions
- long-running session actions are exposed as async jobs with pollable status
- session trace reports are backend-owned artifacts, not frontend-only console output

The current roadmap also includes expanding steering support beyond prompt-only generation into:

- image-prompt or image-variation workflows
- inpainting workflows
- ControlNet-guided workflows

### 6.4 Evolve persistence

To move from SQLite to PostgreSQL or another shared store:

1. keep repository method names stable
2. preserve session and round ordering
3. preserve replay export shape
4. add migration-safe tests before swapping implementations

## 7. Coding Conventions for This Project

- prefer small, focused modules
- keep orchestration logic out of route handlers
- keep feedback normalization separate from update logic
- keep persistence inspectable and replay-friendly
- preserve deterministic behavior in tests
- add docstrings when adding new services or public models

## 8. Testing Expectations

Before merging meaningful behavior changes:

- run `python -m pytest`
- run `npm run test:e2e:chrome` for UI-impacting changes
- use `npm run test:e2e:debug` when you need to watch the browser flow interactively
- use `npm run test:e2e:real` when you need browser validation against the real Diffusers backend
- add or update at least one relevant test when changing lifecycle behavior
- preserve replay export compatibility where possible
- keep the explicitly injected mock test path working even if the runtime stays GPU-only
- keep tracing outputs stable enough for debugging and auditability
- keep `report.html` readable when changing trace payload shapes

## 9. Common Development Tasks

### Start fresh local data

Delete the local data directory if you want a clean environment:

```text
data/
```

### Inspect persisted state

Look in:

```text
data/stablesteering.db
data/artifacts/
data/traces/
```

Open the readable report for one session:

```text
/sessions/{session_id}/trace-report
```

### Validate the browser flow

Minimal manual smoke test:

1. open `/setup`
2. create an experiment
3. open the session page
4. generate a round
5. submit ratings
6. open replay

## 10. Recommended Next Engineering Steps

- add export packaging for session trace bundles
- add richer end-to-end browser tests
