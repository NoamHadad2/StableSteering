# Release Notes v0.1.0

Initial runnable MVP release of StableSteering.

Published HTML documentation:

- [GitHub Pages Docs](https://apartsinprojects.github.io/StableSteering/)

## Highlights

- FastAPI backend for experiments, sessions, rounds, feedback, replay, diagnostics, and async job status
- real Diffusers-backed GPU runtime by default
- explicit test-only mock backend
- browser UI for setup, interactive sessions, replay, diagnostics, and trace visibility
- rich backend logging and persisted frontend/backend trace events
- async round generation and feedback submission with visible progress indicators
- per-session HTML trace reports saved by the backend
- replay exports with schema and app version metadata
- Playwright browser coverage, including replay export smoke and diagnostics checks
- opt-in real-backend browser smoke path for CUDA-capable environments
- reusable real GPU-backed end-to-end example bundle generation

## Included Documentation

- [README.md](E:\Projects\StableSteering\README.md)
- [INSTALL.md](E:\Projects\StableSteering\INSTALL.md)
- [RELEASE.md](E:\Projects\StableSteering\RELEASE.md)
- [quick_start.md](E:\Projects\StableSteering\docs\quick_start.md)
- [developer_guide.md](E:\Projects\StableSteering\docs\developer_guide.md)
- [user_guide.md](E:\Projects\StableSteering\docs\user_guide.md)

## Validation Snapshot

- `python -m pytest`
- `npm run test:e2e:chrome`

## Notes

- The normal runtime requires a CUDA-capable GPU.
- The mock generator is available only for tests and explicit test harnesses.
- This is a research MVP, not a production release.
