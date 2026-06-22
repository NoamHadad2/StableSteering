from __future__ import annotations

from fastapi import FastAPI
import pytest

from app.main import initialize_app_state


def test_initialize_app_state_rejects_non_diffusers_backend_when_gpu_runtime_is_enforced(monkeypatch) -> None:
    application = FastAPI()
    monkeypatch.setattr("app.main.settings.enforce_gpu_runtime", True)
    monkeypatch.setattr("app.main.settings.generation_backend", "mock")

    with pytest.raises(RuntimeError, match="GPU-backed Diffusers inference"):
        initialize_app_state(application)


def test_initialize_app_state_skips_runtime_build_when_tests_inject_services(monkeypatch) -> None:
    application = FastAPI()
    application.state.trace_recorder = object()
    application.state.orchestrator = object()
    monkeypatch.setattr("app.main.settings.enforce_gpu_runtime", True)
    monkeypatch.setattr("app.main.settings.generation_backend", "mock")

    initialize_app_state(application)
