from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont, ImageOps


REPO_ROOT = Path(__file__).resolve().parents[1]
PAPER_ROOT = REPO_ROOT / "paper"
FIGURE_ROOT = PAPER_ROOT / "figures"


@dataclass(frozen=True)
class CuratedRun:
    bundle: str
    policy_id: str
    target_id: str
    row_label: str


CURATED_RUNS = [
    CuratedRun(
        bundle="oracle_progress_followup",
        policy_id="sampler_upgrade",
        target_id="mountain_lake",
        row_label="Mountain lake | two-scale cover sampler",
    ),
    CuratedRun(
        bundle="oracle_inspired_methods",
        policy_id="pl_listwise",
        target_id="black_white_cat_portrait",
        row_label="Cat portrait | Plackett-Luce listwise",
    ),
    CuratedRun(
        bundle="oracle_inspired_methods",
        policy_id="pareto_listwise",
        target_id="red_bicycle_street_photo",
        row_label="Red bicycle | Pareto listwise",
    ),
]


def _font(size: int):
    for candidate in [
        "C:/Windows/Fonts/segoeui.ttf",
        "C:/Windows/Fonts/tahoma.ttf",
        "C:/Windows/Fonts/arial.ttf",
    ]:
        path = Path(candidate)
        if path.exists():
            return ImageFont.truetype(str(path), size=size)
    return ImageFont.load_default()


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def _repo_path(path_str: str) -> Path:
    path = Path(path_str)
    return path if path.is_absolute() else REPO_ROOT / path


def _target_image_path(bundle_root: Path, target_id: str, target_label: str) -> Path:
    targets_dir = bundle_root / "targets"
    target_map = {
        "mountain_lake": "Mountain%20lake.jpg",
        "mountain_lake_landscape": "Mountain%20lake.jpg",
        "cat_portrait_bw": "Cat_portrait_B%26W.JPG",
        "black_white_cat_portrait": "Cat_portrait_B%26W.JPG",
        "red_bicycle": "The%20Red%20Bicycle.%20%2815655615295%29.jpg",
        "red_bicycle_street_photo": "The%20Red%20Bicycle.%20%2815655615295%29.jpg",
    }
    name = target_map.get(target_id)
    if name:
        return targets_dir / name
    normalized = target_label.lower()
    for path in targets_dir.iterdir():
        if normalized.split()[0] in path.name.lower():
            return path
    raise FileNotFoundError(f"Could not resolve target image for {target_id} in {targets_dir}")


def _best_so_far_paths(selected_rows: list[dict[str, str]]) -> dict[int, dict[str, str]]:
    best_clip = float("-inf")
    best_row: dict[str, str] | None = None
    result: dict[int, dict[str, str]] = {}
    for row in sorted(selected_rows, key=lambda r: int(r["round_index"])):
        clip = float(row["clip_score"])
        if clip > best_clip:
            best_clip = clip
            best_row = row
        result[int(row["round_index"])] = dict(best_row) if best_row is not None else dict(row)
    return result


def _load_run_payload(run: CuratedRun) -> dict[str, object]:
    bundle_root = PAPER_ROOT / "results" / run.bundle
    runs_rows = _read_csv(bundle_root / "tables" / "runs.csv")
    candidates_rows = _read_csv(bundle_root / "tables" / "candidates.csv")
    run_row = next(row for row in runs_rows if row["policy_id"] == run.policy_id and row["target_id"] == run.target_id)
    target_path = _target_image_path(bundle_root, run_row["target_id"], run_row["target_label"])
    run_candidates = [row for row in candidates_rows if row["policy_id"] == run.policy_id and row["target_id"] == run.target_id]
    baseline_row = next(
        row for row in run_candidates if row["round_index"] == "1" and str(row.get("baseline_prompt", "")).lower() == "true"
    )
    selected_rows = [row for row in run_candidates if str(row.get("selected", "")).lower() == "true"]
    by_round = _best_so_far_paths(selected_rows)
    max_round = max(by_round)
    checkpoint_round = 4 if 4 in by_round else sorted(by_round)[min(len(by_round) - 1, 2)]
    return {
        "row_label": run.row_label,
        "target_path": target_path,
        "baseline": {
            "label": "Baseline",
            "path": _repo_path(baseline_row["image_path"]),
            "clip": float(baseline_row["clip_score"]),
        },
        "round_1": {
            "label": "Best by R1",
            "path": _repo_path(by_round[1]["image_path"]),
            "clip": float(by_round[1]["clip_score"]),
        },
        "round_mid": {
            "label": f"Best by R{checkpoint_round}",
            "path": _repo_path(by_round[checkpoint_round]["image_path"]),
            "clip": float(by_round[checkpoint_round]["clip_score"]),
        },
        "final": {
            "label": "Final best",
            "path": _repo_path(by_round[max_round]["image_path"]),
            "clip": float(by_round[max_round]["clip_score"]),
        },
    }


def build_figure(output_path: Path) -> None:
    payloads = [_load_run_payload(run) for run in CURATED_RUNS]
    columns = ["Target", "Baseline", "Best by R1", "Best by R4", "Final best"]
    tile_w = 210
    tile_h = 210
    gap = 18
    margin = 24
    header_h = 92
    row_gap = 72
    width = margin * 2 + len(columns) * tile_w + (len(columns) - 1) * gap
    height = margin * 2 + header_h + len(payloads) * tile_h + (len(payloads) - 1) * row_gap + len(payloads) * 52
    canvas = Image.new("RGB", (width, height), "#faf7f0")
    draw = ImageDraw.Draw(canvas)
    title_font = _font(26)
    label_font = _font(18)
    small_font = _font(14)

    draw.text((margin, 18), "Curated oracle-steering progress examples", fill="#2b221a", font=title_font)
    draw.text(
        (margin, 52),
        "Each row shows a target plus baseline and best-so-far checkpoints from a run with clear oracle-measured progress.",
        fill="#6e5a47",
        font=small_font,
    )

    for col_index, label in enumerate(columns):
        x = margin + col_index * (tile_w + gap)
        draw.text((x + 6, margin + header_h - 28), label, fill="#7d4a16", font=label_font)

    for row_index, payload in enumerate(payloads):
        y = margin + header_h + row_index * (tile_h + row_gap + 52)
        x = margin
        target_img = ImageOps.fit(Image.open(payload["target_path"]).convert("RGB"), (tile_w, tile_h), method=Image.Resampling.LANCZOS)
        canvas.paste(target_img, (x, y))
        draw.rounded_rectangle((x, y, x + tile_w, y + tile_h), radius=14, outline="#d6c7b6", width=2)
        draw.text((x + 4, y + tile_h + 8), str(payload["row_label"]), fill="#4e4034", font=small_font)

        for col_offset, key in enumerate(["baseline", "round_1", "round_mid", "final"], start=1):
            x = margin + col_offset * (tile_w + gap)
            panel = payload[key]
            img = ImageOps.fit(Image.open(panel["path"]).convert("RGB"), (tile_w, tile_h), method=Image.Resampling.LANCZOS)
            canvas.paste(img, (x, y))
            draw.rounded_rectangle((x, y, x + tile_w, y + tile_h), radius=14, outline="#d6c7b6", width=2)
            draw.text(
                (x + 4, y + tile_h + 8),
                f"{panel['label']} | CLIP {panel['clip']:.3f}",
                fill="#4e4034",
                font=small_font,
            )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(output_path, quality=95)


def main() -> int:
    FIGURE_ROOT.mkdir(parents=True, exist_ok=True)
    output_path = FIGURE_ROOT / "figure_8_oracle_target_recovery_examples.png"
    build_figure(output_path)
    print(f"Wrote {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
