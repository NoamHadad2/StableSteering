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

## How it runs

The Playwright configuration starts the app with the explicit test-only mock backend so browser flows stay fast and deterministic.
