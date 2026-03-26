from __future__ import annotations

import pytest

from app.core.config_yaml import parse_strategy_config_yaml, render_strategy_config_yaml


def test_render_strategy_config_yaml_uses_current_defaults() -> None:
    rendered = render_strategy_config_yaml()
    assert "candidate_count: 5" in rendered
    assert "sampler: random_local" in rendered
    assert "feedback_mode: scalar_rating" in rendered
    assert "guidance_scale: 7.5" in rendered
    assert "num_inference_steps: 15" in rendered


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
guidance_scale: 8.0
num_inference_steps: 25
model_name: runwayml/stable-diffusion-v1-5
"""
    )
    assert config.candidate_count == 6
    assert config.sampler == "uncertainty_guided"
    assert config.feedback_mode.value == "top_k"
    assert config.guidance_scale == 8.0
    assert config.num_inference_steps == 25


def test_parse_strategy_config_yaml_rejects_non_mapping() -> None:
    with pytest.raises(ValueError, match="mapping"):
        parse_strategy_config_yaml(
            """
- sampler: random_local
"""
        )


def test_parse_strategy_config_yaml_rejects_unknown_sampler() -> None:
    with pytest.raises(ValueError, match="sampler"):
        parse_strategy_config_yaml(
            """
sampler: imaginary_sampler
"""
        )


def test_parse_strategy_config_yaml_rejects_unknown_updater() -> None:
    with pytest.raises(ValueError, match="updater"):
        parse_strategy_config_yaml(
            """
updater: imaginary_updater
"""
        )
