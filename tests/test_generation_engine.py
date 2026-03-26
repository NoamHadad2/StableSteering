from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

from app.core.config import settings
from app.engine.generation import DiffusersGenerationEngine, MockGenerationEngine, build_generation_engine, parse_image_size, resolve_prepared_model_path


def test_parse_image_size_parses_dimensions() -> None:
    assert parse_image_size("512x768") == (512, 768)


def test_parse_image_size_rejects_invalid_values() -> None:
    with pytest.raises(ValueError):
        parse_image_size("oops")


def test_mock_backend_is_rejected_without_test_opt_in(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(settings, "allow_test_mock_backend", False)
    with pytest.raises(RuntimeError, match="reserved for tests"):
        build_generation_engine(
            backend="mock",
            artifacts_dir=tmp_path / "artifacts",
        )


def test_mock_backend_is_available_with_explicit_test_opt_in(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(settings, "allow_test_mock_backend", True)
    engine = build_generation_engine(
        backend="mock",
        artifacts_dir=tmp_path / "artifacts",
    )
    assert isinstance(engine, MockGenerationEngine)


def test_auto_backend_refuses_when_model_is_missing(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError, match="Prepared model not found"):
        build_generation_engine(
            backend="auto",
            model_id="runwayml/stable-diffusion-v1-5",
            models_root=tmp_path / "models",
            artifacts_dir=tmp_path / "artifacts",
        )


def test_diffusers_backend_requires_prepared_model_when_remote_download_disabled(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(settings, "allow_remote_model_download", False)
    with pytest.raises(FileNotFoundError):
        build_generation_engine(
            backend="diffusers",
            model_id="runwayml/stable-diffusion-v1-5",
            models_root=tmp_path / "models",
            artifacts_dir=tmp_path / "artifacts",
        )


def test_resolve_prepared_model_path_uses_slugged_model_directory(tmp_path: Path) -> None:
    path = resolve_prepared_model_path("runwayml/stable-diffusion-v1-5", tmp_path)
    assert path == tmp_path / "runwayml--stable-diffusion-v1-5"


def test_diffusers_engine_requires_cuda_when_gpu_is_mandatory(tmp_path: Path) -> None:
    engine = DiffusersGenerationEngine(
        model_source=str(tmp_path / "model"),
        artifacts_dir=tmp_path / "artifacts",
        device="cuda",
        require_gpu=True,
    )

    with pytest.raises(RuntimeError, match="CUDA-capable GPU"):
        engine._resolve_device(SimpleNamespace(cuda=SimpleNamespace(is_available=lambda: False)))


def test_auto_backend_uses_diffusers_engine_when_model_exists(tmp_path: Path) -> None:
    prepared = tmp_path / "models" / "runwayml--stable-diffusion-v1-5"
    prepared.mkdir(parents=True)

    engine = build_generation_engine(
        backend="auto",
        model_id="runwayml/stable-diffusion-v1-5",
        models_root=tmp_path / "models",
        artifacts_dir=tmp_path / "artifacts",
    )
    assert isinstance(engine, DiffusersGenerationEngine)
