#!/usr/bin/env python3
"""Sample CHELSA V2.1 monthly fields at selected GHCN stations."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import numpy as np
import pandas as pd
import rasterio


ROOT = Path(__file__).resolve().parents[2]
OUTPUT = ROOT / "work" / "validation" / "chelsa_at_ghcnd_1991_2020.csv"
JAN_JUL_OUTPUT = ROOT / "work" / "validation" / "chelsa_at_ghcnd_jan_jul_1991_2020.csv"
VARIABLES = ("tas", "tasmax", "tasmin", "pr")
MONTHS = range(1, 13)
YEARS = range(1991, 2021)


def url(variable: str, year: int, month: int) -> str:
    return (
        "https://os.unil.cloud.switch.ch/chelsa02/chelsa/global/monthly/"
        f"{variable}/{year}/CHELSA_{variable}_{month:02d}_{year}_V.2.1.tif"
    )


def sample_file(variable: str, year: int, month: int, stations: pd.DataFrame) -> list[dict]:
    source_url = url(variable, year, month)
    options = {
        "GDAL_DISABLE_READDIR_ON_OPEN": "EMPTY_DIR",
        "CPL_VSIL_CURL_ALLOWED_EXTENSIONS": ".tif",
        "GDAL_HTTP_MAX_RETRY": "5",
        "GDAL_HTTP_RETRY_DELAY": "2",
    }
    with rasterio.Env(**options), rasterio.open(source_url) as source:
        coordinates = list(zip(stations["longitude"], stations["latitude"]))
        values = [sample[0] for sample in source.sample(coordinates)]
        scale, offset, nodata = source.scales[0], source.offsets[0], source.nodata

    rows = []
    for station, raw in zip(stations.itertuples(index=False), values):
        value = np.nan if raw == nodata else float(raw) * scale + offset
        if variable.startswith("tas") and np.isfinite(value):
            value -= 273.15
        rows.append(
            {
                "station_id": station.station_id,
                "station_name": station.station_name,
                "latitude": station.latitude,
                "longitude": station.longitude,
                "year": year,
                "month": month,
                "variable": variable,
                "value": value,
                "source_url": source_url,
            }
        )
    return rows


def main() -> None:
    metadata = pd.read_csv(ROOT / "work" / "validation" / "ghcnd_station_metadata.csv")
    stations = metadata.drop_duplicates("station_id")[
        ["station_id", "station_name", "latitude", "longitude"]
    ].reset_index(drop=True)
    if OUTPUT.exists():
        existing = pd.read_csv(OUTPUT)
    elif JAN_JUL_OUTPUT.exists():
        existing = pd.read_csv(JAN_JUL_OUTPUT)
    else:
        existing = pd.DataFrame()
    completed = set()
    if not existing.empty:
        counts = existing.groupby(["variable", "year", "month"])["station_id"].nunique()
        completed = set(counts[counts == len(stations)].index)

    jobs = [
        (variable, year, month)
        for variable in VARIABLES
        for year in YEARS
        for month in MONTHS
        if (variable, year, month) not in completed
    ]
    if not jobs:
        print(f"Déjà complet : {OUTPUT}")
        return
    print(f"Reprise avec {len(completed)} fichiers déjà traités; {len(jobs)} restants", flush=True)
    rows = existing.to_dict("records")
    with ThreadPoolExecutor(max_workers=12) as pool:
        futures = {
            pool.submit(sample_file, variable, year, month, stations): (variable, year, month)
            for variable, year, month in jobs
        }
        for number, future in enumerate(as_completed(futures), start=1):
            job = futures[future]
            try:
                rows.extend(future.result())
            except Exception as exc:
                raise RuntimeError(f"Échec CHELSA pour {job}: {exc}") from exc
            if number % 40 == 0 or number == len(jobs):
                frame = pd.DataFrame(rows).drop_duplicates(
                    ["station_id", "variable", "year", "month"], keep="last"
                ).sort_values(["station_id", "variable", "year", "month"])
                frame.to_csv(OUTPUT, index=False)
                print(f"CHELSA aux stations : {number}/{len(jobs)} fichiers restants", flush=True)
    print(f"Écrit : {OUTPUT}")


if __name__ == "__main__":
    main()
