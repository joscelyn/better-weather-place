#!/usr/bin/env python3
"""Validate CHELSA against WMO 1991-2020 normals across Morocco.

This closes the gap left by incomplete GHCN-Daily series in Morocco. The WMO
station normals use at least 24 years of the 1991-2020 reference period. No
Canary Islands data are read by this script.
"""

from __future__ import annotations

import json
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import numpy as np
import pandas as pd
import rasterio
import requests


ROOT = Path(__file__).resolve().parents[2]
VALIDATION = ROOT / "work" / "validation"
OUTPUTS = ROOT / "outputs"
CACHE = VALIDATION / "cache" / "wmo_morocco"
CHELSA_CACHE = CACHE / "chelsa_jobs"
CACHE.mkdir(parents=True, exist_ok=True)
CHELSA_CACHE.mkdir(parents=True, exist_ok=True)

YEARS = range(1991, 2021)
MONTHS = range(1, 13)
MONTH_COLUMNS = [
    "Jan", "Feb", "Mar", "Apr", "May", "Jun",
    "Jul", "Aug", "Sep", "Oct", "Nov", "Dec",
]
WMO_VARIABLES = ("TAVG", "TMAX", "TMIN", "PRCP", "DP01")
CHELSA_VARIABLES = ("tas", "tasmax", "tasmin", "pr")
VARIABLE_PAIRS = {
    "tas": "TAVG",
    "tasmax": "TMAX",
    "tasmin": "TMIN",
    "pr": "PRCP",
}


def wmo_url(variable: str) -> str:
    return (
        "https://www.nodc.noaa.gov/archive/arc0216/0253808/6.6/data/0-data/"
        "data-composite-primary-parameters-min24/"
        f"wmo_normals_9120_{variable}_min24.csv"
    )


def load_wmo_variable(variable: str) -> pd.DataFrame:
    path = CACHE / f"wmo_normals_9120_{variable}_min24.csv"
    if not path.exists():
        response = requests.get(wmo_url(variable), timeout=90)
        response.raise_for_status()
        path.write_bytes(response.content)
    frame = pd.read_csv(path, skipinitialspace=True)
    frame.columns = frame.columns.str.strip()
    for column in ("Country", "Station"):
        frame[column] = frame[column].astype(str).str.strip()
    frame["wmo_id"] = frame["ID"].astype(str).str.strip().str.zfill(8)
    return frame[frame["Country"] == "Morocco"].copy()


def load_wmo() -> tuple[pd.DataFrame, pd.DataFrame]:
    by_variable = {variable: load_wmo_variable(variable) for variable in WMO_VARIABLES}
    station_source = by_variable["TAVG"]
    stations = station_source[
        ["wmo_id", "Station", "Latitude", "Longitude", "Elevation"]
    ].rename(
        columns={
            "Station": "station",
            "Latitude": "latitude",
            "Longitude": "longitude",
            "Elevation": "elevation_m",
        }
    ).sort_values("wmo_id").reset_index(drop=True)

    rows = []
    for variable, frame in by_variable.items():
        for value in frame.itertuples(index=False):
            for month, column in enumerate(MONTH_COLUMNS, start=1):
                normal = float(getattr(value, column))
                rows.append(
                    {
                        "wmo_id": value.wmo_id,
                        "station": value.Station,
                        "month": month,
                        "wmo_variable": variable,
                        "wmo_value": np.nan if normal < 0 else normal,
                    }
                )
    return stations, pd.DataFrame(rows)


def chelsa_url(variable: str, year: int, month: int) -> str:
    return (
        "https://os.unil.cloud.switch.ch/chelsa02/chelsa/global/monthly/"
        f"{variable}/{year}/CHELSA_{variable}_{month:02d}_{year}_V.2.1.tif"
    )


def read_chelsa_job(
    stations: pd.DataFrame, variable: str, year: int, month: int
) -> list[dict]:
    cache_path = CHELSA_CACHE / f"{variable}_{year}_{month:02d}.json"
    if cache_path.exists():
        return json.loads(cache_path.read_text())

    url = chelsa_url(variable, year, month)
    options = {
        "GDAL_DISABLE_READDIR_ON_OPEN": "EMPTY_DIR",
        "CPL_VSIL_CURL_ALLOWED_EXTENSIONS": ".tif",
        "GDAL_HTTP_MAX_RETRY": "5",
        "GDAL_HTTP_RETRY_DELAY": "1",
        "GDAL_HTTP_CONNECTTIMEOUT": "10",
        "GDAL_HTTP_TIMEOUT": "30",
    }
    coordinates = list(zip(stations["longitude"], stations["latitude"]))
    last_error: Exception | None = None
    for delay in (0, 2, 5, 10, 20):
        if delay:
            time.sleep(delay)
        try:
            with rasterio.Env(**options), rasterio.open(url) as source:
                raw_values = [sample[0] for sample in source.sample(coordinates)]
                scale = source.scales[0]
                offset = source.offsets[0]
                nodata = source.nodata
            break
        except Exception as error:
            last_error = error
    else:
        raise RuntimeError(f"Lecture impossible après cinq essais : {url}") from last_error

    rows = []
    for station, raw in zip(stations.itertuples(index=False), raw_values):
        value = np.nan if raw == nodata else float(raw) * scale + offset
        if variable.startswith("tas") and np.isfinite(value):
            value -= 273.15
        rows.append(
            {
                "wmo_id": station.wmo_id,
                "station": station.station,
                "latitude": station.latitude,
                "longitude": station.longitude,
                "elevation_m": station.elevation_m,
                "year": year,
                "month": month,
                "chelsa_variable": variable,
                "chelsa_value": value,
            }
        )
    cache_path.write_text(json.dumps(rows, allow_nan=True))
    return rows


def extract_chelsa(stations: pd.DataFrame) -> pd.DataFrame:
    output = VALIDATION / "chelsa_at_wmo_morocco_1991_2020.csv"
    if output.exists():
        return pd.read_csv(output, dtype={"wmo_id": str})

    jobs = [
        (variable, year, month)
        for variable in CHELSA_VARIABLES
        for year in YEARS
        for month in MONTHS
    ]
    rows: list[dict] = []
    with ThreadPoolExecutor(max_workers=8) as pool:
        futures = {
            pool.submit(read_chelsa_job, stations, *job): job
            for job in jobs
        }
        for completed, future in enumerate(as_completed(futures), start=1):
            job = futures[future]
            try:
                rows.extend(future.result())
            except Exception as error:
                raise RuntimeError(f"Échec CHELSA pour {job}: {error}") from error
            if completed % 60 == 0 or completed == len(jobs):
                print(f"CHELSA Maroc : {completed}/{len(jobs)} fichiers", flush=True)

    frame = pd.DataFrame(rows).sort_values(
        ["wmo_id", "chelsa_variable", "year", "month"]
    )
    frame.to_csv(output, index=False)
    return frame


def build_comparison(chelsa: pd.DataFrame, wmo: pd.DataFrame) -> pd.DataFrame:
    normals = chelsa.groupby(
        [
            "wmo_id", "station", "latitude", "longitude", "elevation_m",
            "month", "chelsa_variable",
        ],
        as_index=False,
    ).agg(
        chelsa_value=("chelsa_value", "mean"),
        chelsa_years=("year", "nunique"),
    )
    normals["wmo_variable"] = normals["chelsa_variable"].map(VARIABLE_PAIRS)
    comparison = normals.merge(
        wmo,
        on=["wmo_id", "station", "month", "wmo_variable"],
        how="left",
    )
    comparison["difference_chelsa_minus_wmo"] = (
        comparison["chelsa_value"] - comparison["wmo_value"]
    )
    comparison["ratio_chelsa_to_wmo"] = np.where(
        comparison["wmo_variable"] == "PRCP",
        comparison["chelsa_value"] / comparison["wmo_value"].replace(0, np.nan),
        np.nan,
    )
    comparison["wet_reference_ge_10mm"] = np.where(
        comparison["wmo_variable"] == "PRCP",
        comparison["wmo_value"] >= 10,
        np.nan,
    )
    return comparison.sort_values(["wmo_id", "chelsa_variable", "month"])


def summarize(comparison: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for variable in ("TAVG", "TMAX", "TMIN"):
        sample = comparison[
            (comparison["wmo_variable"] == variable) & comparison["wmo_value"].notna()
        ]
        rows.append(
            {
                "variable": variable,
                "pairs": len(sample),
                "bias_chelsa_minus_wmo": sample["difference_chelsa_minus_wmo"].mean(),
                "mae": sample["difference_chelsa_minus_wmo"].abs().mean(),
                "p90_absolute_error": sample["difference_chelsa_minus_wmo"].abs().quantile(0.9),
                "median_ratio_wet": np.nan,
                "p10_ratio_wet": np.nan,
                "p90_ratio_wet": np.nan,
                "mae_dry": np.nan,
            }
        )

    precip = comparison[
        (comparison["wmo_variable"] == "PRCP") & comparison["wmo_value"].notna()
    ]
    wet = precip[precip["wmo_value"] >= 10]
    dry = precip[precip["wmo_value"] < 10]
    rows.append(
        {
            "variable": "PRCP",
            "pairs": len(precip),
            "bias_chelsa_minus_wmo": wet["difference_chelsa_minus_wmo"].mean(),
            "mae": wet["difference_chelsa_minus_wmo"].abs().mean(),
            "p90_absolute_error": wet["difference_chelsa_minus_wmo"].abs().quantile(0.9),
            "median_ratio_wet": wet["ratio_chelsa_to_wmo"].median(),
            "p10_ratio_wet": wet["ratio_chelsa_to_wmo"].quantile(0.1),
            "p90_ratio_wet": wet["ratio_chelsa_to_wmo"].quantile(0.9),
            "mae_dry": dry["difference_chelsa_minus_wmo"].abs().mean(),
        }
    )
    return pd.DataFrame(rows)


def main() -> None:
    stations, wmo = load_wmo()
    print(f"Stations marocaines WMO : {len(stations)}", flush=True)
    chelsa = extract_chelsa(stations)
    comparison = build_comparison(chelsa, wmo)
    summary = summarize(comparison)

    station_path = OUTPUTS / "stations-wmo-maroc-1991-2020.csv"
    comparison_path = OUTPUTS / "comparaison-chelsa-wmo-maroc.csv"
    summary_path = OUTPUTS / "synthese-chelsa-wmo-maroc.csv"
    stations.to_csv(station_path, index=False)
    comparison.to_csv(comparison_path, index=False)
    summary.to_csv(summary_path, index=False)

    print("\nSynthèse CHELSA/WMO Maroc :")
    print(summary.to_string(index=False))
    print(f"\nÉcrit : {station_path}")
    print(f"Écrit : {comparison_path}")
    print(f"Écrit : {summary_path}")


if __name__ == "__main__":
    main()
