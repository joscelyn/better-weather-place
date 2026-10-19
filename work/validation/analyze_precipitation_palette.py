#!/usr/bin/env python3
"""Audit the provisional monthly-precipitation palette on 1991-2020 normals."""

from __future__ import annotations

import time
from concurrent.futures import ThreadPoolExecutor, as_completed

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import rasterio
from rasterio.windows import from_bounds as window_from_bounds

from build_pilot_tiles import BOUNDS, CACHE, ENV, HEIGHT, ROOT, WIDTH, YEARS, read_relief_and_water


OUTPUT = ROOT / "outputs"
MONTH_LABELS = [
    "jan", "fév", "mar", "avr", "mai", "juin",
    "juil", "août", "sep", "oct", "nov", "déc",
]
QUANTILES = [0, 0.1, 1, 5, 10, 25, 50, 75, 90, 95, 99, 99.9, 100]
PALETTE_EDGES = np.array([0, 5, 10, 20, 40, 60, 100, 150, 250, 400, np.inf], dtype="float64")
PALETTE_COLORS = [
    "#f7fbff", "#e3eef9", "#cfe1f2", "#9ecae1", "#6baed6",
    "#4292c6", "#2171b5", "#08519c", "#08306b", "#3f007d",
]


def chelsa_url(year: int, month: int) -> str:
    return (
        "https://os.unil.cloud.switch.ch/chelsa02/chelsa/global/monthly/"
        f"pr/{year}/CHELSA_pr_{month:02d}_{year}_V.2.1.tif"
    )


def read_year(year: int, month: int) -> tuple[np.ndarray, np.ndarray]:
    url = chelsa_url(year, month)
    last_error: Exception | None = None
    for attempt in range(1, 4):
        try:
            with rasterio.Env(**ENV), rasterio.open(url) as source:
                window = window_from_bounds(*BOUNDS, transform=source.transform).round_offsets().round_lengths()
                raw = source.read(1, window=window)
                if raw.shape != (HEIGHT, WIDTH):
                    raise RuntimeError(f"Unexpected CHELSA shape for {url}: {raw.shape}")
                valid = raw != source.nodata
                millimetres = raw.astype("float32") * source.scales[0] + source.offsets[0]
                return millimetres, valid
        except Exception as exc:
            last_error = exc
            if attempt < 3:
                time.sleep(attempt * 2)
    assert last_error is not None
    raise last_error


def read_normal(month: int) -> np.ndarray:
    path = CACHE / f"precipitation_{month:02d}_1991_2020.npy"
    if path.exists():
        return np.load(path)

    total = np.zeros((HEIGHT, WIDTH), dtype="float64")
    count = np.zeros((HEIGHT, WIDTH), dtype="uint8")
    with ThreadPoolExecutor(max_workers=4) as pool:
        futures = {pool.submit(read_year, year, month): year for year in YEARS}
        for index, future in enumerate(as_completed(futures), start=1):
            values, valid = future.result()
            total[valid] += values[valid]
            count[valid] += 1
            if index % 5 == 0 or index == len(futures):
                print(f"CHELSA précipitations mois {month:02d}: {index}/30", flush=True)

    normal = np.full((HEIGHT, WIDTH), np.nan, dtype="float32")
    complete = count == len(YEARS)
    normal[complete] = (total[complete] / count[complete]).astype("float32")
    np.save(path, normal)
    return normal


def interval_label(left: float, right: float) -> str:
    if np.isposinf(right):
        return f">= {left:g}"
    return f"{left:g} à < {right:g}"


def main() -> None:
    _, water = read_relief_and_water()
    land = water == 0
    summary_rows: list[dict] = []
    occupancy_rows: list[dict] = []

    for month in range(1, 13):
        normal = read_normal(month)
        values = normal[land & np.isfinite(normal)]
        if values.min() < 0:
            raise RuntimeError(f"Negative precipitation in month {month}: {values.min()}")
        percentiles = np.percentile(values, QUANTILES)
        row = {
            "month": month,
            "label": MONTH_LABELS[month - 1],
            "land_pixel_count": values.size,
            "below_5mm_percent": 100 * np.mean(values < 5),
            "below_10mm_percent": 100 * np.mean(values < 10),
            "above_400mm_percent": 100 * np.mean(values > 400),
            "above_600mm_percent": 100 * np.mean(values > 600),
        }
        row.update({f"p{str(q).replace('.', '_')}": value for q, value in zip(QUANTILES, percentiles)})
        summary_rows.append(row)

        counts, _ = np.histogram(values, bins=PALETTE_EDGES)
        for left, right, count in zip(PALETTE_EDGES[:-1], PALETTE_EDGES[1:], counts):
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
    summary.to_csv(OUTPUT / "analyse-palette-precipitations.csv", index=False)
    occupancy.to_csv(OUTPUT / "occupation-palette-precipitations.csv", index=False)

    figure, axes = plt.subplots(2, 1, figsize=(12, 9), constrained_layout=True)
    months = summary["month"].to_numpy()
    axes[0].fill_between(months, summary["p1"], summary["p99"], color="#6baed6", alpha=0.22, label="P1–P99")
    axes[0].fill_between(months, summary["p10"], summary["p90"], color="#2171b5", alpha=0.35, label="P10–P90")
    axes[0].plot(months, summary["p50"], color="#08306b", marker="o", linewidth=2, label="médiane")
    axes[0].axhline(400, color="#3f007d", linestyle="--", linewidth=1.2, label="borne actuelle 400 mm")
    axes[0].set_ylim(0, 420)
    axes[0].set_xticks(months, MONTH_LABELS)
    axes[0].set_ylabel("précipitations (mm/mois)")
    axes[0].set_title("Distribution terrestre mensuelle — quantiles spatiaux")
    axes[0].legend(loc="upper right", ncols=5, fontsize=8)
    axes[0].grid(axis="y", alpha=0.18)

    pivot = occupancy.pivot(index="month", columns="interval", values="percent")
    ordered_labels = [interval_label(a, b) for a, b in zip(PALETTE_EDGES[:-1], PALETTE_EDGES[1:])]
    bottom = np.zeros(12)
    for label, color in zip(ordered_labels, PALETTE_COLORS):
        values = pivot[label].to_numpy()
        axes[1].bar(months, values, bottom=bottom, color=color, width=0.82, label=label)
        bottom += values
    axes[1].set_xticks(months, MONTH_LABELS)
    axes[1].set_ylim(0, 100)
    axes[1].set_ylabel("part des pixels terrestres (%)")
    axes[1].set_title("Occupation des intervalles de la palette")
    axes[1].legend(title="mm/mois", bbox_to_anchor=(1.01, 1), loc="upper left", fontsize=8)

    figure.suptitle("Audit de la palette — précipitations mensuelles 1991–2020", fontsize=15)
    figure.savefig(OUTPUT / "analyse-palette-precipitations.png", dpi=180)
    plt.close(figure)

    print(summary.to_string(index=False))


if __name__ == "__main__":
    main()
