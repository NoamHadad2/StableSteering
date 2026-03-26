from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.core.tracing import TraceRecorder
from app.core.schema import StrategyConfig
from app.engine.generation import MockGenerationEngine
from app.engine.orchestrator import Orchestrator
from app.main import app
from app.storage.repository import JsonRepository


@pytest.fixture()
def client(tmp_path: Path) -> TestClient:
    repository = JsonRepository(tmp_path / "data")
    generator = MockGenerationEngine((tmp_path / "data" / "artifacts"))
    trace_recorder = TraceRecorder(tmp_path / "data" / "traces")
    app.state.trace_recorder = trace_recorder
    app.state.orchestrator = Orchestrator(repository=repository, generator=generator, trace_recorder=trace_recorder)
    return TestClient(app)


@pytest.fixture()
def strategy_config() -> dict:
    return StrategyConfig().model_dump(mode="json")
