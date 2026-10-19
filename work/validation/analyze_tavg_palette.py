#!/usr/bin/env python3
"""Audit the provisional mean-temperature palette on all twelve monthly normals."""

from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.colors import LinearSegmentedColormap, Normalize

from build_pilot_tiles import (
    ROOT,
    TEMPERATURE_STOPS,
    read_relief_and_water,
    read_temperature_normal,
)


OUTPUT = ROOT / "outputs"
MONTH_LABELS = [
    "jan", "fév", "mar", "avr", "mai", "juin",
    "juil", "août", "sep", "oct", "nov", "déc",
]
QUANTILES = [0, 0.1, 1, 5, 10, 25, 50, 75, 90, 95, 99, 99.9, 100]
STOP_VALUES = np.array([stop[0] for stop in TEMPERATURE_STOPS], dtype="float64")
BIN_EDGES = np.concatenate(([-np.inf], STOP_VALUES, [np.inf]))


def interval_label(left: float, right: float) -> str:
    if np.isneginf(left):
        return f"< {right:g}"
    if np.isposinf(right):
        return f">= {left:g}"
    return f"{left:g} à < {right:g}"


def palette_colormap() -> LinearSegmentedColormap:
    minimum, maximum = STOP_VALUES[0], STOP_VALUES[-1]
    colors = [((value - minimum) / (maximum - minimum), color) for value, color in TEMPERATURE_STOPS]
    return LinearSegmentedColormap.from_list("better-weather-temperature", colors)


def main() -> None:
    _, water = read_relief_and_water()
    land = water == 0
    summary_rows: list[dict] = []
    occupancy_rows: list[dict] = []
    monthly_values: list[np.ndarray] = []

    for month in range(1, 13):
        normal = read_temperature_normal(month)
        values = normal[land & np.isfinite(normal)]
        monthly_values.append(values)
        percentiles = np.percentile(values, QUANTILES)
        row = {
            "month": month,
            "label": MONTH_LABELS[month - 1],
            "land_pixel_count": values.size,
            "below_palette_min_percent": 100 * np.mean(values < STOP_VALUES[0]),
            "above_palette_max_percent": 100 * np.mean(values > STOP_VALUES[-1]),
        }
        row.update({f"p{str(q).replace('.', '_')}": value for q, value in zip(QUANTILES, percentiles)})
        summary_rows.append(row)

        counts, _ = np.histogram(values, bins=BIN_EDGES)
        for left, right, count in zip(BIN_EDGES[:-1], BIN_EDGES[1:], counts):
            occupancy_rows.append(
                {
                    "month": month,
                    "label": MONTH_LABELS[month - 1],
                    "interval": interval_label(left, right),
                    "pixel_count": int(count),
                    "percent": 100 * count / values.size,
                }
            )

    summary = pd.DataFrame(summary_rows)
    occupancy = pd.DataFrame(occupancy_rows)
    summary.to_csv(OUTPUT / "analyse-palette-temperature-moyenne.csv", index=False)
    occupancy.to_csv(OUTPUT / "occupation-palette-temperature-moyenne.csv", index=False)

    figure, axes = plt.subplots(
        2,
        1,
        figsize=(12, 8),
        height_ratios=(1.15, 1),
        constrained_layout=True,
    )
    months = summary["month"].to_numpy()
    axes[0].fill_between(months, summary["p1"], summary["p99"], color="#74add1", alpha=0.25, label="P1–P99")
    axes[0].fill_between(months, summary["p10"], summary["p90"], color="#fdae61", alpha=0.42, label="P10–P90")
    axes[0].plot(months, summary["p50"], color="#6b1d1d", marker="o", linewidth=2, label="médiane")
    for stop in (-30, -20, -10, 0, 10, 20, 30, 40):
        axes[0].axhline(stop, color="#777777", linewidth=0.45, alpha=0.35)
    axes[0].set_xticks(months, MONTH_LABELS)
    axes[0].set_ylabel("température moyenne (°C)")
    axes[0].set_title("Distribution terrestre mensuelle — quantiles spatiaux")
    axes[0].legend(loc="upper left", ncols=3)
    axes[0].grid(axis="y", alpha=0.18)

    histogram_bins = np.linspace(-30, 40, 141)
    heatmap = []
    for values in monthly_values:
        counts, _ = np.histogram(values, bins=histogram_bins)
        heatmap.append(counts / counts.sum() * 100)
    heatmap_array = np.asarray(heatmap)
    cmap = palette_colormap()
    axes[1].imshow(
        heatmap_array,
        aspect="auto",
        interpolation="nearest",
        extent=(histogram_bins[0], histogram_bins[-1], 12.5, 0.5),
        cmap="Greys",
        norm=Normalize(vmin=0, vmax=max(1.0, np.percentile(heatmap_array, 99))),
    )
    axes[1].set_yticks(np.arange(1, 13), MONTH_LABELS)
    axes[1].set_xlabel("température moyenne (°C)")
    axes[1].set_ylabel("mois")
    axes[1].set_title("Occupation de la plage thermique (densité spatiale)")

    gradient = np.linspace(-30, 40, 512)[None, :]
    inset = axes[1].inset_axes([0.0, -0.34, 1.0, 0.12])
    inset.imshow(gradient, aspect="auto", cmap=cmap, extent=(-30, 40, 0, 1))
    inset.set_yticks([])
    inset.set_xticks(STOP_VALUES)
    inset.set_xlabel("palette provisoire et points d’arrêt (°C)")

    figure.suptitle("Audit de la palette — température moyenne 1991–2020", fontsize=15)
    figure.savefig(OUTPUT / "analyse-palette-temperature-moyenne.png", dpi=180)
    plt.close(figure)

    print(summary.to_string(index=False))


if __name__ == "__main__":
    main()
