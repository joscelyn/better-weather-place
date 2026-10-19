#!/usr/bin/env python3
"""Export the exact perimeter of the official native CERRA grid to GeoJSON."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import rasterio
from rasterio.warp import transform


ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "work/validation/cache/official_cerra/auth_test_1991-01-01_00.grib"
OUTPUT = ROOT / "outputs/emprise-cerra-officielle.geojson"


def main() -> None:
    with rasterio.open(SOURCE) as dataset:
        bounds = dataset.bounds
        steps = 256
        perimeter_xy = [
            *zip(np.linspace(bounds.left, bounds.right, steps), np.full(steps, bounds.top)),
            *zip(np.full(steps, bounds.right), np.linspace(bounds.top, bounds.bottom, steps)),
            *zip(np.linspace(bounds.right, bounds.left, steps), np.full(steps, bounds.bottom)),
            *zip(np.full(steps, bounds.left), np.linspace(bounds.bottom, bounds.top, steps)),
        ]
        x, y = zip(*perimeter_xy)
        longitude, latitude = transform(dataset.crs, "EPSG:4326", x, y)
        ring = [[round(lon, 7), round(lat, 7)] for lon, lat in zip(longitude, latitude)]
        ring.append(ring[0])

        feature = {
            "type": "FeatureCollection",
            "features": [
                {
                    "type": "Feature",
                    "properties": {
                        "name": "Emprise native CERRA 5,5 km",
                        "source": "Copernicus Climate Data Store",
                        "grid_width": dataset.width,
                        "grid_height": dataset.height,
                        "grid_spacing_m": abs(dataset.transform.a),
                        "reference_file": SOURCE.name,
                    },
                    "geometry": {"type": "Polygon", "coordinates": [ring]},
                }
            ],
        }

    OUTPUT.write_text(json.dumps(feature, ensure_ascii=False, indent=2) + "\n")
    print(OUTPUT)


if __name__ == "__main__":
    main()
