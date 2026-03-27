from __future__ import annotations

from html import escape
from pathlib import Path
from typing import Protocol

from app.bootstrap.huggingface import model_slug
from app.core.config import settings
from app.core.schema import Candidate, Session, SteeringMode


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


def resolve_steering_mode(session: Session) -> SteeringMode:
    """Resolve and validate the session steering mode used at generation time."""

    mode = session.config.steering_mode
    if mode in {
        SteeringMode.low_dimensional,
        SteeringMode.content_masked,
        SteeringMode.token_factorized,
        SteeringMode.token_vector_field,
    }:
        return mode
    raise ValueError(f"Unsupported steering mode: {mode}")


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

        steering_mode = resolve_steering_mode(session)
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
<text x="40" y="435" fill="white" font-size="18" font-family="Arial">Steering mode: {escape(steering_mode.value)}</text>
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
                "steering_mode": steering_mode.value,
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

    def _hidden_basis(self, hidden: int, index_id: int, *, device, dtype):
        """Build a deterministic hidden-space basis vector for one steering axis."""

        torch = self._torch
        index = torch.linspace(0.0, 1.0, hidden, device=device, dtype=dtype)
        basis = torch.sin(index * (index_id + 1) * torch.pi) + torch.cos(index * (index_id + 1) * 0.5 * torch.pi)
        return basis / torch.norm(basis)

    def _token_hidden_basis(self, seq_len: int, hidden: int, index_id: int, *, device, dtype):
        """Build a deterministic per-token hidden-vector field for one steering axis."""

        torch = self._torch
        token_index = torch.linspace(0.0, 1.0, seq_len, device=device, dtype=dtype).view(seq_len, 1)
        hidden_index = torch.linspace(0.0, 1.0, hidden, device=device, dtype=dtype).view(1, hidden)
        frequency = float(index_id + 1)
        basis = (
            torch.sin((token_index + 0.17 * frequency) * (hidden_index + 0.11) * torch.pi * (1.0 + frequency))
            + 0.7 * torch.cos((token_index * (0.45 + 0.08 * frequency) - hidden_index * (0.63 + 0.04 * frequency)) * torch.pi)
            + 0.35 * torch.sin((token_index * hidden_index + 0.13 * frequency) * 2.0 * torch.pi)
        )
        return basis / torch.clamp(torch.norm(basis), min=torch.tensor(1e-6, device=device, dtype=dtype))

    def _token_inputs(self, pipe, prompt: str, *, seq_len: int, device, dtype):
        """Tokenize the prompt so token-aware steering modes can shape per-token offsets."""

        tokenizer = getattr(pipe, "tokenizer", None)
        if tokenizer is None:
            return None

        tokenized = tokenizer(
            prompt,
            padding="max_length",
            truncation=True,
            max_length=seq_len,
            return_tensors="pt",
        )
        input_ids = tokenized.input_ids.to(device=device)
        attention_mask = tokenized.attention_mask.to(device=device, dtype=dtype)
        return {"input_ids": input_ids, "attention_mask": attention_mask}

    def _content_mask(self, token_inputs, *, tokenizer, dtype):
        """Build a mask that suppresses padding and special tokens for token-aware steering."""

        attention_mask = token_inputs["attention_mask"].to(dtype=dtype)
        input_ids = token_inputs["input_ids"]
        content_mask = attention_mask.clone()

        if tokenizer is not None:
            for attr in ("bos_token_id", "eos_token_id", "pad_token_id"):
                token_id = getattr(tokenizer, attr, None)
                if token_id is not None:
                    content_mask = content_mask * (input_ids != token_id).to(dtype=dtype)

        if float(content_mask.sum()) <= 0.0:
            return attention_mask
        return content_mask

    def _steering_offset(self, prompt_embeds, z, anchor_strength: float, *, steering_mode: SteeringMode, token_inputs=None, tokenizer=None):
        """Project the low-dimensional steering vector into embedding space."""

        torch = self._torch
        seq_len = prompt_embeds.shape[1]
        hidden = prompt_embeds.shape[-1]
        device = prompt_embeds.device
        dtype = prompt_embeds.dtype
        offset = torch.zeros_like(prompt_embeds)

        if steering_mode == SteeringMode.low_dimensional:
            for i, value in enumerate(z):
                basis = self._hidden_basis(hidden, i, device=device, dtype=dtype)
                offset = offset + (float(value) * float(anchor_strength)) * basis.view(1, 1, hidden)
            return offset

        if token_inputs is None:
            raise ValueError(f"Token-aware steering mode {steering_mode.value} requires token inputs.")

        content_mask = self._content_mask(token_inputs, tokenizer=tokenizer, dtype=dtype)
        token_positions = torch.linspace(0.0, 1.0, seq_len, device=device, dtype=dtype)

        if steering_mode == SteeringMode.content_masked:
            token_profile = 0.35 + 0.65 * torch.sin(token_positions * torch.pi)
            token_profile = token_profile.view(1, seq_len, 1) * content_mask.view(1, seq_len, 1)
            active_tokens = torch.clamp(content_mask.sum(), min=1.0)
            normalizer = torch.clamp(token_profile.sum(dim=1, keepdim=True), min=1.0)
            token_profile = token_profile * (active_tokens / normalizer)
            for i, value in enumerate(z):
                basis = self._hidden_basis(hidden, i, device=device, dtype=dtype)
                offset = offset + (float(value) * float(anchor_strength)) * token_profile * basis.view(1, 1, hidden)
            return offset

        if steering_mode == SteeringMode.token_factorized:
            mask = content_mask.view(seq_len)
            for i, value in enumerate(z):
                hidden_basis = self._hidden_basis(hidden, i, device=device, dtype=dtype)
                token_basis = (
                    torch.sin(token_positions * (i + 1) * torch.pi)
                    + 0.5 * torch.cos(token_positions * (i + 1) * 2.0 * torch.pi)
                ) * mask
                if float(token_basis.abs().sum()) > 0.0:
                    token_basis = token_basis - ((token_basis * mask).sum() / torch.clamp(mask.sum(), min=1.0)) * mask
                    token_norm = torch.norm(token_basis)
                    if float(token_norm) > 0.0:
                        token_basis = token_basis / token_norm
                offset = offset + (float(value) * float(anchor_strength) * 0.8) * token_basis.view(1, seq_len, 1) * hidden_basis.view(1, 1, hidden)
            return offset

        if steering_mode == SteeringMode.token_vector_field:
            mask = content_mask.view(seq_len, 1)
            active_tokens = torch.clamp(mask.sum(), min=1.0)
            for i, value in enumerate(z):
                token_hidden_basis = self._token_hidden_basis(seq_len, hidden, i, device=device, dtype=dtype) * mask
                if float(token_hidden_basis.abs().sum()) > 0.0:
                    token_hidden_basis = token_hidden_basis - token_hidden_basis.sum(dim=0, keepdim=True) / active_tokens
                    token_hidden_basis = token_hidden_basis * mask
                    token_hidden_basis = token_hidden_basis / torch.clamp(
                        torch.norm(token_hidden_basis),
                        min=torch.tensor(1e-6, device=device, dtype=dtype),
                    )
                offset = offset + (float(value) * float(anchor_strength) * 0.7) * token_hidden_basis.unsqueeze(0)
            return offset

        return offset

    def _encode_steered_embeddings(self, session: Session, candidate: Candidate):
        """Encode prompt text, then apply a deterministic steering offset."""

        steering_mode = resolve_steering_mode(session)
        pipe = self._load_pipeline(self._resolve_model_source(session))
        prompt_embeds, negative_prompt_embeds = pipe.encode_prompt(
            prompt=session.prompt,
            device=self.device,
            num_images_per_prompt=1,
            do_classifier_free_guidance=True,
            negative_prompt=session.negative_prompt or "",
        )
        token_inputs = self._token_inputs(
            pipe,
            session.prompt,
            seq_len=prompt_embeds.shape[1],
            device=prompt_embeds.device,
            dtype=prompt_embeds.dtype,
        )
        steered_prompt_embeds = prompt_embeds + self._steering_offset(
            prompt_embeds,
            candidate.z,
            session.config.anchor_strength,
            steering_mode=steering_mode,
            token_inputs=token_inputs,
            tokenizer=getattr(pipe, "tokenizer", None),
        )
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
                "steering_mode": resolve_steering_mode(session).value,
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
