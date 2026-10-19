#!/usr/bin/env python3
"""Sample the public Copernicus DEM GLO-30 COGs at validation points."""

from __future__ import annotations

import math
from pathlib import Path

import pandas as pd
import rasterio


ROOT = Path(__file__).resolve().parents[2]

POINTS = [
    ("alpes", "Annecy", 45.899, 6.129),
    ("alpes", "Chamonix", 45.924, 6.870),
    ("alpes", "Mont-Blanc", 45.833, 6.865),
    ("pyrenees", "Perpignan", 42.688, 2.894),
    ("pyrenees", "Font-Romeu", 42.505, 2.040),
    ("portugal-galice", "Porto", 41.157, -8.629),
    ("portugal-galice", "Santiago", 42.878, -8.545),
    ("portugal-galice", "Faro", 37.019, -7.931),
    ("andalousie", "Malaga", 36.722, -4.421),
    ("andalousie", "Grenade", 37.177, -3.599),
    ("maroc", "Essaouira", 31.509, -9.770),
    ("maroc", "Marrakech", 31.630, -8.009),
    ("maroc", "Ifrane", 33.522, -5.110),
    ("canaries", "La-Laguna", 28.488, -16.316),
    ("canaries", "Costa-Adeje", 28.087, -16.735),
    ("canaries", "Teide", 28.272, -16.643),
    ("nord", "Reykjavik", 64.147, -21.943),
    ("nord", "Tromso", 69.649, 18.956),
]


def coordinate_token(value: int, positive: str, negative: str, width: int) -> str:
    hemisphere = positive if value >= 0 else negative
    return f"{hemisphere}{abs(value):0{width}d}_00"


def tile_url(latitude: float, longitude: float) -> str:
    south = math.floor(latitude)
    west = math.floor(longitude)
    lat_token = coordinate_token(south, "N", "S", 2)
    lon_token = coordinate_token(west, "E", "W", 3)
    tile = f"Copernicus_DSM_COG_10_{lat_token}_{lon_token}_DEM"
    return (
        "https://copernicus-dem-30m.s3.eu-central-1.amazonaws.com/"
        f"{tile}/{tile}.tif"
    )


def main() -> None:
    rows = []
    env = {
        "GDAL_DISABLE_READDIR_ON_OPEN": "EMPTY_DIR",
        "CPL_VSIL_CURL_ALLOWED_EXTENSIONS": ".tif",
        "GDAL_HTTP_MAX_RETRY": "4",
        "GDAL_HTTP_RETRY_DELAY": "1",
    }
    for region, name, latitude, longitude in POINTS:
        url = tile_url(latitude, longitude)
        with rasterio.Env(**env), rasterio.open(url) as dataset:
            elevation = float(next(dataset.sample([(longitude, latitude)]))[0])
            rows.append(
                {
                    "region": region,
                    "point": name,
                    "latitude": latitude,
                    "longitude": longitude,
                    "elevation_m": elevation,
                    "horizontal_resolution_arcsec": 1.0,
                    "horizontal_resolution_approx_m": 30,
                    "model": "Copernicus DEM GLO-30 (DSM)",
                    "release": "2021",
                    "source_url": url,
                }
            )
        print(f"Copernicus DEM : {name} = {elevation:.1f} m", flush=True)

    frame = pd.DataFrame(rows)
    work_output = ROOT / "work" / "validation" / "copernicus_dem_glo30_points.csv"
    user_output = ROOT / "outputs" / "altitudes-points-tests.csv"
    frame.to_csv(work_output, index=False)
    frame.to_csv(user_output, index=False)
    print(f"Écrit : {user_output}")


if __name__ == "__main__":
    main()
