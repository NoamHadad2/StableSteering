from __future__ import annotations

from pathlib import Path

from app.core.schema import ExperimentCreate, SessionCreate, StrategyConfig
from app.engine.generation import build_generation_engine
from app.engine.orchestrator import Orchestrator
from app.storage.repository import JsonRepository


def main() -> int:
    """Run a minimal real-model smoke test through the orchestration layer."""

    root = Path("tmp_real_smoke")
    try:
        import torch
    except ImportError as exc:
        raise RuntimeError("PyTorch is required for the real Diffusers smoke test.") from exc

    if not torch.cuda.is_available():
        raise RuntimeError(
            "The real Diffusers smoke test requires a CUDA-capable GPU. "
            "Use the mock backend for CPU-only environments."
        )

    repository = JsonRepository(root / "data")
    generator = build_generation_engine(
        backend="diffusers",
        model_id="runwayml/stable-diffusion-v1-5",
        models_root=Path("models"),
        artifacts_dir=root / "data" / "artifacts",
    )
    orchestrator = Orchestrator(repository=repository, generator=generator)
    experiment = orchestrator.create_experiment(
        ExperimentCreate(
            name="Real model smoke",
            description="single-candidate real backend smoke test",
            config=StrategyConfig(
                candidate_count=1,
                image_size="256x256",
                sampler="random_local",
                updater="winner_average",
                model_name="runwayml/stable-diffusion-v1-5",
            ),
        )
    )
    session = orchestrator.create_session(
        SessionCreate(
            experiment_id=experiment.id,
            prompt="A studio portrait of a futuristic silver motorcycle",
            negative_prompt="blurry, distorted",
        )
    )
    round_response = orchestrator.generate_round(session.id)
    image_name = Path(round_response.image_urls[0]).name
    artifact_path = root / "data" / "artifacts" / image_name
    print("Real Diffusers smoke test completed:")
    print(f"  round_id: {round_response.round_id}")
    print(f"  image_url: {round_response.image_urls[0]}")
    print(f"  artifact_path: {artifact_path}")
    print(f"  artifact_exists: {artifact_path.exists()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
