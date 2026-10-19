#!/usr/bin/env python3
"""Validate Copernicus DEM Water Body Mask at the 18 test points."""

from __future__ import annotations

import math
from pathlib import Path

import numpy as np
import pandas as pd
import rasterio
from rasterio.windows import Window

from make_spatial_window_validation import ENV, wbm_url


ROOT = Path(__file__).resolve().parents[2]
CLASSES = {0: "terre", 1: "océan", 2: "lac", 3: "rivière"}


def analyse_point(latitude: float, longitude: float) -> dict:
    url = wbm_url(math.floor(latitude), math.floor(longitude))
    with rasterio.Env(**ENV), rasterio.open(url) as source:
        row, column = source.index(longitude, latitude)
        click_class = int(source.read(1, window=Window(column, row, 1, 1))[0, 0])

        # Approximately 1 km centred on the click (37 pixels at the equator).
        half_cell_pixels = 18
        cell = source.read(
            1,
            window=Window(
                column - half_cell_pixels,
                row - half_cell_pixels,
                half_cell_pixels * 2 + 1,
                half_cell_pixels * 2 + 1,
            ),
            boundless=True,
            fill_value=255,
        )
        valid = cell != 255
        land_fraction = float((cell[valid] == 0).mean()) if valid.any() else np.nan

        nearest_land_m = 0.0
        if click_class != 0:
            radius = 300  # roughly 8 km, sufficient for coastal click recovery
            nearby = source.read(
                1,
                window=Window(column - radius, row - radius, radius * 2 + 1, radius * 2 + 1),
                boundless=True,
                fill_value=255,
            )
            land_rows, land_columns = np.where(nearby == 0)
            if len(land_rows):
                delta_rows = land_rows - radius
                delta_columns = land_columns - radius
                metres_y = abs(source.transform.e) * 111_320
                metres_x = source.transform.a * 111_320 * math.cos(math.radians(latitude))
                nearest_land_m = float(
                    np.sqrt((delta_rows * metres_y) ** 2 + (delta_columns * metres_x) ** 2).min()
                )
            else:
                nearest_land_m = np.nan

    if click_class == 0:
        action = "utiliser la cellule climatique terrestre"
    elif np.isfinite(nearest_land_m) and nearest_land_m <= 2_000:
        action = "proposer la cellule terrestre la plus proche"
    else:
        action = "afficher eau, sans valeur climatique terrestre"
    return {
        "water_mask_class": click_class,
        "surface": CLASSES.get(click_class, "inconnue"),
        "land_fraction_approx_1km": land_fraction,
        "nearest_land_m": nearest_land_m,
        "recommended_click_action": action,
        "source_url": url,
    }


def main() -> None:
    points = pd.read_csv(ROOT / "outputs" / "altitudes-points-tests.csv")
    rows = []
    for point in points.itertuples(index=False):
        result = analyse_point(point.latitude, point.longitude)
        rows.append(
            {
                "region": point.region,
                "point": point.point,
                "latitude": point.latitude,
                "longitude": point.longitude,
                **result,
            }
        )
        print(
            f"{point.point}: {result['surface']}, "
            f"terre dans 1 km {result['land_fraction_approx_1km']:.1%}, "
            f"terrain le plus proche {result['nearest_land_m']:.0f} m",
            flush=True,
        )
    output = ROOT / "outputs" / "controle-masque-eau-points.csv"
    pd.DataFrame(rows).to_csv(output, index=False)
    print(f"Écrit : {output}")


if __name__ == "__main__":
    main()
