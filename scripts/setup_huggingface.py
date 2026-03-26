from __future__ import annotations

import argparse
from pathlib import Path

from app.bootstrap.huggingface import prepare_huggingface_model


def build_parser() -> argparse.ArgumentParser:
    """Create the CLI parser for Hugging Face model setup."""

    parser = argparse.ArgumentParser(
        description="Download and prepare Hugging Face model assets for StableSteering."
    )
    parser.add_argument(
        "--model-id",
        default="runwayml/stable-diffusion-v1-5",
        help="Hugging Face model repo id to prepare.",
    )
    parser.add_argument(
        "--output-root",
        default="models",
        help="Directory where prepared model snapshots should be stored.",
    )
    parser.add_argument(
        "--cache-dir",
        default=None,
        help="Optional Hugging Face cache directory.",
    )
    parser.add_argument(
        "--revision",
        default=None,
        help="Optional revision, branch, or commit to pin.",
    )
    parser.add_argument(
        "--extra-pattern",
        action="append",
        default=[],
        help="Additional snapshot patterns to download.",
    )
    return parser


def main() -> int:
    """Run the Hugging Face model preparation workflow."""

    parser = build_parser()
    args = parser.parse_args()
    result = prepare_huggingface_model(
        model_id=args.model_id,
        output_root=Path(args.output_root),
        cache_dir=Path(args.cache_dir) if args.cache_dir else None,
        revision=args.revision,
        extra_patterns=args.extra_pattern,
    )
    print("Prepared Hugging Face assets:")
    print(f"  model_id: {result['model_id']}")
    print(f"  model_dir: {result['model_dir']}")
    print(f"  snapshot_path: {result['snapshot_path']}")
    print(f"  manifest_path: {result['manifest_path']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
