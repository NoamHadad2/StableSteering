from __future__ import annotations

from pathlib import Path

from huggingface_hub.utils import LocalEntryNotFoundError

from app.core.config import settings

_CLIP_CACHE: dict[tuple[str, str], tuple[object, object]] = {}
_DINO_CACHE: dict[tuple[str, str], tuple[object, object]] = {}


def huggingface_cache_dir() -> Path:
    path = settings.huggingface_cache_dir
    path.mkdir(parents=True, exist_ok=True)
    return path


def get_clip_components(model_id: str, device: str, *, local_only: bool = True):
    key = (model_id, device)
    cached = _CLIP_CACHE.get(key)
    if cached is not None:
        return cached

    from transformers import CLIPModel, CLIPProcessor

    cache_dir = huggingface_cache_dir()
    try:
        model = CLIPModel.from_pretrained(
            model_id,
            cache_dir=str(cache_dir),
            local_files_only=local_only,
        ).to(device)
        processor = CLIPProcessor.from_pretrained(
            model_id,
            cache_dir=str(cache_dir),
            local_files_only=local_only,
        )
    except (OSError, LocalEntryNotFoundError) as exc:
        if local_only:
            raise RuntimeError(
                f"CLIP model '{model_id}' is not available in the local cache. "
                "Run scripts/preload_experiment_models.py first."
            ) from exc
        raise
    model.eval()
    _CLIP_CACHE[key] = (model, processor)
    return model, processor


def get_dino_components(model_id: str, device: str, *, local_only: bool = True):
    key = (model_id, device)
    cached = _DINO_CACHE.get(key)
    if cached is not None:
        return cached

    from transformers import AutoImageProcessor, AutoModel

    cache_dir = huggingface_cache_dir()
    try:
        processor = AutoImageProcessor.from_pretrained(
            model_id,
            cache_dir=str(cache_dir),
            local_files_only=local_only,
        )
        model = AutoModel.from_pretrained(
            model_id,
            cache_dir=str(cache_dir),
            local_files_only=local_only,
        ).to(device)
    except (OSError, LocalEntryNotFoundError) as exc:
        if local_only:
            raise RuntimeError(
                f"DINO model '{model_id}' is not available in the local cache. "
                "Run scripts/preload_experiment_models.py first."
            ) from exc
        raise
    model.eval()
    _DINO_CACHE[key] = (processor, model)
    return processor, model
