from __future__ import annotations

import json
from pathlib import Path

from app.bootstrap.huggingface import build_allow_patterns, model_slug, write_manifest


def test_model_slug_replaces_repo_separator() -> None:
    assert model_slug("runwayml/stable-diffusion-v1-5") == "runwayml--stable-diffusion-v1-5"


def test_build_allow_patterns_includes_defaults_and_extras() -> None:
    patterns = build_allow_patterns(["custom/*", "vae/*"])
    assert "model_index.json" in patterns
    assert "custom/*" in patterns
    assert patterns.count("vae/*") == 1


def test_write_manifest_creates_json_file(tmp_path: Path) -> None:
    manifest = write_manifest(
        tmp_path,
        model_id="runwayml/stable-diffusion-v1-5",
        revision="main",
        cache_dir=tmp_path / "cache",
        allow_patterns=["model_index.json"],
        snapshot_path=str(tmp_path / "snapshot"),
    )
    payload = json.loads(manifest.read_text(encoding="utf-8"))
    assert payload["model_id"] == "runwayml/stable-diffusion-v1-5"
    assert payload["allow_patterns"] == ["model_index.json"]
