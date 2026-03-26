from __future__ import annotations

import pytest

from app.core.config_yaml import parse_strategy_config_yaml, render_strategy_config_yaml


def test_render_strategy_config_yaml_uses_current_defaults() -> None:
    rendered = render_strategy_config_yaml()
    assert "candidate_count: 5" in rendered
    assert "sampler: random_local" in rendered
    assert "feedback_mode: scalar_rating" in rendered


def test_parse_strategy_config_yaml_accepts_valid_yaml() -> None:
    config = parse_strategy_config_yaml(
        """
sampler: uncertainty_guided
updater: linear_preference
feedback_mode: top_k
seed_policy: fixed-per-round
steering_mode: low_dimensional
candidate_count: 6
image_size: 512x512
trust_radius: 0.4
anchor_strength: 0.2
model_name: runwayml/stable-diffusion-v1-5
"""
    )
    assert config.candidate_count == 6
    assert config.sampler == "uncertainty_guided"
    assert config.feedback_mode.value == "top_k"


def test_parse_strategy_config_yaml_rejects_non_mapping() -> None:
    with pytest.raises(ValueError, match="mapping"):
        parse_strategy_config_yaml(
            """
- sampler: random_local
"""
        )
