from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Literal
from uuid import uuid4

from pydantic import BaseModel, Field


def utc_now() -> datetime:
    """Return a timezone-aware UTC timestamp."""

    return datetime.now(timezone.utc)


def new_id(prefix: str) -> str:
    """Create a short, readable identifier with a stable prefix."""

    return f"{prefix}_{uuid4().hex[:12]}"


class ExperimentStatus(str, Enum):
    draft = "draft"
    active = "active"
    paused = "paused"
    completed = "completed"
    archived = "archived"


class SessionStatus(str, Enum):
    created = "created"
    ready = "ready"
    awaiting_feedback = "awaiting_feedback"
    updating = "updating"
    completed = "completed"
    failed = "failed"
    paused = "paused"


class RenderStatus(str, Enum):
    pending = "pending"
    rendering = "rendering"
    succeeded = "succeeded"
    failed = "failed"


class FeedbackType(str, Enum):
    scalar_rating = "scalar_rating"
    pairwise = "pairwise"
    top_k = "top_k"
    winner_only = "winner_only"
    approve_reject = "approve_reject"


class SeedPolicy(str, Enum):
    fixed_per_round = "fixed-per-round"
    fixed_per_candidate = "fixed-per-candidate"
    fixed_per_candidate_role = "fixed-per-candidate-role"


class SamplerType(str, Enum):
    random_local = "random_local"
    exploit_orthogonal = "exploit_orthogonal"
    uncertainty_guided = "uncertainty_guided"
    axis_sweep = "axis_sweep"
    incumbent_mix = "incumbent_mix"


class UpdaterType(str, Enum):
    winner_average = "winner_average"
    winner_copy = "winner_copy"
    linear_preference = "linear_preference"


class SteeringMode(str, Enum):
    low_dimensional = "low_dimensional"


class StrategyConfig(BaseModel):
    """Experiment-level strategy choices and tunable parameters."""

    sampler: SamplerType = SamplerType.exploit_orthogonal
    updater: UpdaterType = UpdaterType.winner_average
    feedback_mode: FeedbackType = FeedbackType.scalar_rating
    seed_policy: SeedPolicy = SeedPolicy.fixed_per_candidate
    steering_mode: SteeringMode = SteeringMode.low_dimensional
    steering_dimension: int = Field(default=5, ge=1, le=16)
    candidate_count: int = Field(default=5, ge=1, le=12)
    image_size: str = "512x512"
    trust_radius: float = Field(default=0.55, gt=0.0, le=1.0)
    anchor_strength: float = Field(default=0.7, ge=0.0, le=2.0)
    guidance_scale: float = Field(default=7.5, gt=0.0, le=20.0)
    num_inference_steps: int = Field(default=15, ge=1, le=100)
    model_name: str = "runwayml/stable-diffusion-v1-5"


class ExperimentCreate(BaseModel):
    """Payload for creating a reusable experiment configuration."""

    name: str
    description: str = ""
    config: StrategyConfig = Field(default_factory=StrategyConfig)


class Experiment(BaseModel):
    """Persisted experiment configuration and metadata."""

    id: str = Field(default_factory=lambda: new_id("exp"))
    name: str
    description: str = ""
    status: ExperimentStatus = ExperimentStatus.active
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)
    config: StrategyConfig


class SessionCreate(BaseModel):
    """Payload for starting a session from an experiment or ad hoc config."""

    experiment_id: str | None = None
    config: StrategyConfig | None = None
    prompt: str
    negative_prompt: str = ""


class SetupSessionRequest(BaseModel):
    """Prompt-first setup payload that carries an editable YAML config blob."""

    experiment_name: str
    description: str = ""
    prompt: str
    negative_prompt: str = ""
    config_yaml: str


class Candidate(BaseModel):
    """One proposed point in steering space and its render metadata."""

    id: str = Field(default_factory=lambda: new_id("cand"))
    round_id: str
    candidate_index: int
    z: list[float]
    sampler_role: str
    predicted_score: float | None = None
    predicted_uncertainty: float | None = None
    seed: int
    generation_params: dict[str, Any]
    image_path: str | None = None
    render_status: RenderStatus = RenderStatus.pending


class FeedbackEvent(BaseModel):
    """Normalized record of one user feedback action for a round."""

    id: str = Field(default_factory=lambda: new_id("fb"))
    round_id: str
    type: FeedbackType
    payload: dict[str, Any]
    normalized_payload: dict[str, Any]
    critique_text: str | None = None
    created_at: datetime = Field(default_factory=utc_now)


class Round(BaseModel):
    """One propose-render-feedback-update cycle within a session."""

    id: str = Field(default_factory=lambda: new_id("rnd"))
    session_id: str
    round_index: int
    incumbent_z: list[float]
    trust_radius: float
    seed_policy: str
    render_status: RenderStatus = RenderStatus.pending
    candidates: list[Candidate] = Field(default_factory=list)
    feedback_events: list[FeedbackEvent] = Field(default_factory=list)
    update_summary: dict[str, Any] = Field(default_factory=dict)
    latency_ms: int = 0
    created_at: datetime = Field(default_factory=utc_now)


class Session(BaseModel):
    """Interactive steering session state."""

    id: str = Field(default_factory=lambda: new_id("ses"))
    experiment_id: str
    prompt: str
    negative_prompt: str = ""
    model_name: str
    status: SessionStatus = SessionStatus.created
    basis_type: str = "random_orthonormal"
    current_round: int = 0
    current_z: list[float] = Field(default_factory=list)
    incumbent_candidate_id: str | None = None
    final_selected_candidate: str | None = None
    base_embedding_cache_key: str = Field(default_factory=lambda: new_id("emb"))
    config: StrategyConfig
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)


class SessionSummary(BaseModel):
    """Convenience container for session plus ordered rounds."""

    session: Session
    rounds: list[Round]


class RoundResponse(BaseModel):
    """API response returned after generating a round."""

    round_id: str
    candidate_metadata: list[Candidate]
    image_urls: list[str]
    state_summary: dict[str, Any]


class FeedbackRequest(BaseModel):
    """API payload used to submit feedback for a round."""

    feedback_type: FeedbackType
    payload: dict[str, Any]
    critique_text: str | None = None


class FeedbackResponse(BaseModel):
    """API response returned after feedback updates the incumbent state."""

    update_summary: dict[str, Any]
    next_incumbent_state: list[float]


class ReplayExport(BaseModel):
    """Serializable replay bundle for one completed or in-progress session."""

    schema_version: str = "1.0"
    app_version: str = "0.1.0"
    experiment: Experiment | None
    session: Session
    rounds: list[Round]
    exported_at: datetime = Field(default_factory=utc_now)


class ApiError(BaseModel):
    """Structured API error payload."""

    error_code: Literal["not_found", "invalid_input", "conflict", "internal_error"]
    message: str
