from __future__ import annotations

import argparse
import base64
import json
import math
import os
import textwrap
import time
from io import BytesIO
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from PIL import Image, ImageDraw, ImageFont


REPO_ROOT = Path(__file__).resolve().parents[1]
PAPER_ROOT = REPO_ROOT / "paper"
FIGURE_ROOT = PAPER_ROOT / "figures"
CONFIG_PATH = Path.home() / ".gemini-imagegen.json"

RAW_DIR = FIGURE_ROOT / "raw_visual_abstract_variants"
RAW_PATH = RAW_DIR / "visual_abstract_method_panel.png"
FINAL_PATH = FIGURE_ROOT / "figure_0_visual_abstract.png"

METHOD_PANEL_PROMPT = (
    "Create a square conceptual illustration for an academic AI paper, with no words, no labels, no numerals, and no watermark. "
    "Show a preference-guided iterative image-refinement mechanism: several small image thumbnails arranged around a subtle circular latent manifold, "
    "a comparison-and-selection node receiving arrows from the thumbnails, and one refined selected thumbnail emerging as the next direction. "
    "The image must look like a serious journal figure rather than promo art: light warm paper background, restrained graphite linework, muted teal and copper accents, "
    "precise geometry, gentle depth, clean negative space, no stage titles, no decorative sci-fi effects, no UI chrome. "
    "The content should be visual and conceptual, not photorealistic: thumbnail cards may depict a stylized tree-like or object-like motif with controlled variation."
)


def _extract_image_bytes(payload: dict[str, Any]) -> bytes:
    for candidate in payload.get("candidates", []):
        content = candidate.get("content", {})
        for part in content.get("parts", []):
            inline = part.get("inlineData") or part.get("inline_data")
            if inline and inline.get("data"):
                return base64.b64decode(inline["data"])
    raise RuntimeError("Gemini response did not contain inline image data.")


def _load_api_key() -> str:
    env_key = os.environ.get("GEMINI_API_KEY")
    if env_key:
        return env_key
    if CONFIG_PATH.exists():
        payload = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
        api_key = payload.get("api_key")
        if api_key:
            return str(api_key)
    raise SystemExit("GEMINI_API_KEY is required, either in the environment or in ~/.gemini-imagegen.json")


def _generate_raw(*, api_key: str, prompt: str, output: Path, model: str = "gemini-3.1-flash-image-preview") -> Path:
    body = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"imageConfig": {"aspectRatio": "1:1"}},
    }
    request = Request(
        url=f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent",
        data=json.dumps(body).encode("utf-8"),
        headers={"Content-Type": "application/json", "x-goog-api-key": api_key},
        method="POST",
    )
    last_error: Exception | None = None
    for attempt in range(3):
        try:
            with urlopen(request, timeout=240) as response:
                payload = json.loads(response.read().decode("utf-8"))
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_bytes(_extract_image_bytes(payload))
            return output
        except HTTPError as exc:
            details = exc.read().decode("utf-8", errors="replace")
            last_error = RuntimeError(f"Gemini API request failed with HTTP {exc.code}: {details}")
        except URLError as exc:
            last_error = RuntimeError(f"Gemini API request failed: {exc.reason}")
        if attempt < 2:
            time.sleep(3 + attempt * 2)
    raise last_error or RuntimeError("Gemini API request failed.")


def _font(size: int, bold: bool = False):
    candidates = [
        "C:/Windows/Fonts/georgiab.ttf" if bold else "C:/Windows/Fonts/georgia.ttf",
        "C:/Windows/Fonts/timesbd.ttf" if bold else "C:/Windows/Fonts/times.ttf",
        "C:/Windows/Fonts/arialbd.ttf" if bold else "C:/Windows/Fonts/arial.ttf",
    ]
    for candidate in candidates:
        path = Path(candidate)
        if path.exists():
            return ImageFont.truetype(str(path), size=size)
    return ImageFont.load_default()


def _draw_wrapped(draw: ImageDraw.ImageDraw, *, text: str, box: tuple[int, int, int, int], font: ImageFont.ImageFont, fill: tuple[int, int, int], line_gap: int = 7) -> None:
    x0, y0, x1, y1 = box
    width = x1 - x0
    avg_char_px = max(8, font.size // 2)
    wrap = max(12, width // avg_char_px)
    lines = textwrap.wrap(text, width=wrap)
    y = y0
    for line in lines:
        bbox = draw.textbbox((0, 0), line, font=font)
        line_h = bbox[3] - bbox[1]
        if y + line_h > y1:
            break
        draw.text((x0, y), line, font=font, fill=fill)
        y += line_h + line_gap


def _draw_column_box(draw: ImageDraw.ImageDraw, box: tuple[int, int, int, int]) -> None:
    draw.rounded_rectangle(box, radius=26, fill=(255, 251, 245), outline=(214, 201, 185), width=2)


def _draw_prompt_panel(draw: ImageDraw.ImageDraw, box: tuple[int, int, int, int], title_font: ImageFont.ImageFont, body_font: ImageFont.ImageFont, small_font: ImageFont.ImageFont) -> None:
    x0, y0, x1, y1 = box
    draw.text((x0 + 28, y0 + 26), "Why refinement is difficult", font=title_font, fill=(31, 27, 22))
    body = (
        "Users can often recognize a better image before they can verbalize the exact prompt revision. "
        "The paper therefore treats refinement as repeated preference-guided search rather than repeated prompt rewriting."
    )
    _draw_wrapped(
        draw,
        text=body,
        box=(x0 + 28, y0 + 76, x1 - 28, y0 + 168),
        font=body_font,
        fill=(56, 47, 39),
    )

    card = (x0 + 42, y0 + 204, x0 + 182, y0 + 394)
    frame = (x0 + 216, y0 + 212, x0 + 392, y0 + 388)
    draw.rounded_rectangle(card, radius=14, fill=(253, 250, 246), outline=(96, 100, 105), width=3)
    draw.rectangle(frame, outline=(96, 100, 105), width=3)

    for idx in range(5):
        y = card[1] + 26 + idx * 28
        draw.line((card[0] + 24, y, card[0] + 116, y), fill=(128, 129, 132), width=3)
        if idx < 3:
            draw.line((card[0] + 24, y + 12, card[0] + 96, y + 12), fill=(164, 164, 166), width=2)
    draw.rectangle((card[0] + 24, card[1] + 24, card[0] + 58, card[1] + 58), outline=(114, 118, 123), width=3)
    draw.line((card[0] + 28, card[1] + 48, card[0] + 54, card[1] + 28), fill=(114, 118, 123), width=3)

    cx = (frame[0] + frame[2]) // 2
    cy = (frame[1] + frame[3]) // 2
    for radius, color in [
        (70, (88, 131, 136)),
        (56, (111, 155, 160)),
        (38, (195, 162, 121)),
        (26, (226, 209, 176)),
    ]:
        draw.ellipse((cx - radius, cy - radius, cx + radius, cy + radius), fill=color)
    draw.line((card[2] + 12, cy, frame[0] - 12, cy), fill=(122, 117, 110), width=4)
    draw.polygon([(frame[0] - 16, cy), (frame[0] - 30, cy - 9), (frame[0] - 30, cy + 9)], fill=(122, 117, 110))

    draw.text((x0 + 44, y0 + 420), "Persistent prompt", font=small_font, fill=(94, 79, 62))
    draw.text((x0 + 216, y0 + 420), "Initial image under latent uncertainty", font=small_font, fill=(94, 79, 62))


def _draw_step_badge(draw: ImageDraw.ImageDraw, center: tuple[int, int], number: int, fill_color: tuple[int, int, int]) -> None:
    cx, cy = center
    draw.ellipse((cx - 18, cy - 18, cx + 18, cy + 18), fill=fill_color, outline=(132, 108, 83), width=2)
    draw.text((cx - 6, cy - 12), str(number), font=_font(20, bold=True), fill=(37, 29, 22))


def _draw_method_panel(canvas: Image.Image, draw: ImageDraw.ImageDraw, box: tuple[int, int, int, int], raw_panel: Image.Image, title_font: ImageFont.ImageFont, body_font: ImageFont.ImageFont, small_font: ImageFont.ImageFont) -> None:
    x0, y0, x1, y1 = box
    draw.text((x0 + 28, y0 + 26), "Preference-guided iterative loop", font=title_font, fill=(31, 27, 22))
    body = (
        "The prompt stays fixed. Each round proposes an exploit-explore batch, elicits comparative feedback, models local preference, "
        "and updates a low-dimensional steering state for the next round."
    )
    _draw_wrapped(
        draw,
        text=body,
        box=(x0 + 28, y0 + 76, x1 - 28, y0 + 160),
        font=body_font,
        fill=(56, 47, 39),
    )

    panel_box = (x0 + 34, y0 + 182, x1 - 34, y0 + 470)
    draw.rounded_rectangle(panel_box, radius=20, fill=(248, 244, 237), outline=(206, 196, 181), width=2)

    raw_panel = raw_panel.convert("RGB")
    raw_panel.thumbnail((panel_box[2] - panel_box[0] - 18, panel_box[3] - panel_box[1] - 18))
    px = panel_box[0] + ((panel_box[2] - panel_box[0]) - raw_panel.width) // 2
    py = panel_box[1] + ((panel_box[3] - panel_box[1]) - raw_panel.height) // 2
    canvas.paste(raw_panel, (px, py))

    step_y = y0 + 522
    step_xs = [x0 + 68, x0 + 188, x0 + 308, x0 + 428]
    step_titles = [
        "Sample",
        "Compare",
        "Model",
        "Update",
    ]
    step_texts = [
        "exploit-explore",
        "feedback",
        "preference",
        "state",
    ]
    step_colors = [
        (222, 192, 157),
        (197, 215, 215),
        (213, 196, 160),
        (171, 202, 196),
    ]
    for index, (sx, title, sub, color) in enumerate(zip(step_xs, step_titles, step_texts, step_colors), start=1):
        _draw_step_badge(draw, (sx, step_y), index, color)
        bbox = draw.textbbox((0, 0), title, font=small_font)
        draw.text((sx - (bbox[2] - bbox[0]) // 2, step_y + 28), title, font=small_font, fill=(39, 34, 29))
        sub_font = _font(14)
        sub_bbox = draw.textbbox((0, 0), sub, font=sub_font)
        draw.text((sx - (sub_bbox[2] - sub_bbox[0]) / 2, step_y + 56), sub, font=sub_font, fill=(104, 89, 73))
    for left, right in zip(step_xs, step_xs[1:]):
        draw.line((left + 18, step_y, right - 18, step_y), fill=(122, 117, 110), width=3)
        draw.polygon([(right - 14, step_y), (right - 26, step_y - 7), (right - 26, step_y + 7)], fill=(122, 117, 110))


def _draw_bar_chart(draw: ImageDraw.ImageDraw, *, box: tuple[int, int, int, int], title: str, values: list[tuple[str, float]], color: tuple[int, int, int], y_range: tuple[float, float]) -> None:
    x0, y0, x1, y1 = box
    draw.text((x0, y0), title, font=_font(22, bold=True), fill=(31, 27, 22))
    chart = (x0 + 6, y0 + 42, x1 - 10, y1 - 34)
    draw.rounded_rectangle((chart[0] - 8, chart[1] - 8, chart[2] + 8, chart[3] + 8), radius=16, fill=(249, 245, 239), outline=(215, 203, 188), width=2)
    axis_x0, axis_y0, axis_x1, axis_y1 = chart
    draw.line((axis_x0 + 40, axis_y0, axis_x0 + 40, axis_y1), fill=(117, 111, 102), width=2)
    draw.line((axis_x0 + 40, axis_y1, axis_x1, axis_y1), fill=(117, 111, 102), width=2)

    vmin, vmax = y_range
    step = (axis_x1 - axis_x0 - 70) / max(1, len(values))
    bar_w = int(step * 0.55)
    for tick in range(4):
        frac = tick / 3
        value = vmax - frac * (vmax - vmin)
        y = axis_y0 + frac * (axis_y1 - axis_y0)
        draw.line((axis_x0 + 36, int(y), axis_x1, int(y)), fill=(231, 225, 216), width=1)
        label = f"{value:.2f}"
        draw.text((axis_x0 - 2, int(y) - 8), label, font=_font(14), fill=(100, 88, 74))

    for idx, (label, value) in enumerate(values):
        x_left = axis_x0 + 56 + idx * step
        frac = (value - vmin) / max(1e-6, (vmax - vmin))
        bar_top = axis_y1 - frac * (axis_y1 - axis_y0)
        draw.rounded_rectangle((x_left, bar_top, x_left + bar_w, axis_y1), radius=10, fill=color, outline=(108, 95, 80), width=2)
        draw.text((x_left + 2, bar_top - 22), f"{value:.3f}", font=_font(14, bold=True), fill=(58, 49, 40))
        lines = label.split(" ")
        ly = axis_y1 + 8
        for part in lines:
            bbox = draw.textbbox((0, 0), part, font=_font(14))
            lw = bbox[2] - bbox[0]
            draw.text((x_left + (bar_w - lw) / 2, ly), part, font=_font(14), fill=(84, 72, 59))
            ly += 16


def _draw_results_panel(draw: ImageDraw.ImageDraw, box: tuple[int, int, int, int], title_font: ImageFont.ImageFont, body_font: ImageFont.ImageFont, small_font: ImageFont.ImageFont) -> None:
    x0, y0, x1, y1 = box
    draw.text((x0 + 28, y0 + 26), "Representative empirical finding", font=title_font, fill=(31, 27, 22))
    body = (
        "In the repeated hidden-target oracle protocol, the best candidate improves over rounds. "
        "The figure highlights the aggregate similarity shift from baseline to final selection."
    )
    _draw_wrapped(
        draw,
        text=body,
        box=(x0 + 28, y0 + 76, x1 - 28, y0 + 162),
        font=body_font,
        fill=(56, 47, 39),
    )

    _draw_bar_chart(
        draw,
        box=(x0 + 28, y0 + 184, x1 - 28, y0 + 380),
        title="Oracle target recovery",
        values=[("Baseline", 0.828), ("Final", 0.881)],
        color=(178, 143, 97),
        y_range=(0.78, 0.90),
    )
    _draw_bar_chart(
        draw,
        box=(x0 + 28, y0 + 404, x1 - 28, y0 + 602),
        title="Image-embedding agreement",
        values=[("Baseline", 0.452), ("Final", 0.595)],
        color=(116, 160, 164),
        y_range=(0.40, 0.62),
    )

    highlight = (
        "The paper studies which choices within the loop drive progress: steering representation, proposal geometry, "
        "preference aggregation, and incumbent policy."
    )
    draw.rounded_rectangle((x0 + 28, y0 + 630, x1 - 28, y1 - 28), radius=18, fill=(247, 242, 235), outline=(214, 201, 185), width=2)
    _draw_wrapped(
        draw,
        text=highlight,
        box=(x0 + 48, y0 + 654, x1 - 48, y1 - 58),
        font=small_font,
        fill=(73, 62, 49),
    )


def _build_visual_abstract(raw_path: Path, output_path: Path) -> Path:
    raw = Image.open(raw_path).convert("RGB")
    canvas = Image.new("RGB", (1920, 1080), (245, 239, 231))
    draw = ImageDraw.Draw(canvas)

    title_font = _font(32, bold=True)
    body_font = _font(22)
    small_font = _font(18)

    draw.rounded_rectangle((28, 22, 1892, 114), radius=24, fill=(255, 252, 247), outline=(214, 201, 185), width=2)
    draw.text((52, 40), "Visual Abstract", font=_font(28, bold=True), fill=(113, 79, 47))
    draw.text((52, 72), "StableSteering: Preference-Guided Iterative Refinement for Text-to-Image Generation", font=title_font, fill=(28, 24, 20))
    draw.text((1470, 42), "Conceptual figure with quantitative highlights", font=_font(18), fill=(116, 101, 83))

    columns = [
        (38, 144, 610, 1024),
        (674, 144, 1246, 1024),
        (1310, 144, 1882, 1024),
    ]
    for box in columns:
        _draw_column_box(draw, box)

    _draw_prompt_panel(draw, columns[0], title_font, body_font, small_font)
    _draw_method_panel(canvas, draw, columns[1], raw, title_font, body_font, small_font)
    _draw_results_panel(draw, columns[2], title_font, body_font, small_font)

    footer = (
        "Conceptual visual abstract generated with Gemini for the central method illustration and composed locally for scientific presentation. "
        "Quantitative highlights correspond to the repeated hidden-target oracle study reported in the paper."
    )
    draw.text((54, 1040), footer, font=_font(16), fill=(100, 86, 70))

    output_path.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(output_path, quality=95)
    return output_path


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate a Gemini-based visual abstract for the StableSteering paper.")
    parser.add_argument("--model", default="gemini-3.1-flash-image-preview")
    args = parser.parse_args()

    api_key = _load_api_key()
    _generate_raw(api_key=api_key, prompt=METHOD_PANEL_PROMPT, output=RAW_PATH, model=args.model)
    _build_visual_abstract(RAW_PATH, FINAL_PATH)
    print(RAW_PATH)
    print(FINAL_PATH)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
