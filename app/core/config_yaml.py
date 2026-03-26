from __future__ import annotations

from textwrap import dedent

import yaml
from pydantic import ValidationError

from app.core.schema import StrategyConfig


CONFIG_COMMENT_BLOCK = dedent(
    """\
    # StableSteering per-session strategy configuration
    # Edit any of these values before creating a new session.
    # This YAML is reloaded fresh for each setup page visit or reset action.
    #
    # sampler: random_local | exploit_orthogonal | uncertainty_guided | axis_sweep | incumbent_mix
    # updater: winner_average | winner_copy | linear_preference
    # feedback_mode: scalar_rating | pairwise | top_k | winner_only | approve_reject
    # seed_policy: fixed-per-round | fixed-per-candidate | fixed-per-candidate-role
    # steering_dimension: low-dimensional steering vector size, for example 3 or 5
    # image_size: WIDTHxHEIGHT, for example 512x512
    # guidance_scale: classifier-free guidance strength, for example 7.5
    # num_inference_steps: diffusion denoising steps, for example 15 or 30
    """
)


def render_strategy_config_yaml(config: StrategyConfig | None = None) -> str:
    """Return a readable YAML document for one session strategy config."""

    payload = (config or StrategyConfig()).model_dump(mode="json")
    dumped = yaml.safe_dump(payload, sort_keys=False, default_flow_style=False).strip()
    return f"{CONFIG_COMMENT_BLOCK}\n{dumped}\n"


def parse_strategy_config_yaml(text: str) -> StrategyConfig:
    """Parse editable YAML into a validated StrategyConfig instance."""

    try:
        payload = yaml.safe_load(text) or {}
    except yaml.YAMLError as exc:
        raise ValueError(f"Invalid YAML configuration: {exc}") from exc

    if not isinstance(payload, dict):
        raise ValueError("Config YAML must define a mapping of key/value pairs.")

    try:
        return StrategyConfig.model_validate(payload)
    except ValidationError as exc:
        messages = []
        for error in exc.errors():
            location = ".".join(str(part) for part in error.get("loc", []))
            messages.append(f"{location}: {error.get('msg')}")
        raise ValueError("Invalid session configuration. " + "; ".join(messages)) from exc
