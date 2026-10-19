#!/usr/bin/env python3
"""Audit provisional palettes for monthly mean daily maximum and minimum temperature."""

from __future__ import annotations

import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import rasterio
from rasterio.windows import from_bounds as window_from_bounds

from build_pilot_tiles import BOUNDS, CACHE, ENV, HEIGHT, ROOT, WIDTH, YEARS, read_relief_and_water


OUTPUT = ROOT / "outputs"
VARIABLES = {
    "tmax": {"source": "tasmax", "label": "maximales moyennes"},
    "tmin": {"source": "tasmin", "label": "minimales moyennes"},
}
MONTH_LABELS = [
    "jan", "fév", "mar", "avr", "mai", "juin",
    "juil", "août", "sep", "oct", "nov", "déc",
]
QUANTILES = [0, 0.1, 1, 5, 10, 25, 50, 75, 90, 95, 99, 99.9, 100]
CURRENT_MINIMUM = -30.0
CURRENT_MAXIMUM = 40.0
PROPOSED_MINIMUM = -40.0
PROPOSED_MAXIMUM = 50.0


def chelsa_url(source_variable: str, year: int, month: int) -> str:
    return (
        "https://os.unil.cloud.switch.ch/chelsa02/chelsa/global/monthly/"
        f"{source_variable}/{year}/CHELSA_{source_variable}_{month:02d}_{year}_V.2.1.tif"
    )


def read_year(source_variable: str, year: int, month: int) -> tuple[np.ndarray, np.ndarray]:
    url = chelsa_url(source_variable, year, month)
    last_error: Exception | None = None
    for attempt in range(1, 4):
        try:
            with rasterio.Env(**ENV), rasterio.open(url) as source:
                window = window_from_bounds(*BOUNDS, transform=source.transform).round_offsets().round_lengths()
                raw = source.read(1, window=window)
                if raw.shape != (HEIGHT, WIDTH):
                    raise RuntimeError(f"Unexpected CHELSA shape for {url}: {raw.shape}")
                valid = raw != source.nodata
                celsius = raw.astype("float32") * source.scales[0] + source.offsets[0] - 273.15
                return celsius, valid
        except Exception as exc:  # Network-backed reads can fail transiently.
            last_error = exc
            if attempt < 3:
                time.sleep(attempt * 2)
    assert last_error is not None
    raise last_error


def read_normal(variable: str, month: int) -> np.ndarray:
    path = CACHE / f"{variable}_{month:02d}_1991_2020.npy"
    if path.exists():
        return np.load(path)

    source_variable = VARIABLES[variable]["source"]
    total = np.zeros((HEIGHT, WIDTH), dtype="float64")
    count = np.zeros((HEIGHT, WIDTH), dtype="uint8")
    with ThreadPoolExecutor(max_workers=4) as pool:
        futures = {
            pool.submit(read_year, source_variable, year, month): year
            for year in YEARS
        }
        for index, future in enumerate(as_completed(futures), start=1):
            values, valid = future.result()
            total[valid] += values[valid]
            count[valid] += 1
            if index % 5 == 0 or index == len(futures):
                print(f"CHELSA {variable} mois {month:02d}: {index}/30", flush=True)

    normal = np.full((HEIGHT, WIDTH), np.nan, dtype="float32")
    complete = count == len(YEARS)
    normal[complete] = (total[complete] / count[complete]).astype("float32")
    np.save(path, normal)
    return normal


def main() -> None:
    _, water = read_relief_and_water()
    land = water == 0
    rows: list[dict] = []

    for month in range(1, 13):
        for variable in VARIABLES:
            normal = read_normal(variable, month)
            values = normal[land & np.isfinite(normal)]
            percentiles = np.percentile(values, QUANTILES)
            row = {
                "variable": variable,
                "month": month,
                "label": MONTH_LABELS[month - 1],
                "land_pixel_count": values.size,
                "below_minus_30_percent": 100 * np.mean(values < CURRENT_MINIMUM),
                "above_40_percent": 100 * np.mean(values > CURRENT_MAXIMUM),
                "below_minus_40_percent": 100 * np.mean(values < PROPOSED_MINIMUM),
                "above_50_percent": 100 * np.mean(values > PROPOSED_MAXIMUM),
            }
            row.update({f"p{str(q).replace('.', '_')}": value for q, value in zip(QUANTILES, percentiles)})
            rows.append(row)

    summary = pd.DataFrame(rows)
    summary.to_csv(OUTPUT / "analyse-palettes-temperatures-extremes.csv", index=False)

    figure, axes = plt.subplots(2, 1, figsize=(12, 8), sharex=True, constrained_layout=True)
    colors = {"tmax": "#c62828", "tmin": "#1565c0"}
    for axis, variable in zip(axes, VARIABLES):
        data = summary[summary["variable"] == variable].sort_values("month")
        months = data["month"].to_numpy()
        axis.fill_between(months, data["p1"], data["p99"], color=colors[variable], alpha=0.18, label="P1–P99")
        axis.fill_between(months, data["p10"], data["p90"], color=colors[variable], alpha=0.32, label="P10–P90")
        axis.plot(months, data["p50"], color=colors[variable], marker="o", linewidth=2, label="médiane")
        axis.axhline(CURRENT_MINIMUM, color="#313695", linestyle="--", linewidth=1, label="borne actuelle −30 °C")
        axis.axhline(CURRENT_MAXIMUM, color="#a50026", linestyle="--", linewidth=1, label="borne actuelle 40 °C")
        axis.axhline(PROPOSED_MINIMUM, color="#171747", linestyle=":", linewidth=1, label="extension −40 °C")
        axis.axhline(PROPOSED_MAXIMUM, color="#31000f", linestyle=":", linewidth=1, label="extension 50 °C")
        axis.set_ylabel("température (°C)")
        axis.set_title(VARIABLES[variable]["label"].capitalize())
        axis.grid(axis="y", alpha=0.18)
        axis.legend(loc="upper left", ncols=5, fontsize=8)
    axes[-1].set_xticks(range(1, 13), MONTH_LABELS)
    axes[-1].set_xlabel("mois")
    figure.suptitle("Audit des palettes de températures extrêmes — 1991–2020", fontsize=15)
    figure.savefig(OUTPUT / "analyse-palettes-temperatures-extremes.png", dpi=180)
    plt.close(figure)

    print(summary.to_string(index=False))


if __name__ == "__main__":
    main()
