#!/usr/bin/env python3
"""Validate official CERRA-Land rainy days against Moroccan WMO normals."""

from __future__ import annotations

import math
import re
import zipfile
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import cdsapi
import numpy as np
import pandas as pd

from validate_wmo_morocco import load_wmo


ROOT = Path(__file__).resolve().parents[2]
CACHE = ROOT / "work" / "validation" / "cache" / "official_cerra_land_wmo_morocco"
CACHE.mkdir(parents=True, exist_ok=True)
OUTPUTS = ROOT / "outputs"


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
            raise RuntimeError(f"Un CSV attendu dans {zip_path}, trouvé : {members}")
        with archive.open(members[0]) as source, csv_path.open("wb") as target:
            target.write(source.read())


def fetch_station(station: pd.Series) -> pd.DataFrame:
    stem = f"{station.wmo_id}_{slugify(station.station)}"
    zip_path = CACHE / f"{stem}_precip_1991_2020.zip"
    csv_path = CACHE / f"{stem}_precip_1991_2020.csv"
    if not csv_path.exists():
        if zip_path.exists() and not zipfile.is_zipfile(zip_path):
            zip_path.unlink()
        if not zip_path.exists():
            client = cdsapi.Client(quiet=True, progress=False)
            client.retrieve(
                "reanalysis-cerra-land-timeseries",
                {
                    "variable": ["total_precipitation"],
                    "location": {
                        "longitude": float(station.longitude),
                        "latitude": float(station.latitude),
                    },
                    "date": ["1991-01-01/2020-12-31"],
                    "data_format": "csv",
                },
                str(zip_path),
            )
        extract_csv(zip_path, csv_path)

    frame = pd.read_csv(csv_path, parse_dates=["valid_time"])
    frame["wmo_id"] = station.wmo_id
    frame["station"] = station.station
    frame["requested_latitude"] = station.latitude
    frame["requested_longitude"] = station.longitude
    return frame


def main() -> None:
    stations, wmo = load_wmo()
    frames = []
    with ThreadPoolExecutor(max_workers=4) as pool:
        futures = {
            pool.submit(fetch_station, station): station.station
            for _, station in stations.iterrows()
        }
        for completed, future in enumerate(as_completed(futures), start=1):
            frames.append(future.result())
            print(
                f"CERRA-Land Maroc {completed}/{len(stations)} : {futures[future]}",
                flush=True,
            )

    daily = pd.concat(frames, ignore_index=True)
    daily["year"] = daily["valid_time"].dt.year
    daily["month"] = daily["valid_time"].dt.month
    daily["rain_day_ge_1mm"] = daily["tp"] >= 1.0
    yearly = daily.groupby(["wmo_id", "station", "year", "month"], as_index=False).agg(
        cerra_land_rainy_days=("rain_day_ge_1mm", "sum"),
        observed_days=("valid_time", "count"),
    )
    normals = yearly.groupby(["wmo_id", "station", "month"], as_index=False).agg(
        cerra_land_rainy_days=("cerra_land_rainy_days", "mean"),
        cerra_land_years=("year", "nunique"),
        minimum_observed_days=("observed_days", "min"),
    )
    dp01 = wmo[wmo["wmo_variable"] == "DP01"].rename(
        columns={"wmo_value": "wmo_rainy_days_ge_1mm"}
    )
    comparison = normals.merge(
        dp01[["wmo_id", "station", "month", "wmo_rainy_days_ge_1mm"]],
        on=["wmo_id", "station", "month"],
        how="inner",
    )
    comparison["difference_cerra_land_minus_wmo_days"] = (
        comparison["cerra_land_rainy_days"] - comparison["wmo_rainy_days_ge_1mm"]
    )

    metadata_rows = []
    for station in stations.itertuples(index=False):
        sample = daily[daily["wmo_id"] == station.wmo_id]
        grid_latitude = float(sample["latitude"].iloc[0])
        grid_longitude = float(sample["longitude"].iloc[0])
        metadata_rows.append(
            {
                "wmo_id": station.wmo_id,
                "station": station.station,
                "station_latitude": station.latitude,
                "station_longitude": station.longitude,
                "grid_latitude": grid_latitude,
                "grid_longitude": grid_longitude,
                "grid_offset_km": haversine_km(
                    station.latitude, station.longitude, grid_latitude, grid_longitude
                ),
                "daily_rows": len(sample),
                "missing_precipitation_days": int(sample["tp"].isna().sum()),
            }
        )
    metadata = pd.DataFrame(metadata_rows)

    monthly = comparison.groupby("month", as_index=False).agg(
        pairs=("station", "size"),
        bias_days=("difference_cerra_land_minus_wmo_days", "mean"),
        mae_days=(
            "difference_cerra_land_minus_wmo_days",
            lambda values: float(np.mean(np.abs(values))),
        ),
        p90_absolute_error_days=(
            "difference_cerra_land_minus_wmo_days",
            lambda values: float(np.quantile(np.abs(values), 0.9)),
        ),
    )

    comparison_path = OUTPUTS / "comparaison-cerra-land-wmo-jours-pluie-maroc.csv"
    summary_path = OUTPUTS / "synthese-cerra-land-wmo-jours-pluie-maroc.csv"
    metadata_path = OUTPUTS / "controle-mailles-cerra-land-stations-wmo-maroc.csv"
    comparison.to_csv(comparison_path, index=False)
    monthly.to_csv(summary_path, index=False)
    metadata.to_csv(metadata_path, index=False)

    error = comparison["difference_cerra_land_minus_wmo_days"]
    print(
        "\nCERRA-Land vs WMO — jours >= 1 mm : "
        f"biais {error.mean():+.2f} j/mois, "
        f"MAE {error.abs().mean():.2f} j/mois, "
        f"p90 {error.abs().quantile(0.9):.2f} j/mois"
    )
    print(
        f"Décalage de grille médian/max : "
        f"{metadata['grid_offset_km'].median():.2f}/"
        f"{metadata['grid_offset_km'].max():.2f} km"
    )
    print(f"Écrit : {comparison_path}")
    print(f"Écrit : {summary_path}")
    print(f"Écrit : {metadata_path}")


if __name__ == "__main__":
    main()
