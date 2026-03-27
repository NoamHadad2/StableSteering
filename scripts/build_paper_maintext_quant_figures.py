from __future__ import annotations

import csv
from pathlib import Path

import matplotlib.pyplot as plt


REPO_ROOT = Path(__file__).resolve().parents[1]
PAPER_ROOT = REPO_ROOT / "paper"
FIGURE_ROOT = PAPER_ROOT / "figures"


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def _style_axes(axis) -> None:
    axis.grid(axis="y", alpha=0.22, linestyle="--", linewidth=0.8)
    axis.set_axisbelow(True)
    axis.spines["top"].set_visible(False)
    axis.spines["right"].set_visible(False)


def _two_metric_chart(
    rows: list[dict[str, str]],
    *,
    label_key: str,
    clip_key: str,
    dino_key: str,
    output_path: Path,
    title: str,
) -> None:
    labels = [row[label_key] for row in rows]
    clip_values = [float(row[clip_key]) for row in rows]
    dino_values = [float(row[dino_key]) for row in rows]
    x = range(len(labels))
    width = 0.38

    fig, axes = plt.subplots(1, 2, figsize=(12.2, 4.8), constrained_layout=True)
    for axis, values, color, metric_title in [
        (axes[0], clip_values, "#2358c4", "Final CLIP similarity"),
        (axes[1], dino_values, "#1d8a6b", "Final DINOv2 similarity"),
    ]:
        bars = axis.bar(list(x), values, color=color, width=0.72)
        axis.set_title(metric_title, fontsize=12)
        axis.set_xticks(list(x), labels, rotation=18, ha="right")
        _style_axes(axis)
        for bar, value in zip(bars, values, strict=True):
            axis.text(bar.get_x() + bar.get_width() / 2, value + 0.008, f"{value:.3f}", ha="center", va="bottom", fontsize=9)

    fig.suptitle(title, fontsize=14)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output_path, format="svg", bbox_inches="tight")
    plt.close(fig)


def _progress_chart(
    rows: list[dict[str, str]],
    *,
    output_path: Path,
    title: str,
) -> None:
    labels = [row["policy_label"] for row in rows]
    metrics = [
        ("mean_final_clip", "Final CLIP", "#2358c4"),
        ("mean_final_dinov2", "Final DINOv2", "#1d8a6b"),
        ("mean_late_improvement_rounds", "Late improvements", "#b97219"),
        ("plateau_run_share", "Plateau share", "#8c4b97"),
    ]
    x = range(len(labels))

    fig, axes = plt.subplots(2, 2, figsize=(12.8, 8.0), constrained_layout=True)
    axes_flat = axes.flatten()
    for axis, (key, metric_title, color) in zip(axes_flat, metrics, strict=True):
        values = [float(row[key]) for row in rows]
        bars = axis.bar(list(x), values, color=color, width=0.72)
        axis.set_title(metric_title, fontsize=12)
        axis.set_xticks(list(x), labels, rotation=18, ha="right")
        _style_axes(axis)
        for bar, value in zip(bars, values, strict=True):
            axis.text(bar.get_x() + bar.get_width() / 2, value + max(values + [0.1]) * 0.03, f"{value:.2f}", ha="center", va="bottom", fontsize=9)

    fig.suptitle(title, fontsize=14)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output_path, format="svg", bbox_inches="tight")
    plt.close(fig)


def build_steering_mode() -> None:
    rows = _read_csv(PAPER_ROOT / "results" / "steering_mode_comparison" / "tables" / "policy_summary.csv")
    _two_metric_chart(
        rows,
        label_key="policy_label",
        clip_key="mean_final_best_clip",
        dino_key="mean_final_best_dinov2",
        output_path=FIGURE_ROOT / "figure_19_steering_mode_curve.svg",
        title="Steering-direction comparison at final recovery",
    )


def build_method_extension() -> None:
    rows = _read_csv(PAPER_ROOT / "results" / "method_extension_comparison" / "tables" / "policy_summary.csv")
    for slice_id, output_name, title in [
        ("sampler_slice", "figure_13_sampler_extension_curve.svg", "Sampler extension comparison at final recovery"),
        ("preference_slice", "figure_14_preference_extension_curve.svg", "Preference-model extension comparison at final recovery"),
        ("oracle_slice", "figure_15_oracle_policy_curve.svg", "Oracle-policy comparison at final recovery"),
    ]:
        slice_rows = [row for row in rows if row["slice_id"] == slice_id]
        _two_metric_chart(
            slice_rows,
            label_key="policy_label",
            clip_key="mean_final_best_clip",
            dino_key="mean_final_best_dinov2",
            output_path=FIGURE_ROOT / output_name,
            title=title,
        )


def build_oracle_policy_figure(results_dir: str, output_name: str, title: str) -> None:
    rows = _read_csv(PAPER_ROOT / "results" / results_dir / "tables" / "policy_summary.csv")
    _progress_chart(rows, output_path=FIGURE_ROOT / output_name, title=title)


def main() -> int:
    FIGURE_ROOT.mkdir(parents=True, exist_ok=True)
    build_steering_mode()
    build_method_extension()
    build_oracle_policy_figure(
        "oracle_progress_diagnosis",
        "figure_16_oracle_progress_diagnosis.svg",
        "Oracle progress diagnosis summary",
    )
    build_oracle_policy_figure(
        "oracle_inspired_methods",
        "figure_17_oracle_inspired_methods.svg",
        "Inspired-method comparison summary",
    )
    build_oracle_policy_figure(
        "oracle_plateau_reformulation",
        "figure_18_oracle_plateau_reformulation.svg",
        "Restart-style reformulation summary",
    )
    print(f"Wrote summary figures to {FIGURE_ROOT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
