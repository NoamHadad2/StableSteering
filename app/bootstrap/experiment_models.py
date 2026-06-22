from __future__ import annotations

from pathlib import Path

from huggingface_hub.utils import LocalEntryNotFoundError

from app.core.config import settings

_CLIP_CACHE: dict[tuple[str, str], tuple[object, object]] = {}
_DINO_CACHE: dict[tuple[str, str], tuple[object, object]] = {}
_SIGLIP_CACHE: dict[tuple[str, str], tuple[object, object]] = {}
_BLIP_CAPTION_CACHE: dict[tuple[str, str], tuple[object, object]] = {}
_LPIPS_CACHE: dict[tuple[str, str], object] = {}


def huggingface_cache_dir() -> Path:
    path = settings.huggingface_cache_dir
    path.mkdir(parents=True, exist_ok=True)
    return path


def _local_cache_error(model_family: str, model_id: str) -> RuntimeError:
    return RuntimeError(
        f"{model_family} model '{model_id}' is not available in the local cache. "
        "Run scripts/preload_experiment_models.py first."
    )


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
            raise _local_cache_error("CLIP", model_id) from exc
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
            raise _local_cache_error("DINO", model_id) from exc
        raise
    model.eval()
    _DINO_CACHE[key] = (processor, model)
    return processor, model


def get_siglip_components(model_id: str, device: str, *, local_only: bool = True):
    key = (model_id, device)
    cached = _SIGLIP_CACHE.get(key)
    if cached is not None:
        return cached

    from transformers import SiglipImageProcessor, SiglipModel

    cache_dir = huggingface_cache_dir()
    try:
        processor = SiglipImageProcessor.from_pretrained(
            model_id,
            cache_dir=str(cache_dir),
            local_files_only=local_only,
            use_fast=False,
        )
        model = SiglipModel.from_pretrained(
            model_id,
            cache_dir=str(cache_dir),
            local_files_only=local_only,
        ).to(device)
    except (OSError, LocalEntryNotFoundError) as exc:
        if local_only:
            raise _local_cache_error("SigLIP", model_id) from exc
        raise
    model.eval()
    _SIGLIP_CACHE[key] = (processor, model)
    return processor, model


def get_blip_caption_components(model_id: str, device: str, *, local_only: bool = True):
    key = (model_id, device)
    cached = _BLIP_CAPTION_CACHE.get(key)
    if cached is not None:
        return cached

    from transformers import BlipForConditionalGeneration, BlipProcessor

    cache_dir = huggingface_cache_dir()
    try:
        processor = BlipProcessor.from_pretrained(
            model_id,
            cache_dir=str(cache_dir),
            local_files_only=local_only,
            use_fast=False,
        )
        model = BlipForConditionalGeneration.from_pretrained(
            model_id,
            cache_dir=str(cache_dir),
            local_files_only=local_only,
        ).to(device)
    except (OSError, LocalEntryNotFoundError) as exc:
        if local_only:
            raise _local_cache_error("BLIP caption", model_id) from exc
        raise
    model.eval()
    _BLIP_CAPTION_CACHE[key] = (processor, model)
    return processor, model


def get_lpips_metric(net_name: str, device: str):
    key = (net_name, device)
    cached = _LPIPS_CACHE.get(key)
    if cached is not None:
        return cached

    import lpips

    model = lpips.LPIPS(net=net_name).to(device)
    model.eval()
    _LPIPS_CACHE[key] = model
    return model
