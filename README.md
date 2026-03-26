# StableSteering

StableSteering is a research documentation repository for an interactive system that studies prompt-embedding steering for text-to-image diffusion models.

The runtime app is now GPU-only by default and expects CUDA-backed Diffusers inference.

The current repository contains the specification set used to define the project before implementation:

- [Motivation](./docs/motivation.md)
- [Theoretical Background](./docs/theoretical_background.md)
- [System Specification](./docs/system_specification.md)
- [System Test Specification](./docs/system_test_specification.md)
- [Pre-Implementation Blueprint](./docs/pre_implementation_blueprint.md)
- [Documentation Audit Ledger](./docs/document_audit.md)
- [Quick Start](./docs/quick_start.md)
- [User Guide](./docs/user_guide.md)
- [Developer Guide](./docs/developer_guide.md)
- [FAQ](./docs/faq.md)

## Folder Guides

Per-folder documentation is available in:

- [app/README.md](./app/README.md)
- [app/bootstrap/README.md](./app/bootstrap/README.md)
- [app/core/README.md](./app/core/README.md)
- [app/engine/README.md](./app/engine/README.md)
- [app/feedback/README.md](./app/feedback/README.md)
- [app/frontend/README.md](./app/frontend/README.md)
- [app/frontend/templates/README.md](./app/frontend/templates/README.md)
- [app/frontend/static/README.md](./app/frontend/static/README.md)
- [app/samplers/README.md](./app/samplers/README.md)
- [app/storage/README.md](./app/storage/README.md)
- [app/updaters/README.md](./app/updaters/README.md)
- [tests/README.md](./tests/README.md)
- [tests/e2e/README.md](./tests/e2e/README.md)
- [scripts/README.md](./scripts/README.md)
- [docs/README.md](./docs/README.md)

## Repo Status

This repository now contains:

- the original research and specification documents
- a runnable FastAPI-based MVP
- a real GPU-backed Diffusers generation workflow
- a deterministic mock generation path reserved for tests
- rich backend logging and persisted trace events
- frontend trace capture and visible trace panels
- automated API, lifecycle, and browser tests including replay export smoke coverage

## Recommended Reading Order

1. [Motivation](./docs/motivation.md)
2. [Theoretical Background](./docs/theoretical_background.md)
3. [System Specification](./docs/system_specification.md)
4. [System Test Specification](./docs/system_test_specification.md)
5. [Pre-Implementation Blueprint](./docs/pre_implementation_blueprint.md)
6. [Quick Start](./docs/quick_start.md)

## Run Locally

```bash
python -m pip install -e .[dev]
python scripts/run_dev.py
```

Install real inference dependencies:

```bash
python -m pip install -e .[dev,inference]
```

Open:

```text
http://127.0.0.1:8000
```

Run tests:

```bash
python -m pytest
```

Run browser end-to-end tests in Chrome:

```bash
npm install
npm run test:e2e:chrome
```

Run a headed Chrome debug session:

```bash
npm run test:e2e:debug
```

Prepare Hugging Face assets for the real generator:

```bash
python scripts/setup_huggingface.py
```

Select the real Diffusers backend:

```bash
set STABLE_STEERING_GENERATION_BACKEND=diffusers
python scripts/run_dev.py
```

Real Diffusers inference is GPU-only. The app now targets `cuda` explicitly for
model runs and will fail fast if a CUDA-capable GPU is not available. The
default server runtime also enforces the `diffusers` backend and never falls
back to mock automatically. The mock generator is reserved for explicit test
harnesses only.

Trace logs are persisted under `data/traces/`.

Run a one-off real-model smoke test:

```bash
python scripts/smoke_real_diffusers.py
```

## Legacy Source

The original combined specification is preserved as:

- [Legacy Combined Spec](./docs/system_spec_legacy_combined.md)

## Next Suggested Steps

- add a diagnostics endpoint for backend, CUDA, and model readiness
- introduce a database-backed repository
- add schema versioning to replay exports
- expand browser coverage for pairwise and top-k feedback flows
