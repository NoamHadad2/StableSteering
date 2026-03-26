# FAQ

## What is StableSteering?

StableSteering is a research prototype for studying interactive prompt-embedding steering in text-to-image systems.

If you want the easiest conceptual introduction, start with [student_tutorial.md](student_tutorial.md).

## Does it generate real AI images yet?

Yes, if you install the inference dependencies, prepare a local model snapshot, and run with the Diffusers backend enabled.

The real Diffusers path is GPU-only and explicitly requires CUDA. If a GPU is
not available, the default app server does not start. It never falls back to
mock automatically, and the mock generator is reserved for tests only.

## Why keep a mock generator at all?

Mock renders make the core system easier to implement, debug, and test. They let us validate:

- session creation
- round generation
- feedback submission
- update logic
- replay export

without requiring real image generation in every automated test.

## What is the normal runtime path?

The normal app runtime uses the real Diffusers backend on GPU. The mock generator exists only for explicit test harnesses.

## Does the user flow start from a text prompt?

Yes.

The normal workflow begins on `/setup`, where the user enters a text prompt and then starts a session from that prompt.

## Is there a setup script for Hugging Face models?

Yes.

Run:

```bash
python scripts/setup_huggingface.py
```

This prepares a local model snapshot directory and writes a manifest describing what was downloaded.

## Where is the session data stored?

The current MVP stores structured state in a local SQLite database:

```text
data/stablesteering.db
```

Generated images, trace logs, and per-session reports are stored alongside it under `data/`.

## Where are the generated artifacts stored?

The current generated artifacts are stored under:

```text
data/artifacts/
```

## Where are trace logs stored?

Trace files are stored under:

```text
data/traces/
```

Per-session trace bundles are stored under:

```text
data/traces/sessions/<session_id>/
```

Each session bundle contains:

- `backend-events.jsonl`
- `frontend-events.jsonl`
- `report.html`

## How do async actions work?

Round generation and feedback submission run as async jobs.

In the browser, you will see:

- a progress bar
- a status label
- automatic refresh after success
- inline error text if the job fails

Behind the scenes, the UI submits async requests and polls a job-status endpoint until the work completes.

## Is there a real end-to-end example run?

Yes.

Run:

```bash
python scripts/create_real_e2e_example.py
```

This creates a real GPU-backed example bundle under:

```text
output/examples/real_e2e_example_run/
```

That bundle includes generated images, a manifest, a standalone walkthrough HTML file, and the session trace report.

## What feedback modes are supported?

The schema supports:

- scalar rating
- pairwise comparison
- top-k ranking

The current UI uses rating inputs for all supported modes and derives the final payload from the selected feedback mode.

## Are other diffusion workflows in scope?

Yes, on the roadmap.

The current implementation focuses on prompt-first text-to-image steering, but the roadmaps now also include:

- image-prompt or image-variation steering
- inpainting steering
- ControlNet-guided steering

## What samplers are implemented?

The current MVP includes:

- `random_local`
- `exploit_orthogonal`
- `uncertainty_guided`

## What updaters are implemented?

The current MVP includes:

- `winner_copy`
- `winner_average`
- `linear_preference`

## Is the system deterministic?

The mock-generation path is deterministic for the same session state and seed logic, which is useful for tests and replay. Real generation still persists seeds and configuration for auditability, but exact image-level determinism depends on the runtime stack and model behavior.

## How do I run it?

Install dependencies:

```bash
python -m pip install -e .[dev]
```

Start the app:

```bash
python scripts/run_dev.py
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

## Is this production-ready?

No. It is a research-oriented MVP intended to exercise the architecture described in the specification set.
