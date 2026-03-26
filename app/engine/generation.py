from __future__ import annotations

from html import escape
from pathlib import Path
from typing import Protocol

from app.bootstrap.huggingface import model_slug
from app.core.config import settings
from app.core.schema import Candidate, Session


def _color_from_candidate(candidate: Candidate) -> tuple[str, str]:
    """Derive stable mock-render colors from the steering vector."""

    a = int(abs(candidate.z[0]) * 255) % 255
    b = int(abs(candidate.z[1]) * 255) % 255
    c = int(abs(candidate.z[2]) * 255) % 255
    primary = f"rgb({a}, {b}, {c})"
    secondary = f"rgb({255 - a}, {255 - b}, {255 - c})"
    return primary, secondary


def parse_image_size(value: str) -> tuple[int, int]:
    """Parse a `WIDTHxHEIGHT` image size string."""

    try:
        width_str, height_str = value.lower().split("x", maxsplit=1)
        return int(width_str), int(height_str)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"Invalid image size: {value!r}. Expected format WIDTHxHEIGHT.") from exc


class GenerationEngine(Protocol):
    """Protocol shared by generation backends used by the orchestrator."""

    def render_candidate(self, session: Session, candidate: Candidate) -> Candidate:
        """Render a candidate and attach its public artifact path."""

    def diagnostics(self) -> dict:
        """Return runtime diagnostics for the configured generation backend."""


class MockGenerationEngine:
    """Deterministic render engine used strictly for tests.

    Instead of invoking a real diffusion backend, this engine writes a small
    SVG artifact that exposes the prompt, seed, role, and steering vector.
    That keeps the full session lifecycle testable without a GPU dependency.
    """

    def __init__(self, artifacts_dir: Path | None = None) -> None:
        self.artifacts_dir = artifacts_dir or settings.artifacts_dir
        self.artifacts_dir.mkdir(parents=True, exist_ok=True)

    def render_candidate(self, session: Session, candidate: Candidate) -> Candidate:
        """Render one candidate to an SVG artifact and attach its public path."""

        primary, secondary = _color_from_candidate(candidate)
        width, height = parse_image_size(session.config.image_size)
        path = self.artifacts_dir / f"{candidate.id}.svg"
        svg = f"""<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}">
<defs>
  <linearGradient id="bg" x1="0%" y1="0%" x2="100%" y2="100%">
    <stop offset="0%" stop-color="{primary}" />
    <stop offset="100%" stop-color="{secondary}" />
  </linearGradient>
</defs>
<rect width="100%" height="100%" fill="url(#bg)" />
<rect x="24" y="24" width="{max(width - 48, 0)}" height="{max(height - 48, 0)}" rx="18" fill="rgba(255,255,255,0.14)" stroke="white" stroke-opacity="0.35" />
<text x="40" y="70" fill="white" font-size="28" font-family="Arial">StableSteering Mock Render</text>
<text x="40" y="120" fill="white" font-size="18" font-family="Arial">Prompt: {escape(session.prompt[:50])}</text>
<text x="40" y="155" fill="white" font-size="18" font-family="Arial">Candidate: {escape(candidate.id)}</text>
<text x="40" y="190" fill="white" font-size="18" font-family="Arial">Role: {escape(candidate.sampler_role)}</text>
<text x="40" y="225" fill="white" font-size="18" font-family="Arial">Seed: {candidate.seed}</text>
<text x="40" y="260" fill="white" font-size="18" font-family="Arial">z: {escape(', '.join(f'{v:.3f}' for v in candidate.z))}</text>
<text x="40" y="295" fill="white" font-size="18" font-family="Arial">Model: {escape(session.config.model_name)}</text>
<text x="40" y="330" fill="white" font-size="18" font-family="Arial">CFG: {session.config.guidance_scale:.2f}</text>
<text x="40" y="365" fill="white" font-size="18" font-family="Arial">Steps: {session.config.num_inference_steps}</text>
<text x="40" y="400" fill="white" font-size="18" font-family="Arial">Anchor strength: {session.config.anchor_strength:.2f}</text>
</svg>"""
        path.write_text(svg, encoding="utf-8")
        candidate.image_path = f"/artifacts/{path.name}"
        candidate.generation_params.update(
            {
                "backend": "mock",
                "image_size": session.config.image_size,
                "guidance_scale": session.config.guidance_scale,
                "num_inference_steps": session.config.num_inference_steps,
                "model_source": session.config.model_name,
                "anchor_strength": session.config.anchor_strength,
            }
        )
        return candidate

    def diagnostics(self) -> dict:
        """Return lightweight diagnostics for the test-only mock engine."""

        cuda_available = False
        try:
            import torch

            cuda_available = bool(torch.cuda.is_available())
        except ImportError:
            cuda_available = False

        return {
            "backend": "mock",
            "model_source": None,
            "configured_device": None,
            "active_device": None,
            "pipeline_loaded": False,
            "cuda_available": cuda_available,
            "local_files_only": True,
            "test_only_backend": True,
        }


class DiffusersGenerationEngine:
    """Lazy-loaded Diffusers backend that steers prompt embeddings directly."""

    def __init__(
        self,
        *,
        model_source: str,
        artifacts_dir: Path | None = None,
        device: str | None = None,
        num_inference_steps: int | None = None,
        local_files_only: bool = True,
        require_gpu: bool = True,
    ) -> None:
        self.default_model_source = model_source
        self.artifacts_dir = artifacts_dir or settings.artifacts_dir
        self.device = device
        self.default_num_inference_steps = num_inference_steps or settings.diffusion_num_inference_steps
        self.local_files_only = local_files_only
        self.require_gpu = require_gpu
        self.artifacts_dir.mkdir(parents=True, exist_ok=True)
        self._pipelines: dict[str, object] = {}
        self._active_model_source = model_source
        self._torch = None

    def _resolve_device(self, torch) -> str:
        """Resolve the runtime device and enforce GPU-backed Diffusers inference."""

        requested_device = (self.device or settings.inference_device or "cuda").strip().lower()
        if requested_device == "auto":
            requested_device = "cuda"

        if requested_device == "cuda":
            if not torch.cuda.is_available():
                raise RuntimeError(
                    "Diffusers inference requires a CUDA-capable GPU, but torch.cuda.is_available() is false. "
                    "The runtime does not fall back to the mock generator."
                )
            return "cuda"

        if self.require_gpu:
            raise RuntimeError(
                f"Diffusers inference is configured to require GPU execution, but device={requested_device!r} was requested. "
                "Set STABLE_STEERING_INFERENCE_DEVICE=cuda."
            )

        return requested_device

    def _load_pipeline(self, model_source: str | None = None):
        """Load and cache the Stable Diffusion pipeline on first use."""

        source = model_source or self.default_model_source
        if source in self._pipelines:
            self._active_model_source = source
            return self._pipelines[source]

        import torch
        from diffusers import StableDiffusionPipeline

        resolved_device = self._resolve_device(torch)
        dtype = torch.float16 if resolved_device == "cuda" else torch.float32

        pipeline = StableDiffusionPipeline.from_pretrained(
            source,
            torch_dtype=dtype,
            local_files_only=self.local_files_only,
            safety_checker=None,
        )
        pipeline = pipeline.to(resolved_device)
        pipeline.set_progress_bar_config(disable=True)
        if hasattr(pipeline, "enable_attention_slicing"):
            pipeline.enable_attention_slicing()

        self._torch = torch
        self.device = resolved_device
        self._pipelines[source] = pipeline
        self._active_model_source = source
        return pipeline

    def diagnostics(self) -> dict:
        """Return runtime diagnostics without forcing pipeline initialization."""

        cuda_available = False
        torch_available = False
        try:
            import torch

            torch_available = True
            cuda_available = bool(torch.cuda.is_available())
        except ImportError:
            torch_available = False
            cuda_available = False

        configured_device = (self.device or settings.inference_device or "cuda").strip().lower()
        if configured_device == "auto":
            configured_device = "cuda"

        pipeline_loaded = bool(self._pipelines)
        active_device = self.device if pipeline_loaded else configured_device
        return {
            "backend": "diffusers",
            "model_source": self._active_model_source,
            "default_model_source": self.default_model_source,
            "configured_device": configured_device,
            "active_device": active_device,
            "pipeline_loaded": pipeline_loaded,
            "cuda_available": cuda_available,
            "torch_available": torch_available,
            "local_files_only": self.local_files_only,
            "test_only_backend": False,
            "default_num_inference_steps": self.default_num_inference_steps,
            "loaded_model_sources": sorted(self._pipelines.keys()),
        }

    def _resolve_model_source(self, session: Session) -> str:
        """Resolve the per-session model source from YAML config."""

        requested_model = (session.config.model_name or "").strip()
        if not requested_model:
            return self.default_model_source

        prepared_path = resolve_prepared_model_path(requested_model)
        if prepared_path.exists():
            return str(prepared_path)
        if requested_model == settings.huggingface_model_id:
            return self.default_model_source
        if settings.allow_remote_model_download:
            return requested_model
        raise FileNotFoundError(
            f"Prepared model not found for session model_name={requested_model!r} at {prepared_path}. "
            "Run scripts/setup_huggingface.py first or enable STABLE_STEERING_ALLOW_REMOTE_MODEL_DOWNLOAD=true."
        )

    def _steering_offset(self, prompt_embeds, z, anchor_strength: float):
        """Project the low-dimensional steering vector into embedding space."""

        torch = self._torch
        hidden = prompt_embeds.shape[-1]
        device = prompt_embeds.device
        dtype = prompt_embeds.dtype
        index = torch.linspace(0.0, 1.0, hidden, device=device, dtype=dtype)
        offset = torch.zeros_like(prompt_embeds)
        for i, value in enumerate(z):
            basis = torch.sin(index * (i + 1) * torch.pi) + torch.cos(index * (i + 1) * 0.5 * torch.pi)
            basis = basis / torch.norm(basis)
            offset = offset + (float(value) * float(anchor_strength)) * basis.view(1, 1, hidden)
        return offset

    def _encode_steered_embeddings(self, session: Session, candidate: Candidate):
        """Encode prompt text, then apply a deterministic steering offset."""

        pipe = self._load_pipeline(self._resolve_model_source(session))
        prompt_embeds, negative_prompt_embeds = pipe.encode_prompt(
            prompt=session.prompt,
            device=self.device,
            num_images_per_prompt=1,
            do_classifier_free_guidance=True,
            negative_prompt=session.negative_prompt or "",
        )
        steered_prompt_embeds = prompt_embeds + self._steering_offset(prompt_embeds, candidate.z, session.config.anchor_strength)
        return steered_prompt_embeds, negative_prompt_embeds

    def render_candidate(self, session: Session, candidate: Candidate) -> Candidate:
        """Render a candidate to a PNG using Diffusers prompt-embedding control."""

        model_source = self._resolve_model_source(session)
        pipe = self._load_pipeline(model_source)
        prompt_embeds, negative_prompt_embeds = self._encode_steered_embeddings(session, candidate)
        width, height = parse_image_size(session.config.image_size)
        torch = self._torch
        generator = torch.Generator(device=self.device).manual_seed(candidate.seed)
        guidance_scale = float(session.config.guidance_scale)
        num_inference_steps = int(session.config.num_inference_steps)

        result = pipe(
            prompt_embeds=prompt_embeds,
            negative_prompt_embeds=negative_prompt_embeds,
            width=width,
            height=height,
            num_inference_steps=num_inference_steps,
            guidance_scale=guidance_scale,
            generator=generator,
            output_type="pil",
        )
        image = result.images[0]
        path = self.artifacts_dir / f"{candidate.id}.png"
        image.save(path)
        candidate.image_path = f"/artifacts/{path.name}"
        candidate.generation_params.update(
            {
                "backend": "diffusers",
                "guidance_scale": guidance_scale,
                "num_inference_steps": num_inference_steps,
                "model_source": model_source,
                "anchor_strength": session.config.anchor_strength,
                "steering_mode": session.config.steering_mode,
            }
        )
        return candidate


def resolve_prepared_model_path(model_id: str, models_root: Path | None = None) -> Path:
    """Resolve the expected local path for a prepared Hugging Face model snapshot."""

    root = models_root or settings.models_dir
    return root / model_slug(model_id)


def build_generation_engine(
    *,
    backend: str | None = None,
    model_id: str | None = None,
    models_root: Path | None = None,
    artifacts_dir: Path | None = None,
    num_inference_steps: int | None = None,
) -> GenerationEngine:
    """Build the configured generation backend.

    Runtime code must not silently fall back to the mock engine. If the real
    backend cannot be constructed, this function raises a clear error instead.
    """

    selected_backend = backend or settings.generation_backend
    selected_model_id = model_id or settings.huggingface_model_id
    prepared_path = resolve_prepared_model_path(selected_model_id, models_root)

    if selected_backend == "mock":
        if not settings.allow_test_mock_backend:
            raise RuntimeError(
                "The mock generation backend is reserved for tests and is disabled in normal runtime. "
                "Set STABLE_STEERING_ALLOW_TEST_MOCK_BACKEND=true only in an explicit test harness."
            )
        return MockGenerationEngine(artifacts_dir=artifacts_dir)

    if selected_backend == "diffusers":
        if not prepared_path.exists() and not settings.allow_remote_model_download:
            raise FileNotFoundError(
                f"Prepared model not found at {prepared_path}. Run scripts/setup_huggingface.py first "
                "or enable STABLE_STEERING_ALLOW_REMOTE_MODEL_DOWNLOAD=true."
            )
        source = str(prepared_path) if prepared_path.exists() else selected_model_id
        return DiffusersGenerationEngine(
            model_source=source,
            artifacts_dir=artifacts_dir,
            device=settings.inference_device,
            num_inference_steps=num_inference_steps,
            local_files_only=prepared_path.exists() or not settings.allow_remote_model_download,
            require_gpu=True,
        )

    if selected_backend == "auto":
        if not prepared_path.exists():
            raise FileNotFoundError(
                f"Prepared model not found at {prepared_path}. Run scripts/setup_huggingface.py first "
                "or use the explicit test-only mock backend in a harness that enables STABLE_STEERING_ALLOW_TEST_MOCK_BACKEND=true."
            )
        return DiffusersGenerationEngine(
            model_source=str(prepared_path),
            artifacts_dir=artifacts_dir,
            device=settings.inference_device,
            num_inference_steps=num_inference_steps,
            local_files_only=True,
            require_gpu=True,
        )

    raise ValueError(f"Unsupported generation backend: {selected_backend}")
