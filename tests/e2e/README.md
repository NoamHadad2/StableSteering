# E2E Tests Folder

This folder contains Playwright browser tests.

## Files

- `app.spec.js`
  Browser smoke coverage for:
  - session creation through the UI
  - round generation and feedback submission
  - replay page navigation
  - replay export API retrieval
  - diagnostics page visibility

- `real_backend.spec.js`
  Opt-in browser smoke coverage for the real Diffusers runtime. This is intended for CUDA-capable environments with a prepared local model snapshot.

## How it runs

The Playwright configuration starts the app with the explicit test-only mock backend so browser flows stay fast and deterministic.

For a real-backend browser smoke run:

- prepare the local model snapshot first
- ensure CUDA-backed inference works on the machine
- set `STABLE_STEERING_E2E_REAL=true`
- run `npm run test:e2e:real`
