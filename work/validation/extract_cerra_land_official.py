#!/usr/bin/env python3
"""Extract official CERRA-Land daily precipitation time series from CDS.

The CDS time-series product is optimised for long temporal ranges at individual
locations. Raw ZIP/CSV responses stay in the ignored validation cache; only the
small monthly 1991-2020 climatology and point metadata are written outside it.
"""

from __future__ import annotations

import math
import re
import zipfile
from pathlib import Path

import cdsapi
import pandas as pd


ROOT = Path(__file__).resolve().parents[2]
CACHE = ROOT / "work" / "validation" / "cache" / "official_cerra_land"
CACHE.mkdir(parents=True, exist_ok=True)

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


def slugify(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", value.lower()).strip("_")


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    radius_km = 6371.0088
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    d_phi = math.radians(lat2 - lat1)
    d_lambda = math.radians(lon2 - lon1)
    a = (
        math.sin(d_phi / 2) ** 2
        + math.cos(phi1) * math.cos(phi2) * math.sin(d_lambda / 2) ** 2
    )
    return 2 * radius_km * math.asin(math.sqrt(a))


def extract_csv(zip_path: Path, csv_path: Path) -> None:
    with zipfile.ZipFile(zip_path) as archive:
        members = [name for name in archive.namelist() if name.endswith(".csv")]
        if len(members) != 1:
            raise RuntimeError(f"Expected one CSV in {zip_path}, found {members}")
        with archive.open(members[0]) as source, csv_path.open("wb") as target:
            target.write(source.read())


def fetch_point(
    client: cdsapi.Client,
    region: str,
    name: str,
    latitude: float,
    longitude: float,
) -> pd.DataFrame:
    slug = slugify(name)
    zip_path = CACHE / f"{slug}_precip_1991_2020.zip"
    csv_path = CACHE / f"{slug}_precip_1991_2020.csv"

    if not csv_path.exists():
        if not zip_path.exists():
            client.retrieve(
                "reanalysis-cerra-land-timeseries",
                {
                    "variable": ["total_precipitation"],
                    "location": {
                        "longitude": longitude,
                        "latitude": latitude,
                    },
                    "date": ["1991-01-01/2020-12-31"],
                    "data_format": "csv",
                },
                str(zip_path),
            )
        extract_csv(zip_path, csv_path)

    frame = pd.read_csv(csv_path, parse_dates=["valid_time"])
    required = {"valid_time", "tp", "latitude", "longitude"}
    missing = required.difference(frame.columns)
    if missing:
        raise RuntimeError(f"Missing columns for {name}: {sorted(missing)}")

    frame["region"] = region
    frame["point"] = name
    frame["requested_latitude"] = latitude
    frame["requested_longitude"] = longitude
    return frame


def main() -> None:
    client = cdsapi.Client(quiet=False, progress=False)
    frames = []
    for index, point in enumerate(POINTS, start=1):
        frame = fetch_point(client, *point)
        frames.append(frame)
        print(f"CERRA-Land officiel {index}/{len(POINTS)} : {point[1]}", flush=True)

    daily = pd.concat(frames, ignore_index=True)
    daily["year"] = daily["valid_time"].dt.year
    daily["month"] = daily["valid_time"].dt.month
    daily["rain_day"] = daily["tp"] >= 1.0

    by_year_month = (
        daily.groupby(["region", "point", "year", "month"], as_index=False)
        .agg(
            precipitation_mm=("tp", "sum"),
            rainy_days_ge_1mm=("rain_day", "sum"),
            observed_days=("valid_time", "count"),
        )
    )

    normals = (
        by_year_month.groupby(["region", "point", "month"], as_index=False)
        .agg(
            precipitation_mm=("precipitation_mm", "mean"),
            rainy_days_ge_1mm=("rainy_days_ge_1mm", "mean"),
            years=("year", "nunique"),
            minimum_observed_days=("observed_days", "min"),
        )
        .sort_values(["region", "point", "month"])
    )

    metadata_rows = []
    for region, name, latitude, longitude in POINTS:
        point_data = daily[daily["point"] == name]
        grid_latitude = float(point_data["latitude"].iloc[0])
        grid_longitude = float(point_data["longitude"].iloc[0])
        metadata_rows.append(
            {
                "region": region,
                "point": name,
                "requested_latitude": latitude,
                "requested_longitude": longitude,
                "grid_latitude": grid_latitude,
                "grid_longitude": grid_longitude,
                "grid_offset_km": haversine_km(
                    latitude, longitude, grid_latitude, grid_longitude
                ),
                "first_date": point_data["valid_time"].min().date().isoformat(),
                "last_date": point_data["valid_time"].max().date().isoformat(),
                "daily_rows": len(point_data),
                "missing_precipitation_days": int(point_data["tp"].isna().sum()),
            }
        )

    validation_dir = ROOT / "work" / "validation"
    normals.to_csv(
        validation_dir / "cerra_land_official_monthly_normals_1991_2020.csv",
        index=False,
    )
    pd.DataFrame(metadata_rows).to_csv(
        validation_dir / "cerra_land_official_point_metadata.csv", index=False
    )

    print(
        f"Terminé : {len(daily):,} jours, {len(normals):,} normales mensuelles",
        flush=True,
    )


if __name__ == "__main__":
    main()
