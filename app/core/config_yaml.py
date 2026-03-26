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
    # sampler: random_local | exploit_orthogonal | uncertainty_guided
    # updater: winner_average | winner_copy | linear_preference
    # feedback_mode: scalar_rating | pairwise | top_k
    # image_size: WIDTHxHEIGHT, for example 512x512
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
