from __future__ import annotations

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings shared by runtime code and tests."""

    app_name: str = "StableSteering"
    app_version: str = "0.1.0"
    environment: str = "development"
    data_dir: Path = Path("data")
    artifacts_dir_name: str = "artifacts"
    models_dir: Path = Path("models")
    traces_dir_name: str = "traces"
    default_candidate_count: int = 4
    default_image_size: str = "512x512"
    generation_backend: str = "diffusers"
    enforce_gpu_runtime: bool = True
    allow_test_mock_backend: bool = False
    inference_device: str = "cuda"
    huggingface_model_id: str = "runwayml/stable-diffusion-v1-5"
    allow_remote_model_download: bool = False
    diffusion_num_inference_steps: int = 15

    model_config = SettingsConfigDict(
        env_prefix="STABLE_STEERING_",
        env_file=".env",
        extra="ignore",
    )

    @property
    def artifacts_dir(self) -> Path:
        """Return the directory used for generated render artifacts."""

        return self.data_dir / self.artifacts_dir_name

    @property
    def traces_dir(self) -> Path:
        """Return the directory used for persisted trace and event logs."""

        return self.data_dir / self.traces_dir_name


settings = Settings()
