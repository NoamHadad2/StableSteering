from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont, ImageOps


REPO_ROOT = Path(__file__).resolve().parents[1]
PAPER_ROOT = REPO_ROOT / "paper"
FIGURE_ROOT = PAPER_ROOT / "figures"
DATA_ROOT = PAPER_ROOT / "data" / "flickr8k_curated_test_sample"
RUNS_CSV = PAPER_ROOT / "results" / "oracle_caption_metric_extension" / "runs.csv"


@dataclass(frozen=True)
class ExampleRow:
    panel: str
    target_id: str
    target_label: str
    title: str
    slice_name: str
    conditions: tuple[tuple[str, str], ...]


ROWS = [
    ExampleRow(
        panel="Caption-source comparison",
        target_id="flickr8k_02_a_girl_wearing_a_brown_cap_red_sneakers_and_a_da",
        target_label="Girl on rock bench",
        title="Human caption strongest",
        slice_name="caption_source_slice",
        conditions=(
            ("human_caption", "Human caption"),
            ("blip_standard_caption", "BLIP caption"),
            ("blip_detailed_caption", "BLIP detailed"),
        ),
    ),
    ExampleRow(
        panel="Caption-source comparison",
        target_id="flickr8k_08_a_car_is_driven_on_a_dusty_track",
        target_label="Rally car on dusty track",
        title="Detailed BLIP caption strongest",
        slice_name="caption_source_slice",
        conditions=(
            ("human_caption", "Human caption"),
            ("blip_standard_caption", "BLIP caption"),
            ("blip_detailed_caption", "BLIP detailed"),
        ),
    ),
    ExampleRow(
        panel="Oracle-policy comparison",
        target_id="flickr8k_04_a_basketball_player_preparing_to_shoot_the_ball",
        target_label="Basketball jump shot",
        title="CLIP oracle strongest on CLIP",
        slice_name="oracle_metric_slice",
        conditions=(
            ("clip_only", "CLIP oracle"),
            ("multimetric_mix", "Multi-metric"),
            ("siglip_only", "SigLIP oracle"),
        ),
    ),
    ExampleRow(
        panel="Oracle-policy comparison",
        target_id="flickr8k_05_a_little_boy_with_a_blue_shirt_is_wearing_a_helm",
        target_label="Child on bicycle",
        title="SigLIP oracle strongest on DINO",
        slice_name="oracle_metric_slice",
        conditions=(
            ("clip_only", "CLIP oracle"),
            ("multimetric_mix", "Multi-metric"),
            ("siglip_only", "SigLIP oracle"),
        ),
    ),
]


def _font(size: int, bold: bool = False):
    candidates = []
    if bold:
        candidates = [
            "C:/Windows/Fonts/segoeuib.ttf",
            "C:/Windows/Fonts/arialbd.ttf",
            "C:/Windows/Fonts/tahomabd.ttf",
        ]
    else:
        candidates = [
            "C:/Windows/Fonts/segoeui.ttf",
            "C:/Windows/Fonts/arial.ttf",
            "C:/Windows/Fonts/tahoma.ttf",
        ]
    for candidate in candidates:
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


def _target_image(target_id: str) -> Path:
    return DATA_ROOT / "images" / f"{target_id}.jpg"


def _lookup_run(rows: list[dict[str, str]], slice_name: str, target_id: str, condition_id: str) -> dict[str, str]:
    return next(
        row
        for row in rows
        if row["slice_name"] == slice_name and row["target_id"] == target_id and row["condition_id"] == condition_id
    )


def build_figure(output_path: Path) -> None:
    run_rows = _read_csv(RUNS_CSV)
    payloads: list[dict[str, object]] = []
    for row in ROWS:
        items = []
        for condition_id, short_label in row.conditions:
            run = _lookup_run(run_rows, row.slice_name, row.target_id, condition_id)
            items.append(
                {
                    "label": short_label,
                    "path": _repo_path(run["final_winner_image_path"]),
                    "clip": float(run["final_clip_score"]),
                    "siglip": float(run["final_siglip_score"]),
                    "dinov2": float(run["final_dinov2_score"]),
                }
            )
        payloads.append(
            {
                "panel": row.panel,
                "title": row.title,
                "target_label": row.target_label,
                "target_path": _target_image(row.target_id),
                "items": items,
            }
        )

    tile_w = 230
    tile_h = 180
    gap = 16
    margin = 28
    panel_gap = 56
    row_gap = 62
    text_block_h = 64
    columns = 4
    width = margin * 2 + columns * tile_w + (columns - 1) * gap
    height = margin * 2 + 90 + 2 * (34 + 2 * (tile_h + text_block_h) + row_gap) + panel_gap
    canvas = Image.new("RGB", (width, height), "#faf7f0")
    draw = ImageDraw.Draw(canvas)
    title_font = _font(28, bold=True)
    panel_font = _font(22, bold=True)
    label_font = _font(17, bold=True)
    small_font = _font(14)

    draw.text((margin, 16), "Representative examples from the caption-and-metric oracle extension", fill="#2b221a", font=title_font)
    draw.text(
        (margin, 52),
        "Two caption-source rows and two oracle-policy rows from the curated Flickr8k subset. Scores are final per-run endpoints.",
        fill="#6e5a47",
        font=small_font,
    )

    y = margin + 92
    for panel_name in ("Caption-source comparison", "Oracle-policy comparison"):
        draw.text((margin, y), panel_name, fill="#7d4a16", font=panel_font)
        y += 34
        panel_rows = [payload for payload in payloads if payload["panel"] == panel_name]
        for payload in panel_rows:
            x = margin
            row_y = y
            # Target column.
            target_img = ImageOps.fit(
                Image.open(payload["target_path"]).convert("RGB"),
                (tile_w, tile_h),
                method=Image.Resampling.LANCZOS,
            )
            canvas.paste(target_img, (x, row_y))
            draw.rounded_rectangle((x, row_y, x + tile_w, row_y + tile_h), radius=14, outline="#d6c7b6", width=2)
            draw.text((x + 4, row_y + tile_h + 8), str(payload["target_label"]), fill="#3c332a", font=label_font)
            draw.text((x + 4, row_y + tile_h + 31), str(payload["title"]), fill="#6e5a47", font=small_font)

            for index, item in enumerate(payload["items"], start=1):
                x = margin + index * (tile_w + gap)
                image = ImageOps.fit(
                    Image.open(item["path"]).convert("RGB"),
                    (tile_w, tile_h),
                    method=Image.Resampling.LANCZOS,
                )
                canvas.paste(image, (x, row_y))
                draw.rounded_rectangle((x, row_y, x + tile_w, row_y + tile_h), radius=14, outline="#d6c7b6", width=2)
                draw.text((x + 4, row_y + tile_h + 8), str(item["label"]), fill="#3c332a", font=label_font)
                if panel_name == "Caption-source comparison":
                    metric_text = f"CLIP {item['clip']:.3f} | DINO {item['dinov2']:.3f}"
                else:
                    metric_text = f"CLIP {item['clip']:.3f} | SigLIP {item['siglip']:.3f}"
                draw.text((x + 4, row_y + tile_h + 31), metric_text, fill="#6e5a47", font=small_font)

            y += tile_h + text_block_h + row_gap
        y += panel_gap - row_gap

    output_path.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(output_path, quality=95)


def main() -> int:
    output_path = FIGURE_ROOT / "figure_23_caption_metric_examples.png"
    build_figure(output_path)
    print(f"Wrote {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
