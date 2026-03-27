from __future__ import annotations

import csv
import random
import shutil
from pathlib import Path
from typing import Any

import markdown


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _paper_root() -> Path:
    return _repo_root() / "paper"


def _baseline_root() -> Path:
    return _paper_root() / "results" / "baseline_matrix"


def _output_root() -> Path:
    return _paper_root() / "results" / "human_pairwise_evaluation"


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def _write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fieldnames})


def _write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _markdown_to_html(title: str, markdown_text: str, output_path: Path) -> None:
    body = markdown.markdown(markdown_text, extensions=["extra", "tables", "sane_lists"], output_format="html5")
    html_payload = f"""<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>{title}</title>
    <style>
      body {{ margin: 0; background: #f3ece2; color: #201a15; font-family: Georgia, "Times New Roman", serif; }}
      main {{ max-width: 1100px; margin: 0 auto; padding: 28px 18px 48px; }}
      article {{ background: #fffdfa; border: 1px solid #d9cdbc; border-radius: 18px; padding: 34px 38px 42px; }}
      p, li {{ line-height: 1.66; text-align: justify; }}
      .pair {{ display: grid; grid-template-columns: 1fr 1fr; gap: 18px; margin: 28px 0; }}
      .card {{ border: 1px solid #d9cdbc; border-radius: 12px; background: white; padding: 10px; }}
      .card img {{ width: 100%; border-radius: 10px; display: block; }}
      .meta {{ font-size: 0.95rem; color: #4a4037; margin-top: 0.5rem; }}
    </style>
  </head>
  <body>
    <main><article>{body}</article></main>
  </body>
</html>
"""
    _write_text(output_path, html_payload)


def _resolve_image(run_id: str, candidates: list[dict[str, str]], mode: str) -> dict[str, str]:
    rows = [row for row in candidates if row["run_id"] == run_id]
    if mode == "selected_latest":
        selected = [row for row in rows if str(row["selected"]).lower() == "true"]
        selected.sort(key=lambda row: int(row["round_index"]), reverse=True)
        return selected[0]
    if mode == "selected_first":
        selected = [row for row in rows if str(row["selected"]).lower() == "true"]
        selected.sort(key=lambda row: int(row["round_index"]))
        return selected[0]
    if mode == "no_update_heuristic":
        passed = [row for row in rows if row.get("failed_checks", "[]") in ("[]", "")]
        pool = passed or rows
        pool.sort(key=lambda row: float(row.get("edge_mean", "0") or 0.0), reverse=True)
        return pool[0]
    raise ValueError(f"Unsupported mode: {mode}")


def main() -> int:
    baseline_root = _baseline_root()
    output_root = _output_root()
    candidates = _read_csv(baseline_root / "tables" / "candidates.csv")
    pairs_dir = output_root / "pairs"
    pairs_dir.mkdir(parents=True, exist_ok=True)

    prompt_configs = [
        ("product_hero_shot", "Product hero shot"),
        ("portrait_character", "Portrait / character"),
        ("landscape_environment", "Landscape / environment"),
    ]
    randomizer = random.Random(42)
    pair_rows: list[dict[str, Any]] = []
    html_blocks: list[str] = []
    pair_index = 1
    for prompt_id, prompt_label in prompt_configs:
        prompt_run = f"{prompt_id}__prompt_only_manual__r1"
        no_update_run = f"{prompt_id}__no_update_random_sampling__r1"
        steering_run = f"{prompt_id}__stablesteering_default__r1"

        prompt_row = _resolve_image(prompt_run, candidates, "selected_first")
        no_update_row = _resolve_image(no_update_run, candidates, "no_update_heuristic")
        steering_row = _resolve_image(steering_run, candidates, "selected_latest")

        comparisons = [
            ("prompt_only_vs_stable", "Prompt-only baseline", prompt_row, "StableSteering final", steering_row),
            ("no_update_vs_stable", "No-update representative", no_update_row, "StableSteering final", steering_row),
        ]
        for comparison_slug, left_label, left_row, right_label, right_row in comparisons:
            left_source = baseline_root / "runs" / left_row["run_id"] / "runtime" / "artifacts" / Path(left_row["image_path"]).name
            right_source = baseline_root / "runs" / right_row["run_id"] / "runtime" / "artifacts" / Path(right_row["image_path"]).name
            left_copy = pairs_dir / f"pair_{pair_index:02d}_left{left_source.suffix}"
            right_copy = pairs_dir / f"pair_{pair_index:02d}_right{right_source.suffix}"
            shutil.copy2(left_source, left_copy)
            shutil.copy2(right_source, right_copy)

            if randomizer.random() < 0.5:
                left_display_path, left_policy = left_copy.name, left_label
                right_display_path, right_policy = right_copy.name, right_label
            else:
                left_display_path, left_policy = right_copy.name, right_label
                right_display_path, right_policy = left_copy.name, left_label

            pair_id = f"pair_{pair_index:02d}"
            pair_rows.append(
                {
                    "pair_id": pair_id,
                    "prompt_id": prompt_id,
                    "prompt_label": prompt_label,
                    "comparison_type": comparison_slug,
                    "left_policy_label": left_policy,
                    "right_policy_label": right_policy,
                    "left_image": f"pairs/{left_display_path}",
                    "right_image": f"pairs/{right_display_path}",
                    "judge_question": "Which image better satisfies the prompt while remaining visually coherent?",
                }
            )
            html_blocks.append(
                f"""
### {pair_id}: {prompt_label} / {comparison_slug}

Question: Which image better satisfies the prompt while remaining visually coherent?

<div class="pair">
  <div class="card">
    <img src="pairs/{left_display_path}" alt="{pair_id} left">
    <div class="meta">Side: left</div>
  </div>
  <div class="card">
    <img src="pairs/{right_display_path}" alt="{pair_id} right">
    <div class="meta">Side: right</div>
  </div>
</div>
"""
            )
            pair_index += 1

    _write_csv(
        output_root / "pairs.csv",
        pair_rows,
        [
            "pair_id",
            "prompt_id",
            "prompt_label",
            "comparison_type",
            "left_policy_label",
            "right_policy_label",
            "left_image",
            "right_image",
            "judge_question",
        ],
    )
    _write_csv(output_root / "annotations_blank.csv", [], ["pair_id", "evaluator_id", "chosen_side", "confidence_1_to_5", "notes"])

    protocol_md = (
        "# Human Pairwise Evaluation Package\n\n"
        "This directory packages a small pairwise human-evaluation pilot around the current paper artifacts.\n\n"
        "## Included materials\n\n"
        f"- curated pairs: `{len(pair_rows)}`\n"
        "- blank annotation sheet: `annotations_blank.csv`\n"
        "- pair manifest: `pairs.csv`\n"
        "- browser-friendly preview: `pairwise_review.html`\n\n"
        "## Collection rule\n\n"
        "Judges should answer: **Which image better satisfies the prompt while remaining visually coherent?**\n\n"
        "Allowed responses:\n\n"
        "- `left`\n"
        "- `right`\n"
        "- `tie`\n"
        "- `invalid`\n\n"
        "## Current results status\n\n"
        "- collected annotations: `0`\n"
        "- this package is protocol-ready but does not yet contain human judgments\n"
    )
    _write_text(output_root / "README.md", protocol_md)
    _write_text(
        output_root / "analysis_summary.md",
        "# Human Pairwise Evaluation Analysis\n\nNo human annotations have been collected yet. The package currently provides a protocol-ready pair set, blank annotation sheet, and browser preview for later collection.\n",
    )
    _markdown_to_html("Human Pairwise Evaluation Package", protocol_md + "\n" + "\n".join(html_blocks), output_root / "pairwise_review.html")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
