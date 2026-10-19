#!/usr/bin/env python3
"""Extract a small, reproducible validation sample from CHELSA and CERRA.

This is an exploratory data-quality script, not application code. It reads only
January and July COG blocks from CHELSA and point time series exposed by
Open-Meteo's CERRA archive adapter. Raw responses are cached locally.
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
CACHE = ROOT / "work" / "validation" / "cache"
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

CHELSA_VARS = ("tas", "tasmax", "tasmin", "pr")
MONTHS = (1, 7)
YEARS = range(1991, 2021)


def chelsa_url(variable: str, year: int, month: int) -> str:
    return (
        "https://os.unil.cloud.switch.ch/chelsa02/chelsa/global/monthly/"
        f"{variable}/{year}/CHELSA_{variable}_{month:02d}_{year}_V.2.1.tif"
    )


def read_chelsa_file(variable: str, year: int, month: int) -> list[dict]:
    url = chelsa_url(variable, year, month)
    env_options = {
        "GDAL_DISABLE_READDIR_ON_OPEN": "EMPTY_DIR",
        "CPL_VSIL_CURL_ALLOWED_EXTENSIONS": ".tif",
        "GDAL_HTTP_MAX_RETRY": "4",
        "GDAL_HTTP_RETRY_DELAY": "1",
    }
    with rasterio.Env(**env_options), rasterio.open(url) as src:
        coords = [(lon, lat) for _, _, lat, lon in POINTS]
        raw_values = [sample[0] for sample in src.sample(coords)]
        scale = src.scales[0]
        offset = src.offsets[0]
        nodata = src.nodata

    rows = []
    for (region, name, lat, lon), raw in zip(POINTS, raw_values):
        value = np.nan if raw == nodata else float(raw) * scale + offset
        if variable.startswith("tas") and np.isfinite(value):
            value -= 273.15
        rows.append(
            {
                "region": region,
                "point": name,
                "latitude": lat,
                "longitude": lon,
                "year": year,
                "month": month,
                "variable": variable,
                "value": value,
                "source_url": url,
            }
        )
    return rows


def extract_chelsa() -> pd.DataFrame:
    output = ROOT / "work" / "validation" / "chelsa_points_jan_jul_1991_2020.csv"
    if output.exists():
        return pd.read_csv(output)

    jobs = [
        (variable, year, month)
        for variable in CHELSA_VARS
        for year in YEARS
        for month in MONTHS
    ]
    rows: list[dict] = []
    with ThreadPoolExecutor(max_workers=4) as pool:
        futures = {pool.submit(read_chelsa_file, *job): job for job in jobs}
        for done, future in enumerate(as_completed(futures), start=1):
            job = futures[future]
            try:
                rows.extend(future.result())
            except Exception as exc:
                raise RuntimeError(f"CHELSA extraction failed for {job}: {exc}") from exc
            if done % 20 == 0 or done == len(jobs):
                print(f"CHELSA {done}/{len(jobs)} files", flush=True)

    frame = pd.DataFrame(rows).sort_values(["point", "variable", "year", "month"])
    frame.to_csv(output, index=False)
    return frame


def fetch_cerra_point(region: str, name: str, lat: float, lon: float) -> dict:
    cache_file = CACHE / f"cerra_{name.lower().replace('-', '_')}_1991_2020.json"
    if cache_file.exists():
        return json.loads(cache_file.read_text())

    params = {
        "latitude": lat,
        "longitude": lon,
        "start_date": "1991-01-01",
        "end_date": "2020-12-31",
        "daily": (
            "temperature_2m_mean,temperature_2m_max,temperature_2m_min,"
            "precipitation_sum,sunshine_duration"
        ),
        "models": "cerra",
        "timezone": "GMT",
        "elevation": "nan",
    }
    url = "https://archive-api.open-meteo.com/v1/archive"
    for attempt in range(5):
        response = requests.get(url, params=params, timeout=180)
        if response.status_code == 429:
            time.sleep(3 * (attempt + 1))
            continue
        response.raise_for_status()
        data = response.json()
        cache_file.write_text(json.dumps(data))
        return data
    raise RuntimeError(f"Open-Meteo rate limit persisted for {name}")


def fetch_cerra_batch(start_date: str, end_date: str) -> list[dict]:
    """Fetch every validation point in one API request to minimise rate limits."""
    cache_file = CACHE / f"cerra_batch_{start_date}_{end_date}.json"
    if cache_file.exists():
        return json.loads(cache_file.read_text())

    params = {
        "latitude": ",".join(str(point[2]) for point in POINTS),
        "longitude": ",".join(str(point[3]) for point in POINTS),
        "start_date": start_date,
        "end_date": end_date,
        "daily": (
            "temperature_2m_mean,temperature_2m_max,temperature_2m_min,"
            "precipitation_sum,sunshine_duration"
        ),
        "models": "cerra",
        "timezone": "GMT",
        "elevation": ",".join("nan" for _ in POINTS),
    }
    url = "https://archive-api.open-meteo.com/v1/archive"
    for attempt, delay in enumerate((10, 20, 40, 60), start=1):
        response = requests.get(url, params=params, timeout=300)
        if response.status_code == 429:
            print(f"CERRA batch rate-limited; retry {attempt} in {delay}s", flush=True)
            time.sleep(delay)
            continue
        response.raise_for_status()
        data = response.json()
        if not isinstance(data, list) or len(data) != len(POINTS):
            raise RuntimeError("Unexpected multi-location CERRA response")
        cache_file.write_text(json.dumps(data))
        return data
    raise RuntimeError(f"Open-Meteo rate limit persisted for batch {start_date}/{end_date}")


def extract_cerra() -> tuple[pd.DataFrame, pd.DataFrame]:
    daily_output = ROOT / "work" / "validation" / "cerra_points_daily_1991_2020.csv"
    monthly_output = ROOT / "work" / "validation" / "cerra_points_monthly_1991_2020.csv"
    if daily_output.exists() and monthly_output.exists():
        return pd.read_csv(daily_output), pd.read_csv(monthly_output)

    period_batches = [
        fetch_cerra_batch("1991-01-01", "2005-12-31"),
        fetch_cerra_batch("2006-01-01", "2020-12-31"),
    ]
    daily_frames = []
    for index, (region, name, lat, lon) in enumerate(POINTS, start=1):
        point_periods = []
        for batch in period_batches:
            data = batch[index - 1]
            daily = pd.DataFrame(data["daily"])
            daily["grid_latitude"] = data["latitude"]
            daily["grid_longitude"] = data["longitude"]
            daily["grid_elevation"] = data.get("elevation")
            point_periods.append(daily)
        daily = pd.concat(point_periods, ignore_index=True)
        daily["time"] = pd.to_datetime(daily["time"])
        daily["region"] = region
        daily["point"] = name
        daily["requested_latitude"] = lat
        daily["requested_longitude"] = lon
        daily_frames.append(daily)
        print(f"CERRA {index}/{len(POINTS)} points", flush=True)

    all_daily = pd.concat(daily_frames, ignore_index=True)
    all_daily.to_csv(daily_output, index=False)
    all_daily["year"] = all_daily["time"].dt.year
    all_daily["month"] = all_daily["time"].dt.month
    all_daily["rain_day"] = all_daily["precipitation_sum"] >= 1.0

    monthly_by_year = (
        all_daily.groupby(["region", "point", "year", "month"], as_index=False)
        .agg(
            temperature_mean_c=("temperature_2m_mean", "mean"),
            temperature_max_c=("temperature_2m_max", "mean"),
            temperature_min_c=("temperature_2m_min", "mean"),
            precipitation_mm=("precipitation_sum", "sum"),
            rainy_days=("rain_day", "sum"),
            sunshine_seconds=("sunshine_duration", "sum"),
        )
    )
    monthly = (
        monthly_by_year.groupby(["region", "point", "month"], as_index=False)
        .agg(
            temperature_mean_c=("temperature_mean_c", "mean"),
            temperature_max_c=("temperature_max_c", "mean"),
            temperature_min_c=("temperature_min_c", "mean"),
            precipitation_mm=("precipitation_mm", "mean"),
            rainy_days=("rainy_days", "mean"),
            sunshine_seconds=("sunshine_seconds", "mean"),
            years=("year", "nunique"),
        )
    )
    monthly["sunshine_hours"] = monthly["sunshine_seconds"] / 3600.0
    monthly.drop(columns=["sunshine_seconds"]).to_csv(monthly_output, index=False)
    return all_daily, monthly.drop(columns=["sunshine_seconds"])


def extract_sarah_normals() -> pd.DataFrame:
    """Read official SARAH-3 1991-2020 sunshine normals from EUMETSAT CAN."""
    output = ROOT / "work" / "validation" / "sarah3_sunshine_normals_points.csv"
    if output.exists():
        return pd.read_csv(output)

    rows = []
    url = "https://can.eumetsat.int/wms"
    for index, (region, name, lat, lon) in enumerate(POINTS, start=1):
        params = {
            "request": "GetTimeSeries",
            "service": "WMS",
            "version": "1.1.1",
            "lon": lon,
            "lat": lat,
            "units": "h",
            "layers": "Normals/CM/SDU",
            "HORIZONTAL_DEGREES_SPACING": "0.05",
        }
        response = requests.get(url, params=params, timeout=60)
        response.raise_for_status()
        data = response.json()
        annual_cycle = data.get("model", {}).get("annualCycle", {})
        for month in range(1, 13):
            month_data = annual_cycle.get(str(month), {})
            value = next(iter(month_data.values()), None)
            rows.append(
                {
                    "region": region,
                    "point": name,
                    "latitude": lat,
                    "longitude": lon,
                    "month": month,
                    "sunshine_hours_sarah3": value,
                    "coverage_status": "available" if value is not None else "outside_or_missing",
                }
            )
        print(f"SARAH-3 {index}/{len(POINTS)} points", flush=True)

    frame = pd.DataFrame(rows)
    frame.to_csv(output, index=False)
    return frame


def build_comparison(
    chelsa: pd.DataFrame, cerra_monthly: pd.DataFrame, sarah: pd.DataFrame
) -> pd.DataFrame:
    chelsa_normal = (
        chelsa.groupby(["region", "point", "month", "variable"], as_index=False)
        .agg(chelsa_value=("value", "mean"), chelsa_years=("year", "nunique"))
    )
    chelsa_wide = chelsa_normal.pivot(
        index=["region", "point", "month"], columns="variable", values="chelsa_value"
    ).reset_index()
    comparison = chelsa_wide.merge(
        cerra_monthly[cerra_monthly["month"].isin(MONTHS)],
        on=["region", "point", "month"],
        how="left",
    )
    comparison = comparison.merge(
        sarah[["region", "point", "month", "sunshine_hours_sarah3"]],
        on=["region", "point", "month"],
        how="left",
    )
    comparison["delta_tas_chelsa_minus_cerra_c"] = (
        comparison["tas"] - comparison["temperature_mean_c"]
    )
    comparison["delta_tasmax_chelsa_minus_cerra_c"] = (
        comparison["tasmax"] - comparison["temperature_max_c"]
    )
    comparison["delta_tasmin_chelsa_minus_cerra_c"] = (
        comparison["tasmin"] - comparison["temperature_min_c"]
    )
    comparison["precip_ratio_chelsa_to_cerra"] = comparison["pr"] / comparison[
        "precipitation_mm"
    ].replace(0, np.nan)
    comparison["delta_sunshine_sarah_minus_cerra_h"] = (
        comparison["sunshine_hours_sarah3"] - comparison["sunshine_hours"]
    )
    output = ROOT / "work" / "validation" / "comparison_chelsa_cerra_jan_jul.csv"
    comparison.to_csv(output, index=False)
    return comparison


def main() -> None:
    print("Extracting CHELSA sample", flush=True)
    chelsa = extract_chelsa()
    print("Extracting SARAH-3 normals", flush=True)
    sarah = extract_sarah_normals()
    print("Extracting CERRA sample", flush=True)
    _, cerra_monthly = extract_cerra()
    comparison = build_comparison(chelsa, cerra_monthly, sarah)
    print(comparison.to_string(index=False, float_format=lambda value: f"{value:.2f}"))


if __name__ == "__main__":
    main()
