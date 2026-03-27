from __future__ import annotations

import argparse
from pathlib import Path

import yaml

from app.bootstrap.experiment_models import (
    get_blip_caption_components,
    get_clip_components,
    get_dino_components,
    get_lpips_metric,
    get_siglip_components,
    huggingface_cache_dir,
)
from app.bootstrap.huggingface import prepare_huggingface_model
from app.core.config import settings


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _protocol_model_ids(protocol_dir: Path) -> tuple[set[str], set[str], set[str], set[str], set[str], set[str]]:
    diffusion_models: set[str] = set()
    clip_models: set[str] = set()
    dino_models: set[str] = set()
    siglip_models: set[str] = set()
    caption_models: set[str] = set()
    lpips_nets: set[str] = set()
    for path in protocol_dir.glob("*.yaml"):
        payload = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        if not isinstance(payload, dict):
            continue
        fixed_conditions = payload.get("fixed_conditions", {})
        shared_conditions = payload.get("shared_conditions", {})
        for container in (fixed_conditions, shared_conditions):
            if isinstance(container, dict) and container.get("model_name"):
                diffusion_models.add(str(container["model_name"]))
        if payload.get("oracle_model"):
            clip_models.add(str(payload["oracle_model"]))
        if payload.get("dino_model"):
            dino_models.add(str(payload["dino_model"]))
        caption_model = payload.get("caption_model")
        if isinstance(caption_model, dict) and caption_model.get("id"):
            caption_models.add(str(caption_model["id"]))
        elif isinstance(caption_model, str):
            caption_models.add(caption_model)
        for record in payload.get("evaluation_models", []):
            if not isinstance(record, dict):
                continue
            model_id = record.get("id")
            kind = record.get("kind")
            if not model_id or not kind:
                continue
            if str(kind) == "clip":
                clip_models.add(str(model_id))
            elif str(kind) == "dinov2":
                dino_models.add(str(model_id))
            elif str(kind) == "siglip":
                siglip_models.add(str(model_id))
            elif str(kind) == "lpips":
                lpips_nets.add(str(model_id).replace("lpips-", "", 1))
    return diffusion_models, clip_models, dino_models, siglip_models, caption_models, lpips_nets


def _hf_cache_has_model(cache_dir: Path, model_id: str) -> bool:
    slug = model_id.replace("/", "--")
    return (cache_dir / f"models--{slug}").exists()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Preload StableSteering experiment models into local caches.")
    parser.add_argument(
        "--protocol-dir",
        default=str(_repo_root() / "paper" / "protocols"),
        help="Directory of protocol YAML files to scan for model ids.",
    )
    parser.add_argument(
        "--include-default-diffusion",
        action="store_true",
        help="Also preload the default diffusion model from app settings.",
    )
    return parser


def main() -> int:
    args = build_parser().parse_args()
    protocol_dir = Path(args.protocol_dir)
    diffusion_models, clip_models, dino_models, siglip_models, caption_models, lpips_nets = _protocol_model_ids(protocol_dir)
    if args.include_default_diffusion:
        diffusion_models.add(settings.huggingface_model_id)

    cache_dir = huggingface_cache_dir()

    print("Preloading diffusion models:")
    for model_id in sorted(diffusion_models):
        result = prepare_huggingface_model(
            model_id=model_id,
            output_root=settings.models_dir,
            cache_dir=cache_dir,
        )
        print(f"  prepared {model_id} -> {result['model_dir']}")

    print("Preloading CLIP-family evaluation models:")
    for model_id in sorted(clip_models):
        get_clip_components(model_id, "cpu", local_only=_hf_cache_has_model(cache_dir, model_id))
        print(f"  cached {model_id} in {cache_dir}")

    print("Preloading DINO-family evaluation models:")
    for model_id in sorted(dino_models):
        get_dino_components(model_id, "cpu", local_only=_hf_cache_has_model(cache_dir, model_id))
        print(f"  cached {model_id} in {cache_dir}")

    print("Preloading SigLIP-family evaluation models:")
    for model_id in sorted(siglip_models):
        get_siglip_components(model_id, "cpu", local_only=_hf_cache_has_model(cache_dir, model_id))
        print(f"  cached {model_id} in {cache_dir}")

    print("Preloading captioning models:")
    for model_id in sorted(caption_models):
        get_blip_caption_components(model_id, "cpu", local_only=_hf_cache_has_model(cache_dir, model_id))
        print(f"  cached {model_id} in {cache_dir}")

    print("Preloading LPIPS metrics:")
    for net_name in sorted(lpips_nets):
        get_lpips_metric(net_name, "cpu")
        print(f"  cached lpips-{net_name}")

    print("Done.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
