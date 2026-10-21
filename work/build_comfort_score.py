#!/usr/bin/env python3
"""Build the monthly 0–100 comfort score COGs used by the web map."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import rasterio
from rasterio.enums import Resampling
from rasterio.warp import reproject


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SOURCE = ROOT / "work/derived/1991-2020-masked"
DEFAULT_OUTPUT = ROOT / "work/derived/1991-2020-masked/comfort"
DAYS_PER_MONTH = (31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31)
NODATA = 65535
SCALE = 0.1


def trapezoid_score(values: np.ndarray, low_zero: float, low_ideal: float,
                    high_ideal: float, high_zero: float) -> np.ndarray:
    """Return a smooth 0–100 comfort score with an ideal plateau."""
    result = np.full(values.shape, 100.0, dtype="float32")
    below = values < low_ideal
    above = values > high_ideal
    result[below] = 100 * np.clip(
        (values[below] - low_zero) / (low_ideal - low_zero), 0, 1
    ) ** 1.35
    result[above] = 100 * np.clip(
        (high_zero - values[above]) / (high_zero - high_ideal), 0, 1
    ) ** 1.35
    return result


def comfort_score(tmax: np.ndarray, tmin: np.ndarray, precipitation: np.ndarray,
                  sunshine: np.ndarray, days: int) -> np.ndarray:
    """Combine day, night, sun and rain using a weighted geometric mean."""
    day = trapezoid_score(tmax, 8, 22, 27, 39)
    night = trapezoid_score(tmin, 0, 12, 18, 27)
    sun_hours = sunshine / days
    sun = trapezoid_score(sun_hours, 0, 6, 9, 13)
    rain = 100 * np.clip((180 - precipitation) / 160, 0, 1) ** 0.8
    rain[precipitation <= 20] = 100

    components = ((day, 0.35), (night, 0.25), (sun, 0.25), (rain, 0.15))
    combined = np.ones(tmax.shape, dtype="float32")
    for component, weight in components:
        combined *= np.maximum(component / 100, 0.01) ** weight

    heat_sun_penalty = 15 * np.clip((tmax - 30) / 8, 0, 1) * np.clip(
        (sun_hours - 8) / 4, 0, 1
    )
    return np.clip(combined * 100 - heat_sun_penalty, 0, 100)


def read_on_grid(path: Path, template: rasterio.io.DatasetReader) -> tuple[np.ndarray, np.ndarray]:
    with rasterio.open(path) as source:
        data = np.full((template.height, template.width), np.nan, dtype="float32")
        reproject(
            source=rasterio.band(source, 1),
            destination=data,
            src_transform=source.transform,
            src_crs=source.crs,
            src_nodata=source.nodata,
            dst_transform=template.transform,
            dst_crs=template.crs,
            dst_nodata=np.nan,
            resampling=Resampling.bilinear,
        )
        data = data * source.scales[0] + source.offsets[0]
    return data, np.isfinite(data)


def build_month(source_root: Path, output_root: Path, month: int) -> Path:
    sunshine_path = source_root / "sunshine" / f"{month:02d}.tif"
    output_path = output_root / f"{month:02d}.tif"
    output_root.mkdir(parents=True, exist_ok=True)
    with rasterio.open(sunshine_path) as template:
        sunshine = template.read(1).astype("float32") * template.scales[0] + template.offsets[0]
        valid = sunshine != template.nodata * template.scales[0] + template.offsets[0]
        arrays = {}
        for layer in ("tmax", "tmin", "precipitation"):
            arrays[layer], layer_valid = read_on_grid(source_root / layer / f"{month:02d}.tif", template)
            valid &= layer_valid
        score = comfort_score(
            arrays["tmax"], arrays["tmin"], arrays["precipitation"], sunshine,
            DAYS_PER_MONTH[month - 1],
        )
        encoded = np.full(score.shape, NODATA, dtype="uint16")
        encoded[valid] = np.rint(score[valid] / SCALE).astype("uint16")
        profile = template.profile.copy()
        profile.update(
            dtype="uint16", nodata=NODATA, count=1, compress="deflate", predictor=2,
            tiled=True, blockxsize=256, blockysize=256,
        )
        with rasterio.open(output_path, "w", **profile) as destination:
            destination.write(encoded, 1)
            destination.scales = (SCALE,)
            destination.offsets = (0.0,)
            destination.update_tags(
                score="comfort-v1", reference_period="1991-2020",
                formula="geometric(day=.35,night=.25,sun=.25,rain=.15)-heat_sun_penalty",
            )
    metadata = {
        "layer_id": "comfort", "month": month, "unit": "/100",
        "source": "CHELSA-monthly V2.1 + SARAH-3",
        "weights": {"day": 0.35, "night": 0.25, "sunshine": 0.25, "precipitation": 0.15},
        "ideal_ranges": {"day_c": [22, 27], "night_c": [12, 18], "sun_hours_day": [6, 9], "precipitation_mm_month": [0, 20]},
    }
    output_path.with_suffix(".tif.json").write_text(json.dumps(metadata, ensure_ascii=False, indent=2) + "\n")
    return output_path


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--months", default="1-12", help="Exemple : 1-12 ou 1,7")
    args = parser.parse_args()
    if "-" in args.months:
        start, end = (int(value) for value in args.months.split("-", 1))
        months = range(start, end + 1)
    else:
        months = [int(value) for value in args.months.split(",")]
    for month in months:
        path = build_month(args.source, args.output, month)
        print(path.relative_to(ROOT))


if __name__ == "__main__":
    main()
