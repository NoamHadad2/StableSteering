from __future__ import annotations

import argparse
import json
import random
import re
from pathlib import Path
from typing import Any

import yaml
from datasets import load_dataset
from PIL import Image


REPO_ROOT = Path(__file__).resolve().parents[1]
PAPER_ROOT = REPO_ROOT / "paper"
PROTOCOL_ROOT = PAPER_ROOT / "protocols"

DEFAULT_NEGATIVE_PROMPT = (
    "low detail, blur, distorted anatomy, extra limbs, malformed objects, text, watermark, logo, collage, frame"
)


def _slug(text: str) -> str:
    clean = re.sub(r"[^a-zA-Z0-9]+", "_", text.strip().lower()).strip("_")
    return clean[:48] or "sample"


def _write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _load_yaml(path: Path) -> dict[str, Any]:
    payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"Expected YAML mapping in {path}")
    return payload


def _save_image(image: Image.Image, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    image.convert("RGB").save(path, quality=95)


def _data_root(sample_name: str) -> Path:
    return PAPER_ROOT / "data" / sample_name


def build_subset(*, count: int, seed: int, split: str, sample_name: str, indices: list[int] | None = None) -> dict[str, Any]:
    dataset = load_dataset("jxie/flickr8k", split=split)
    total_available = len(dataset)
    data_root = _data_root(sample_name)

    if indices:
        chosen_indices = sorted(indices)
    else:
        if count > total_available:
            raise ValueError(f"Requested {count} examples but split has only {total_available}")
        rng = random.Random(seed)
        chosen_indices = sorted(rng.sample(range(total_available), count))
    if any(index < 0 or index >= total_available for index in chosen_indices):
        raise ValueError("One or more requested dataset indices are outside the split range")

    images_dir = data_root / "images"
    rows: list[dict[str, Any]] = []
    targets: list[dict[str, Any]] = []
    for order, dataset_index in enumerate(chosen_indices, start=1):
        record = dataset[dataset_index]
        caption = str(record["caption_0"]).strip()
        label = caption[:96]
        target_id = f"flickr8k_{order:02d}_{_slug(caption)}"
        image_path = images_dir / f"{target_id}.jpg"
        _save_image(record["image"], image_path)
        captions = [str(record[f"caption_{idx}"]).strip() for idx in range(5)]
        row = {
            "target_id": target_id,
            "dataset_index": dataset_index,
            "split": split,
            "image_path": str(image_path),
            "caption": caption,
            "caption_0": captions[0],
            "caption_1": captions[1],
            "caption_2": captions[2],
            "caption_3": captions[3],
            "caption_4": captions[4],
        }
        rows.append(row)
        targets.append(
            {
                "id": target_id,
                "label": label,
                "image_url": image_path.resolve().as_uri(),
                "caption": caption,
                "negative_prompt": DEFAULT_NEGATIVE_PROMPT,
                "attribution": (
                    "Flickr8k test split via Hugging Face dataset jxie/flickr8k; "
                    f"dataset index {dataset_index}; caption_0 used as the prompt."
                ),
            }
        )

    manifest = {
        "dataset_name": "Flickr8k",
        "dataset_source": "jxie/flickr8k",
        "dataset_split": split,
        "selection_seed": seed,
        "selected_target_count": len(chosen_indices),
        "total_available_in_split": total_available,
        "selection_indices": chosen_indices,
        "sample_name": sample_name,
        "targets": rows,
    }
    _write_text(data_root / "manifest.json", json.dumps(manifest, indent=2))

    csv_lines = [
        "target_id,dataset_index,split,image_path,caption,caption_0,caption_1,caption_2,caption_3,caption_4"
    ]
    for row in rows:
        escaped = []
        for key in ["target_id", "dataset_index", "split", "image_path", "caption", "caption_0", "caption_1", "caption_2", "caption_3", "caption_4"]:
            value = str(row[key]).replace('"', '""')
            escaped.append(f'"{value}"')
        csv_lines.append(",".join(escaped))
    _write_text(data_root / "manifest.csv", "\n".join(csv_lines) + "\n")

    return {
        "manifest": manifest,
        "targets": targets,
        "data_root": data_root,
    }


def _inject_dataset_metadata(payload: dict[str, Any], *, split: str, seed: int, count: int, total_available: int) -> None:
    payload["dataset"] = {
        "name": "Flickr8k",
        "source": "jxie/flickr8k",
        "split": split,
        "selection_seed": seed,
        "selected_target_count": count,
        "total_available_in_split": total_available,
        "caption_field": "caption_0",
        "selection_note": "Deterministic random subset drawn from the test split for paper evaluation.",
    }


def build_suites(*, targets: list[dict[str, Any]], manifest: dict[str, Any], sample_name: str, oracle_repeats: int, baseline_repeats: int, max_rounds: int) -> None:
    oracle_template = _load_yaml(PROTOCOL_ROOT / "oracle_multimetric_repeated_suite.yaml")
    baseline_template = _load_yaml(PROTOCOL_ROOT / "budget_matched_direct_baselines_suite.yaml")

    oracle_template["suite_name"] = f"oracle_multimetric_repeated_{sample_name}"
    oracle_template["description"] = f"Repeated-seed multi-metric oracle study on the Flickr8k test subset '{sample_name}'."
    oracle_template["repeats_per_target"] = oracle_repeats
    oracle_template["max_rounds"] = max_rounds
    oracle_template["targets"] = targets
    _inject_dataset_metadata(
        oracle_template,
        split=str(manifest["dataset_split"]),
        seed=int(manifest["selection_seed"]),
        count=int(manifest["selected_target_count"]),
        total_available=int(manifest["total_available_in_split"]),
    )

    baseline_template["suite_name"] = f"budget_matched_direct_baselines_{sample_name}"
    baseline_template["description"] = f"Budget-matched direct baseline comparison on the Flickr8k test subset '{sample_name}'."
    baseline_template["repeats_per_target"] = baseline_repeats
    baseline_template["max_rounds"] = max_rounds
    baseline_template["targets"] = targets
    _inject_dataset_metadata(
        baseline_template,
        split=str(manifest["dataset_split"]),
        seed=int(manifest["selection_seed"]),
        count=int(manifest["selected_target_count"]),
        total_available=int(manifest["total_available_in_split"]),
    )

    _write_text(
        PROTOCOL_ROOT / f"oracle_multimetric_repeated_{sample_name}_suite.yaml",
        yaml.safe_dump(oracle_template, sort_keys=False, allow_unicode=False),
    )
    _write_text(
        PROTOCOL_ROOT / f"budget_matched_direct_baselines_{sample_name}_suite.yaml",
        yaml.safe_dump(baseline_template, sort_keys=False, allow_unicode=False),
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Prepare a deterministic Flickr8k evaluation subset and paper protocol YAMLs.")
    parser.add_argument("--count", type=int, default=8, help="Number of Flickr8k test images to include.")
    parser.add_argument("--seed", type=int, default=20260327, help="Selection seed for the deterministic subset.")
    parser.add_argument("--split", default="test", help="Dataset split to use.")
    parser.add_argument("--sample-name", default="flickr8k_eval", help="Folder name under paper/data/ and suffix for generated suite YAMLs.")
    parser.add_argument("--indices", default="", help="Optional comma-separated explicit Flickr8k split indices to use instead of random sampling.")
    parser.add_argument("--oracle-repeats", type=int, default=2, help="Repeats per target for the repeated oracle study.")
    parser.add_argument("--baseline-repeats", type=int, default=2, help="Repeats per target for the direct baseline study.")
    parser.add_argument("--max-rounds", type=int, default=5, help="Rounds per run for both suites.")
    args = parser.parse_args()

    indices = [int(part.strip()) for part in args.indices.split(",") if part.strip()]
    payload = build_subset(count=args.count, seed=args.seed, split=args.split, sample_name=args.sample_name, indices=indices or None)
    build_suites(
        targets=payload["targets"],
        manifest=payload["manifest"],
        sample_name=args.sample_name,
        oracle_repeats=args.oracle_repeats,
        baseline_repeats=args.baseline_repeats,
        max_rounds=args.max_rounds,
    )
    print(payload["data_root"] / "manifest.json")
    print(PROTOCOL_ROOT / f"oracle_multimetric_repeated_{args.sample_name}_suite.yaml")
    print(PROTOCOL_ROOT / f"budget_matched_direct_baselines_{args.sample_name}_suite.yaml")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
