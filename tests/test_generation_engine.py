from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

from app.core.config import settings
from app.core.schema import Candidate, StrategyConfig, Session
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


def test_mock_render_uses_session_generation_config(tmp_path: Path) -> None:
    engine = MockGenerationEngine(tmp_path / "artifacts")
    session = Session(
        experiment_id="exp_test",
        prompt="A configurable test prompt",
        negative_prompt="blurry",
        model_name="custom/model",
        config=StrategyConfig(
            image_size="320x640",
            anchor_strength=0.8,
            guidance_scale=9.5,
            num_inference_steps=28,
            model_name="custom/model",
        ),
    )
    candidate = Candidate(
        round_id="rnd_test",
        candidate_index=0,
        z=[0.1, 0.2, -0.1],
        sampler_role="baseline_prompt",
        seed=123,
        generation_params={},
    )

    rendered = engine.render_candidate(session, candidate)
    svg_path = tmp_path / "artifacts" / f"{candidate.id}.svg"
    svg = svg_path.read_text(encoding="utf-8")

    assert rendered.generation_params["image_size"] == "320x640"
    assert rendered.generation_params["guidance_scale"] == 9.5
    assert rendered.generation_params["num_inference_steps"] == 28
    assert rendered.generation_params["anchor_strength"] == 0.8
    assert rendered.generation_params["model_source"] == "custom/model"
    assert 'width="320"' in svg
    assert 'height="640"' in svg
    assert "CFG: 9.50" in svg
    assert "Steps: 28" in svg
    assert "Anchor strength: 0.80" in svg


def test_diffusers_engine_resolves_per_session_model_name(tmp_path: Path) -> None:
    prepared = tmp_path / "models" / "custom--model"
    prepared.mkdir(parents=True)
    original_models_dir = settings.models_dir
    settings.models_dir = tmp_path / "models"
    engine = DiffusersGenerationEngine(
        model_source=str(tmp_path / "models" / "runwayml--stable-diffusion-v1-5"),
        artifacts_dir=tmp_path / "artifacts",
        device="cuda",
        require_gpu=True,
    )
    session = Session(
        experiment_id="exp_test",
        prompt="A model resolution test",
        model_name="custom/model",
        config=StrategyConfig(model_name="custom/model"),
    )

    try:
        resolved = engine._resolve_model_source(session)
        assert resolved == str(prepared)
    finally:
        settings.models_dir = original_models_dir


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
