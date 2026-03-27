from __future__ import annotations

import csv
import random
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


def _mean_ci(values: list[float], *, bootstrap_samples: int = 2000) -> tuple[float, float, float]:
    if not values:
        raise ValueError("Cannot compute confidence interval for an empty sample.")
    if len(values) == 1:
        value = values[0]
        return value, value, value

    mean_value = sum(values) / len(values)
    rng = random.Random(0)
    boot_means: list[float] = []
    for _ in range(bootstrap_samples):
        sample = [values[rng.randrange(len(values))] for _ in values]
        boot_means.append(sum(sample) / len(sample))
    boot_means.sort()
    low_index = int(0.025 * (bootstrap_samples - 1))
    high_index = int(0.975 * (bootstrap_samples - 1))
    return mean_value, boot_means[low_index], boot_means[high_index]


def _group_metric_rows(
    rows: list[dict[str, str]],
    *,
    label_key: str,
    group_key: str,
    metric_keys: list[str],
) -> list[dict[str, object]]:
    grouped: dict[str, dict[str, object]] = {}
    for row in rows:
        group_value = row[group_key]
        if group_value not in grouped:
            grouped[group_value] = {
                "group": group_value,
                "label": row[label_key],
                "values": {metric_key: [] for metric_key in metric_keys},
            }
        for metric_key in metric_keys:
            grouped[group_value]["values"][metric_key].append(float(row[metric_key]))
    return list(grouped.values())


def _two_metric_chart_from_runs(
    rows: list[dict[str, str]],
    *,
    label_key: str,
    group_key: str,
    clip_key: str,
    dino_key: str,
    output_path: Path,
    title: str,
) -> None:
    grouped_rows = _group_metric_rows(
        rows,
        label_key=label_key,
        group_key=group_key,
        metric_keys=[clip_key, dino_key],
    )
    labels = [row["label"] for row in grouped_rows]
    clip_triplets = [_mean_ci(row["values"][clip_key]) for row in grouped_rows]
    dino_triplets = [_mean_ci(row["values"][dino_key]) for row in grouped_rows]
    clip_values = [triplet[0] for triplet in clip_triplets]
    dino_values = [triplet[0] for triplet in dino_triplets]
    x = range(len(labels))

    fig, axes = plt.subplots(1, 2, figsize=(12.2, 4.8), constrained_layout=True)
    for axis, values, triplets, color, metric_title in [
        (axes[0], clip_values, clip_triplets, "#2358c4", "Final CLIP similarity"),
        (axes[1], dino_values, dino_triplets, "#1d8a6b", "Final DINOv2 similarity"),
    ]:
        lower_errors = [max(0.0, mean_value - ci_low) for mean_value, ci_low, _ in triplets]
        upper_errors = [max(0.0, ci_high - mean_value) for mean_value, _, ci_high in triplets]
        bars = axis.bar(
            list(x),
            values,
            color=color,
            width=0.72,
            yerr=[lower_errors, upper_errors],
            ecolor="#2f2f2f",
            capsize=4,
            linewidth=0.8,
        )
        axis.set_title(metric_title, fontsize=12)
        axis.set_xticks(list(x), labels, rotation=18, ha="right")
        _style_axes(axis)
        for bar, value in zip(bars, values, strict=True):
            axis.text(bar.get_x() + bar.get_width() / 2, value + 0.008, f"{value:.3f}", ha="center", va="bottom", fontsize=9)

    fig.suptitle(title, fontsize=14)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output_path, format="svg", bbox_inches="tight")
    plt.close(fig)


def _progress_chart_from_runs(
    rows: list[dict[str, str]],
    *,
    label_key: str,
    group_key: str,
    output_path: Path,
    title: str,
) -> None:
    # Derived metrics use run-level rows, then compute mean plus bootstrap CI across runs.
    for row in rows:
        row["plateau_indicator"] = "1.0" if row["last_three_plateau"].lower() == "true" else "0.0"
    grouped_rows = _group_metric_rows(
        rows,
        label_key=label_key,
        group_key=group_key,
        metric_keys=[
            "final_clip",
            "final_dinov2",
            "late_improvement_rounds",
            "plateau_indicator",
        ],
    )
    labels = [row["label"] for row in grouped_rows]
    metrics = [
        ("final_clip", "Final CLIP", "#2358c4"),
        ("final_dinov2", "Final DINOv2", "#1d8a6b"),
        ("late_improvement_rounds", "Late improvements", "#b97219"),
        ("plateau_indicator", "Plateau share", "#8c4b97"),
    ]
    x = range(len(labels))

    fig, axes = plt.subplots(2, 2, figsize=(12.8, 8.0), constrained_layout=True)
    axes_flat = axes.flatten()
    for axis, (key, metric_title, color) in zip(axes_flat, metrics, strict=True):
        triplets = [_mean_ci(row["values"][key]) for row in grouped_rows]
        values = [triplet[0] for triplet in triplets]
        lower_errors = [max(0.0, mean_value - ci_low) for mean_value, ci_low, _ in triplets]
        upper_errors = [max(0.0, ci_high - mean_value) for mean_value, _, ci_high in triplets]
        bars = axis.bar(
            list(x),
            values,
            color=color,
            width=0.72,
            yerr=[lower_errors, upper_errors],
            ecolor="#2f2f2f",
            capsize=4,
            linewidth=0.8,
        )
        axis.set_title(metric_title, fontsize=12)
        axis.set_xticks(list(x), labels, rotation=18, ha="right")
        _style_axes(axis)
        offset = max(values + [0.1]) * 0.04
        for bar, value in zip(bars, values, strict=True):
            label = f"{value:.2f}" if value < 10 else f"{value:.1f}"
            axis.text(bar.get_x() + bar.get_width() / 2, value + offset, label, ha="center", va="bottom", fontsize=9)

    fig.suptitle(title, fontsize=14)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output_path, format="svg", bbox_inches="tight")
    plt.close(fig)


def build_steering_mode() -> None:
    rows = _read_csv(PAPER_ROOT / "results" / "steering_mode_comparison" / "tables" / "runs.csv")
    _two_metric_chart_from_runs(
        rows,
        label_key="policy_label",
        group_key="policy_id",
        clip_key="final_best_clip",
        dino_key="final_best_dinov2",
        output_path=FIGURE_ROOT / "figure_19_steering_mode_curve.svg",
        title="Steering-direction comparison at final recovery",
    )


def build_method_extension() -> None:
    rows = _read_csv(PAPER_ROOT / "results" / "method_extension_comparison" / "tables" / "runs.csv")
    for slice_id, output_name, title in [
        ("sampler_slice", "figure_13_sampler_extension_curve.svg", "Sampler extension comparison at final recovery"),
        ("preference_slice", "figure_14_preference_extension_curve.svg", "Preference-model extension comparison at final recovery"),
        ("oracle_slice", "figure_15_oracle_policy_curve.svg", "Oracle-policy comparison at final recovery"),
    ]:
        slice_rows = [row for row in rows if row["slice_id"] == slice_id]
        _two_metric_chart_from_runs(
            slice_rows,
            label_key="policy_label",
            group_key="policy_id",
            clip_key="final_best_clip",
            dino_key="final_best_dinov2",
            output_path=FIGURE_ROOT / output_name,
            title=title,
        )


def build_oracle_policy_figure(results_dir: str, output_name: str, title: str) -> None:
    rows = _read_csv(PAPER_ROOT / "results" / results_dir / "tables" / "runs.csv")
    _progress_chart_from_runs(
        rows,
        label_key="policy_label",
        group_key="policy_id",
        output_path=FIGURE_ROOT / output_name,
        title=title,
    )


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
