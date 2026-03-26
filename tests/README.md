# Tests Folder

This folder contains automated verification for backend behavior and browser flows.

## Files

- `conftest.py`
  Shared pytest fixtures, including the test-only mock generator and temporary storage setup.

- `test_feedback.py`
  Feedback normalization unit tests.

- `test_generation_engine.py`
  Generation backend selection, GPU policy, and mock-backend gating tests.

- `test_huggingface_setup.py`
  Tests for Hugging Face asset preparation helpers.

- `test_runtime_policy.py`
  Runtime startup policy tests, including GPU-only enforcement.

- `test_session_lifecycle.py`
  Integration tests for experiment/session lifecycle, feedback flow, replay export, and diagnostics.

- `test_tracing.py`
  Trace persistence tests for backend and frontend events.

- `e2e/`
  Playwright browser tests.

## Testing policy

Normal automated tests use the explicit test-only mock generator so logic can be validated without requiring real GPU generation on every run.
