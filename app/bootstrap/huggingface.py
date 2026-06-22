from __future__ import annotations

import json
from pathlib import Path
from typing import Iterable

from huggingface_hub import snapshot_download


DEFAULT_ALLOW_PATTERNS = [
    "model_index.json",
    "scheduler/*",
    "text_encoder/*",
    "text_encoder_2/*",
    "tokenizer/*",
    "tokenizer_2/*",
    "unet/*",
    "vae/*",
    "feature_extractor/*",
    "safety_checker/*",
]


def model_slug(model_id: str) -> str:
    """Convert a Hugging Face model id into a filesystem-friendly slug."""

    return model_id.replace("/", "--")


def build_allow_patterns(extra_patterns: Iterable[str] | None = None) -> list[str]:
    """Return the default snapshot patterns plus any caller-provided extras."""

    patterns = list(DEFAULT_ALLOW_PATTERNS)
    if extra_patterns:
        patterns.extend(pattern for pattern in extra_patterns if pattern not in patterns)
    return patterns


def write_manifest(
    output_dir: Path,
    *,
    model_id: str,
    revision: str | None,
    cache_dir: Path | None,
    allow_patterns: list[str],
    snapshot_path: str,
) -> Path:
    """Write a small manifest describing the prepared model snapshot."""

    manifest_path = output_dir / "prepare_manifest.json"
    payload = {
        "model_id": model_id,
        "revision": revision,
        "cache_dir": str(cache_dir) if cache_dir else None,
        "allow_patterns": allow_patterns,
        "snapshot_path": snapshot_path,
    }
    manifest_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return manifest_path


def prepare_huggingface_model(
    *,
    model_id: str,
    output_root: Path,
    revision: str | None = None,
    cache_dir: Path | None = None,
    extra_patterns: Iterable[str] | None = None,
) -> dict[str, str]:
    """Download and stage a diffusers-style model snapshot locally.

    The script intentionally downloads only the module directories the future
    real generator is expected to need. That keeps setup predictable and
    avoids pulling optional artifacts that the current MVP does not use yet.
    """

    output_root.mkdir(parents=True, exist_ok=True)
    model_dir = output_root / model_slug(model_id)
    model_dir.mkdir(parents=True, exist_ok=True)

    allow_patterns = build_allow_patterns(extra_patterns)
    manifest_path = model_dir / "prepare_manifest.json"
    model_index_path = model_dir / "model_index.json"
    if manifest_path.exists() and model_index_path.exists():
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            manifest = None
        if (
            isinstance(manifest, dict)
            and str(manifest.get("model_id")) == model_id
            and manifest.get("revision") == revision
            and list(manifest.get("allow_patterns", [])) == allow_patterns
        ):
            return {
                "model_id": model_id,
                "model_dir": str(model_dir),
                "snapshot_path": str(model_dir),
                "manifest_path": str(manifest_path),
            }

    snapshot_path = snapshot_download(
        repo_id=model_id,
        revision=revision,
        cache_dir=str(cache_dir) if cache_dir else None,
        local_dir=str(model_dir),
        allow_patterns=allow_patterns,
        local_dir_use_symlinks=False,
    )

    manifest_path = write_manifest(
        model_dir,
        model_id=model_id,
        revision=revision,
        cache_dir=cache_dir,
        allow_patterns=allow_patterns,
        snapshot_path=snapshot_path,
    )

    return {
        "model_id": model_id,
        "model_dir": str(model_dir),
        "snapshot_path": snapshot_path,
        "manifest_path": str(manifest_path),
    }
