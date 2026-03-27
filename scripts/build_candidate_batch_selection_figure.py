from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from PIL import Image, ImageDraw, ImageFont


ROOT = Path(r"E:\Projects\StableSteering")
TABLE_PATH = ROOT / "paper" / "results" / "oracle_inspired_methods" / "tables" / "candidates.csv"
OUTPUT_PATH = ROOT / "paper" / "figures" / "figure_2_candidate_batches.png"

POLICY_ID = "qd_sampler"
TARGET_ID = "red_bicycle_street_photo"
SESSION_ID = "ses_1e3c5138b3b2"

BG = "#FFFFFF"
TEXT = "#1A1A1A"
MUTED = "#5A5A5A"
GRID = "#D9D9D9"
SELECTED = "#1A9C52"
CARRIED = "#D08A00"
NEUTRAL = "#B9B9B9"
ARROW = "#4A6FA5"


@dataclass
class Candidate:
    round_index: int
    candidate_index: int
    role: str
    image_path: Path
    clip_score: float
    dinov2_score: float
    carried_forward: bool
    selected: bool


def _load_font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    candidates = []
    if bold:
        candidates = [
            Path(r"C:\Windows\Fonts\arialbd.ttf"),
            Path(r"C:\Windows\Fonts\segoeuib.ttf"),
            Path(r"C:\Windows\Fonts\timesbd.ttf"),
        ]
    else:
        candidates = [
            Path(r"C:\Windows\Fonts\arial.ttf"),
            Path(r"C:\Windows\Fonts\segoeui.ttf"),
            Path(r"C:\Windows\Fonts\times.ttf"),
        ]
    for path in candidates:
        if path.exists():
            return ImageFont.truetype(str(path), size=size)
    return ImageFont.load_default()


def _pretty_role(role: str) -> str:
    mapping = {
        "baseline_prompt": "Baseline",
        "qd_refine": "Refine",
        "qd_forward": "Forward",
        "qd_lateral_plus": "Lateral",
        "qd_far_cover_1": "Far cover",
        "incumbent": "Incumbent",
    }
    return mapping.get(role, role.replace("_", " ").title())


def _read_candidates() -> list[Candidate]:
    rows: list[Candidate] = []
    with TABLE_PATH.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            if (
                row["policy_id"] == POLICY_ID
                and row["target_id"] == TARGET_ID
                and row["session_id"] == SESSION_ID
                and row["round_index"] in {"1", "2"}
            ):
                rows.append(
                    Candidate(
                        round_index=int(row["round_index"]),
                        candidate_index=int(row["candidate_index"]),
                        role=row["sampler_role"],
                        image_path=Path(row["image_path"]),
                        clip_score=float(row["clip_score"]),
                        dinov2_score=float(row["dinov2_score"]),
                        carried_forward=row["carried_forward"].lower() == "true",
                        selected=row["selected"].lower() == "true",
                    )
                )
    rows.sort(key=lambda r: (r.round_index, r.candidate_index))
    return rows


def _fit_image(image_path: Path, size: tuple[int, int]) -> Image.Image:
    image = Image.open(image_path).convert("RGB")
    target_w, target_h = size
    scale = max(target_w / image.width, target_h / image.height)
    resized = image.resize((int(image.width * scale), int(image.height * scale)), Image.Resampling.LANCZOS)
    left = max(0, (resized.width - target_w) // 2)
    top = max(0, (resized.height - target_h) // 2)
    return resized.crop((left, top, left + target_w, top + target_h))


def _draw_multiline(draw: ImageDraw.ImageDraw, xy: tuple[int, int], text: str, font, fill, spacing: int = 4):
    draw.multiline_text(xy, text, font=font, fill=fill, spacing=spacing)


def _tile_border(candidate: Candidate) -> str:
    if candidate.selected:
        return SELECTED
    if candidate.carried_forward:
        return CARRIED
    return NEUTRAL


def _draw_badges(draw: ImageDraw.ImageDraw, x: int, y: int, candidate: Candidate, font):
    badges: list[tuple[str, str]] = []
    if candidate.selected:
        badges.append(("selected", SELECTED))
    if candidate.carried_forward:
        badges.append(("carried", CARRIED))
    cursor_x = x + 10
    for label, color in badges:
        tw = draw.textlength(label, font=font)
        box = (cursor_x, y + 10, cursor_x + tw + 18, y + 10 + 28)
        draw.rounded_rectangle(box, radius=10, fill=color)
        draw.text((cursor_x + 9, y + 14), label, font=font, fill="white")
        cursor_x += int(tw) + 30


def _row_label(round_index: int) -> str:
    if round_index == 1:
        return "Round 1 candidate batch"
    return "Round 2 candidate batch"


def _draw_arrow(draw: ImageDraw.ImageDraw, start: tuple[int, int], end: tuple[int, int]):
    draw.line([start, end], fill=ARROW, width=6)
    head = 16
    ex, ey = end
    draw.polygon(
        [
            (ex, ey),
            (ex - head, ey - head // 2),
            (ex - head, ey + head // 2),
        ],
        fill=ARROW,
    )


def build() -> Path:
    candidates = _read_candidates()
    if not candidates:
        raise RuntimeError("No matching candidates found for the selected archived run.")

    by_round: dict[int, list[Candidate]] = {1: [], 2: []}
    for candidate in candidates:
        by_round[candidate.round_index].append(candidate)

    canvas_w = 2400
    canvas_h = 1320
    margin_x = 90
    top = 70
    tile_w = 340
    tile_h = 250
    tile_gap = 30
    row_gap = 150
    text_gap = 70
    label_col_w = 270

    title_font = _load_font(44, bold=True)
    sub_font = _load_font(28)
    row_font = _load_font(32, bold=True)
    meta_font = _load_font(23)
    badge_font = _load_font(18, bold=True)
    legend_font = _load_font(22)

    canvas = Image.new("RGB", (canvas_w, canvas_h), BG)
    draw = ImageDraw.Draw(canvas)

    title = "Two Consecutive Candidate Batches from One Archived Oracle Run"
    subtitle = (
        "Example from the quality-diversity sampler on the red-bicycle target. "
        "Green borders mark the selected winner for each round; amber marks the carried incumbent."
    )
    draw.text((margin_x, top), title, font=title_font, fill=TEXT)
    _draw_multiline(draw, (margin_x, top + 58), subtitle, sub_font, MUTED)

    legend_y = top + 128
    legend_items = [("selected winner", SELECTED), ("carried incumbent", CARRIED), ("other candidate", NEUTRAL)]
    legend_x = margin_x
    for label, color in legend_items:
        draw.rounded_rectangle((legend_x, legend_y, legend_x + 34, legend_y + 20), radius=8, fill=color)
        draw.text((legend_x + 48, legend_y - 5), label, font=legend_font, fill=MUTED)
        legend_x += 250

    row_top_start = top + 220
    round1_winner_center: tuple[int, int] | None = None
    round2_incumbent_center: tuple[int, int] | None = None

    for round_index in (1, 2):
        row_top = row_top_start + (round_index - 1) * (tile_h + text_gap + row_gap)
        draw.text((margin_x, row_top + 90), _row_label(round_index), font=row_font, fill=TEXT)
        tiles_x = margin_x + label_col_w
        draw.line(
            (tiles_x - 24, row_top + tile_h + text_gap + 20, canvas_w - margin_x, row_top + tile_h + text_gap + 20),
            fill=GRID,
            width=2,
        )

        for idx, candidate in enumerate(by_round[round_index]):
            tile_x = tiles_x + idx * (tile_w + tile_gap)
            tile_y = row_top
            image = _fit_image(candidate.image_path, (tile_w, tile_h))
            canvas.paste(image, (tile_x, tile_y))
            draw.rounded_rectangle(
                (tile_x - 4, tile_y - 4, tile_x + tile_w + 4, tile_y + tile_h + 4),
                radius=14,
                outline=_tile_border(candidate),
                width=8,
            )
            _draw_badges(draw, tile_x, tile_y, candidate, badge_font)

            label = f"{chr(97 + idx)}) {_pretty_role(candidate.role)}"
            stats = f"CLIP {candidate.clip_score:.3f}   DINO {candidate.dinov2_score:.3f}"
            draw.text((tile_x, tile_y + tile_h + 16), label, font=meta_font, fill=TEXT)
            draw.text((tile_x, tile_y + tile_h + 45), stats, font=meta_font, fill=MUTED)

            center = (tile_x + tile_w // 2, tile_y + tile_h // 2)
            if round_index == 1 and candidate.selected:
                round1_winner_center = (center[0], tile_y + tile_h + 6)
            if round_index == 2 and candidate.carried_forward:
                round2_incumbent_center = (center[0], tile_y - 10)

    if round1_winner_center and round2_incumbent_center:
        _draw_arrow(draw, round1_winner_center, round2_incumbent_center)
        mid_x = (round1_winner_center[0] + round2_incumbent_center[0]) // 2 - 84
        mid_y = (round1_winner_center[1] + round2_incumbent_center[1]) // 2 - 12
        draw.rounded_rectangle((mid_x, mid_y, mid_x + 168, mid_y + 34), radius=10, fill="#EDF3FB")
        draw.text((mid_x + 14, mid_y + 6), "carried forward", font=legend_font, fill=ARROW)

    footer = (
        "The figure makes the loop concrete: round 1 exposes a diverse batch, the winner becomes the "
        "incumbent for round 2, and a newly proposed challenger can still overtake that incumbent."
    )
    _draw_multiline(draw, (margin_x, canvas_h - 88), footer, sub_font, MUTED)

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(OUTPUT_PATH, quality=95)
    return OUTPUT_PATH


if __name__ == "__main__":
    out = build()
    print(f"Wrote {out}")
