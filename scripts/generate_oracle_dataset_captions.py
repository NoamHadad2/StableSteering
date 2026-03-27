from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import torch
from PIL import Image

from app.bootstrap.experiment_models import get_blip_caption_components


DEFAULT_MODEL_ID = "Salesforce/blip-image-captioning-large"


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _default_manifest_path() -> Path:
    return _repo_root() / "paper" / "data" / "flickr8k_curated_test_sample" / "manifest.json"


def _default_output_path() -> Path:
    return _repo_root() / "paper" / "data" / "flickr8k_curated_test_sample" / "generated_captions" / "blip_large_captions.json"


def _load_manifest(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"Expected JSON object in {path}")
    return payload


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


def _strip_prompt_prefix(caption: str, prompt_prefix: str | None) -> str:
    text = " ".join(caption.replace("\n", " ").split()).strip()
    if not prompt_prefix:
        return text
    prefix = " ".join(prompt_prefix.split()).strip().lower()
    lowered = text.lower()
    if lowered.startswith(prefix):
        text = text[len(prefix) :].lstrip(" ,.:;-")
    return text or "image"


def _decode(processor: Any, sequences: torch.Tensor) -> list[str]:
    return [processor.decode(sequence, skip_special_tokens=True).strip() for sequence in sequences]


def _generate_caption_variants(processor: Any, model: Any, image: Image.Image) -> dict[str, Any]:
    candidate_rows: list[dict[str, Any]] = []

    def add_candidates(prompt_prefix: str | None, *, num_return_sequences: int) -> None:
        if prompt_prefix is None:
            inputs = processor(images=image, return_tensors="pt")
        else:
            inputs = processor(images=image, text=prompt_prefix, return_tensors="pt")
        inputs = {key: value.to(model.device) for key, value in inputs.items()}
        with torch.no_grad():
            sequences = model.generate(
                **inputs,
                max_new_tokens=48,
                min_new_tokens=8,
                num_beams=max(4, num_return_sequences * 2),
                num_return_sequences=num_return_sequences,
                length_penalty=1.0,
                repetition_penalty=1.12,
                no_repeat_ngram_size=3,
            )
        for decoded in _decode(processor, sequences):
            stripped = _strip_prompt_prefix(decoded, prompt_prefix)
            candidate_rows.append(
                {
                    "prompt_prefix": prompt_prefix,
                    "raw_caption": decoded,
                    "caption": stripped,
                    "word_count": len(stripped.split()),
                }
            )

    add_candidates(None, num_return_sequences=3)
    add_candidates("a detailed photograph of", num_return_sequences=2)
    add_candidates("a detailed natural image of", num_return_sequences=2)

    unique_rows: list[dict[str, Any]] = []
    seen: set[str] = set()
    for row in sorted(candidate_rows, key=lambda item: (-item["word_count"], item["caption"])):
        key = row["caption"].lower()
        if key in seen:
            continue
        seen.add(key)
        unique_rows.append(row)

    standard = next((row for row in unique_rows if row["prompt_prefix"] is None), unique_rows[0])
    detailed = max(unique_rows, key=lambda item: (item["word_count"], item["caption"]))
    return {
        "standard_caption": standard["caption"],
        "standard_word_count": standard["word_count"],
        "selected_detailed_caption": detailed["caption"],
        "selected_detailed_word_count": detailed["word_count"],
        "candidate_captions": unique_rows,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Generate caption-model prompts for the oracle recovery dataset sample.")
    parser.add_argument("--manifest", default=str(_default_manifest_path()), help="Path to the dataset manifest JSON.")
    parser.add_argument("--output", default=str(_default_output_path()), help="Where to write the caption artifact JSON.")
    parser.add_argument("--model-id", default=DEFAULT_MODEL_ID, help="Hugging Face caption model id.")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    manifest_path = Path(args.manifest)
    output_path = Path(args.output)
    manifest = _load_manifest(manifest_path)
    targets = manifest.get("targets", [])
    if not isinstance(targets, list) or not targets:
        raise ValueError("Manifest must contain a non-empty 'targets' list.")

    device = "cuda" if torch.cuda.is_available() else "cpu"
    processor, model = get_blip_caption_components(args.model_id, device, local_only=False)

    rows: list[dict[str, Any]] = []
    human_word_counts: list[int] = []
    ai_word_counts: list[int] = []
    for target in targets:
        image_path = Path(str(target["image_path"]))
        image = Image.open(image_path).convert("RGB")
        captions = _generate_caption_variants(processor, model, image)
        human_caption = str(target.get("caption", "")).strip()
        human_word_counts.append(len(human_caption.split()))
        ai_word_counts.append(int(captions["selected_detailed_word_count"]))
        rows.append(
            {
                "target_id": str(target["target_id"]),
                "image_path": str(image_path),
                "human_caption": human_caption,
                "human_word_count": len(human_caption.split()),
                **captions,
            }
        )

    payload = {
        "caption_model": {
            "id": args.model_id,
            "label": "BLIP image-captioning large",
            "selection_note": (
                "Selected for the oracle caption-recovery extension because it runs reliably in the local "
                "transformers stack and supports reproducible image-to-text caption generation on the curated sample."
            ),
        },
        "dataset_manifest": str(manifest_path),
        "target_count": len(rows),
        "mean_human_word_count": round(sum(human_word_counts) / len(human_word_counts), 3),
        "mean_ai_word_count": round(sum(ai_word_counts) / len(ai_word_counts), 3),
        "rows": rows,
    }
    _write_json(output_path, payload)
    print(f"Wrote caption artifact to {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
