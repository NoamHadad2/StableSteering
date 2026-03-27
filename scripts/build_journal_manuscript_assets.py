from __future__ import annotations

import csv
import shutil
from pathlib import Path

import matplotlib.pyplot as plt
from PIL import Image, ImageDraw, ImageFont, ImageOps


REPO_ROOT = Path(__file__).resolve().parents[1]
PAPER_ROOT = REPO_ROOT / "paper"
FIGURE_ROOT = PAPER_ROOT / "figures"
DOC_FIGURE_ROOT = REPO_ROOT / "docs" / "assets" / "illustrations"
CASE_STUDY_ROOT = REPO_ROOT / "output" / "examples" / "real_e2e_example_run"


def ensure_figure_root() -> None:
    FIGURE_ROOT.mkdir(parents=True, exist_ok=True)


def copy_static_svgs() -> None:
    copies = [
        ("runtime_flow.svg", "figure_1_system_overview.svg"),
        ("session_lifecycle.svg", "figure_2_session_lifecycle.svg"),
        ("config_to_generation.svg", "figure_3_configuration_to_generation.svg"),
    ]
    for source_name, output_name in copies:
        shutil.copy2(DOC_FIGURE_ROOT / source_name, FIGURE_ROOT / output_name)


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


def _read_csv_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def _load_case_study_panels() -> list[tuple[str, str]]:
    return [
        ("Baseline prompt render", "cand_52bef0c2b1dd.png"),
        ("Round 1 selected direction", "cand_f830b6669999.png"),
        ("Round 3 refinement", "cand_8e910d46a02d.png"),
        ("Final incumbent", "cand_4c52b3f7c949.png"),
    ]


def build_case_study_progression() -> None:
    panels = _load_case_study_panels()

    tile_w = 320
    tile_h = 320
    gap = 18
    margin = 24
    header_h = 84
    footer_h = 70
    width = margin * 2 + len(panels) * tile_w + (len(panels) - 1) * gap
    height = margin * 2 + header_h + tile_h + footer_h
    canvas = Image.new("RGB", (width, height), "#faf6ee")
    draw = ImageDraw.Draw(canvas)
    title_font = _font(28)
    label_font = _font(18)
    small_font = _font(15)

    draw.text((margin, 18), "End-to-end qualitative case-study montage", fill="#2b221a", font=title_font)
    draw.text(
        (margin, 52),
        "Baseline, first selected direction, mid-run refinement, and final incumbent from one preserved session.",
        fill="#6e5a47",
        font=small_font,
    )

    y = margin + header_h
    for idx, (label, image_name) in enumerate(panels):
        x = margin + idx * (tile_w + gap)
        image_path = CASE_STUDY_ROOT / "images" / image_name
        tile = Image.open(image_path).convert("RGB")
        tile = ImageOps.fit(tile, (tile_w, tile_h), method=Image.Resampling.LANCZOS)
        canvas.paste(tile, (x, y))
        draw.rounded_rectangle((x, y, x + tile_w, y + tile_h), radius=16, outline="#d6c7b6", width=2)
        draw.text((x + 10, y + tile_h + 10), label, fill="#7d4a16", font=label_font)
        note = "Five-round preserved session" if idx == 0 else ""
        if note:
            draw.text((x + 10, y + tile_h + 36), note, fill="#53463a", font=small_font)

    canvas.save(FIGURE_ROOT / "figure_4_case_study_progression.png", quality=95)


def build_bundle_coverage() -> None:
    bundle_specs = [
        ("baseline_matrix", "Minimal baseline"),
        ("seed_policy_slice", "Seed-policy slice"),
        ("updater_ablation", "Updater ablation"),
    ]
    bundle_rows = []
    for bundle_name, label in bundle_specs:
        rows = _read_csv_rows(PAPER_ROOT / "results" / bundle_name / "analysis" / "policy_summary.csv")
        bundle_rows.append(
            {
                "label": label,
                "run_count": sum(int(row["run_count"]) for row in rows),
                "round_count": sum(int(row["round_count"]) for row in rows),
                "candidate_count": sum(int(row["candidate_count"]) for row in rows),
            }
        )

    labels = [row["label"] for row in bundle_rows]
    figure, axes = plt.subplots(1, 3, figsize=(13.5, 4.2), constrained_layout=True)
    for axis, key, title in zip(
        axes,
        ["run_count", "round_count", "candidate_count"],
        ["Completed runs", "Recorded rounds", "Candidate rows"],
        strict=True,
    ):
        values = [row[key] for row in bundle_rows]
        bars = axis.bar(labels, values, color="#8a4f14")
        axis.set_title(title, fontsize=12)
        axis.tick_params(axis="x", rotation=18)
        axis.grid(axis="y", alpha=0.25, linestyle="--")
        axis.set_axisbelow(True)
        for bar, value in zip(bars, values, strict=True):
            axis.text(bar.get_x() + bar.get_width() / 2, value + max(values) * 0.02, str(value), ha="center", va="bottom", fontsize=10)

    figure.suptitle("Coverage of the executed evaluation bundles", fontsize=14)
    figure.savefig(FIGURE_ROOT / "figure_5_bundle_coverage.png", dpi=220, bbox_inches="tight")
    plt.close(figure)


def build_baseline_workflow_summary() -> None:
    rows = _read_csv_rows(PAPER_ROOT / "results" / "baseline_matrix" / "tables" / "baseline_summary.csv")
    labels = [row["baseline_label"] for row in rows]
    rounds = [float(row["avg_rounds_per_run"]) for row in rows]
    feedback = [float(row["avg_feedback_events_per_run"]) for row in rows]
    palette = ["#6b86b3", "#b6863c", "#7c628f"]

    figure, axes = plt.subplots(1, 2, figsize=(12.2, 4.5), constrained_layout=True)
    for axis, values, title, ylabel in [
        (axes[0], rounds, "Average rounds per run", "Rounds"),
        (axes[1], feedback, "Average feedback events per run", "Feedback events"),
    ]:
        axis.bar(labels, values, color=palette)
        axis.set_title(title, fontsize=12)
        axis.set_ylabel(ylabel)
        axis.tick_params(axis="x", rotation=18)
        axis.grid(axis="y", alpha=0.25, linestyle="--")
        axis.set_axisbelow(True)

    figure.suptitle("Workflow structure in the repeated minimal baseline matrix", fontsize=14)
    figure.savefig(FIGURE_ROOT / "figure_6_baseline_workflow_summary.png", dpi=220, bbox_inches="tight")
    plt.close(figure)


def main() -> int:
    ensure_figure_root()
    copy_static_svgs()
    build_case_study_progression()
    build_bundle_coverage()
    build_baseline_workflow_summary()
    print(f"Wrote manuscript figures to {FIGURE_ROOT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
