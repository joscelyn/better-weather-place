#!/usr/bin/env python3
"""Validate CERRA sunshine against WMO 1991-2020 normals north of 65 N.

The WMO/NCEI composite is an official in-situ reference. Open-Meteo is used
only as a convenient validation adapter for CERRA; it is not an application
dependency. Requests are split into small batches and cached locally.
"""

from __future__ import annotations

import json
import time
from pathlib import Path

import numpy as np
import pandas as pd
import requests


ROOT = Path(__file__).resolve().parents[2]
CACHE = ROOT / "work" / "validation" / "cache" / "northern_sunshine"
CACHE.mkdir(parents=True, exist_ok=True)

WMO_URL = (
    "https://www.nodc.noaa.gov/archive/arc0216/0253808/6.6/data/0-data/"
    "data-composite-primary-parameters-min24/"
    "wmo_normals_9120_TSUN_min24.csv"
)
MONTH_COLUMNS = [
    "Jan", "Feb", "Mar", "Apr", "May", "Jun",
    "Jul", "Aug", "Sep", "Oct", "Nov", "Dec",
]


def load_wmo_north() -> pd.DataFrame:
    path = CACHE / "wmo_normals_9120_TSUN_min24.csv"
    if not path.exists():
        response = requests.get(WMO_URL, timeout=90)
        response.raise_for_status()
        path.write_bytes(response.content)

    frame = pd.read_csv(path, skipinitialspace=True)
    frame.columns = frame.columns.str.strip()
    for column in ("Country", "Station"):
        frame[column] = frame[column].astype(str).str.strip()

    # Complete stations in the northern part of the app's European domain.
    frame = frame[
        frame["Latitude"].between(65, 72)
        & frame["Longitude"].between(-25, 35)
        & (frame[MONTH_COLUMNS] >= 0).all(axis=1)
    ].copy()
    frame = frame.sort_values(["Longitude", "Latitude"]).reset_index(drop=True)
    return frame


def fetch_cerra_batch(points: pd.DataFrame, batch_number: int) -> list[dict]:
    path = CACHE / f"cerra_wmo_north_1991_2020_batch_{batch_number}.json"
    if path.exists():
        return json.loads(path.read_text())

    params = {
        "latitude": ",".join(points["Latitude"].astype(str)),
        "longitude": ",".join(points["Longitude"].astype(str)),
        "start_date": "1991-01-01",
        "end_date": "2020-12-31",
        "daily": "sunshine_duration",
        "models": "cerra",
        "timezone": "GMT",
        # Preserve the native CERRA grid rather than applying point elevation
        # downscaling by the adapter.
        "elevation": ",".join("nan" for _ in range(len(points))),
    }
    for attempt, delay in enumerate((5, 15, 30, 60), start=1):
        response = requests.get(
            "https://archive-api.open-meteo.com/v1/archive",
            params=params,
            timeout=300,
        )
        if response.status_code == 429:
            print(f"Limitation API, nouvel essai {attempt} dans {delay}s", flush=True)
            time.sleep(delay)
            continue
        response.raise_for_status()
        data = response.json()
        if not isinstance(data, list) or len(data) != len(points):
            raise RuntimeError("Réponse CERRA multi-points inattendue")
        path.write_text(json.dumps(data))
        return data
    raise RuntimeError("Limitation CERRA persistante")


def cerra_normals(stations: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict] = []
    batch_size = 5
    for batch_number, start in enumerate(range(0, len(stations), batch_size), start=1):
        points = stations.iloc[start : start + batch_size]
        payloads = fetch_cerra_batch(points, batch_number)
        for station, payload in zip(points.itertuples(index=False), payloads):
            daily = pd.DataFrame(payload["daily"])
            daily["time"] = pd.to_datetime(daily["time"])
            daily["year"] = daily["time"].dt.year
            daily["month"] = daily["time"].dt.month
            daily["sunshine_hours"] = daily["sunshine_duration"] / 3600.0
            yearly = daily.groupby(["year", "month"], as_index=False)["sunshine_hours"].sum()
            normal = yearly.groupby("month", as_index=False)["sunshine_hours"].mean()
            for value in normal.itertuples(index=False):
                rows.append(
                    {
                        "station": station.Station,
                        "country": station.Country,
                        "latitude": station.Latitude,
                        "longitude": station.Longitude,
                        "elevation_m": station.Elevation,
                        "month": int(value.month),
                        "cerra_1991_2020_hours": float(value.sunshine_hours),
                    }
                )
            print(f"CERRA 1991-2020 : {station.Station}", flush=True)
    return pd.DataFrame(rows)


def wmo_long(stations: pd.DataFrame) -> pd.DataFrame:
    renamed = stations.rename(columns={column: month for month, column in enumerate(MONTH_COLUMNS, 1)})
    return renamed.melt(
        id_vars=["Country", "Station", "Latitude", "Longitude", "Elevation"],
        value_vars=list(range(1, 13)),
        var_name="month",
        value_name="wmo_1991_2020_hours",
    ).rename(
        columns={
            "Country": "country",
            "Station": "station",
            "Latitude": "latitude",
            "Longitude": "longitude",
            "Elevation": "elevation_m",
        }
    )


def monthly_correction(comparison: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for month, sample in comparison.groupby("month"):
        x = sample["cerra_1991_2020_hours"].to_numpy()
        y = sample["wmo_1991_2020_hours"].to_numpy()
        factor = float(np.dot(x, y) / np.dot(x, x))

        # Leave one station out: each prediction is made with a factor fitted
        # on the other northern stations.
        loo_predictions = []
        for held_out in range(len(sample)):
            keep = np.arange(len(sample)) != held_out
            loo_factor = float(np.dot(x[keep], y[keep]) / np.dot(x[keep], x[keep]))
            loo_predictions.append(x[held_out] * loo_factor)
        loo_predictions = np.asarray(loo_predictions)

        rows.append(
            {
                "month": int(month),
                "stations": len(sample),
                "multiplicative_factor": factor,
                "mae_raw_hours": float(np.mean(np.abs(x - y))),
                "mae_fitted_hours": float(np.mean(np.abs(x * factor - y))),
                "mae_leave_one_station_out_hours": float(np.mean(np.abs(loo_predictions - y))),
                "max_leave_one_station_out_error_hours": float(np.max(np.abs(loo_predictions - y))),
            }
        )
    return pd.DataFrame(rows)


def main() -> None:
    stations = load_wmo_north()
    print(f"Stations WMO complètes au nord de 65°N : {len(stations)}", flush=True)
    comparison = cerra_normals(stations).merge(
        wmo_long(stations),
        on=["station", "country", "latitude", "longitude", "elevation_m", "month"],
        how="inner",
    )
    corrections = monthly_correction(comparison)
    comparison = comparison.merge(
        corrections[["month", "multiplicative_factor"]], on="month", how="left"
    )
    comparison["cerra_corrected_hours"] = (
        comparison["cerra_1991_2020_hours"] * comparison["multiplicative_factor"]
    )
    comparison["raw_error_hours"] = (
        comparison["cerra_1991_2020_hours"] - comparison["wmo_1991_2020_hours"]
    )
    comparison["corrected_error_hours"] = (
        comparison["cerra_corrected_hours"] - comparison["wmo_1991_2020_hours"]
    )

    comparison_path = ROOT / "outputs" / "comparaison-cerra-wmo-ensoleillement-nord.csv"
    correction_path = ROOT / "outputs" / "correction-cerra-wmo-ensoleillement-nord.csv"
    station_path = ROOT / "outputs" / "synthese-stations-ensoleillement-nord.csv"
    comparison.to_csv(comparison_path, index=False)
    corrections.to_csv(correction_path, index=False)

    station_summary = comparison.groupby(
        ["station", "country", "latitude", "longitude", "elevation_m"], as_index=False
    ).agg(
        wmo_annual_hours=("wmo_1991_2020_hours", "sum"),
        cerra_annual_hours=("cerra_1991_2020_hours", "sum"),
        corrected_annual_hours=("cerra_corrected_hours", "sum"),
        monthly_mae_raw_hours=("raw_error_hours", lambda values: float(np.mean(np.abs(values)))),
        monthly_mae_corrected_hours=(
            "corrected_error_hours", lambda values: float(np.mean(np.abs(values)))
        ),
    )
    station_summary.to_csv(station_path, index=False)

    print("\nValidation croisée mensuelle :")
    print(corrections.to_string(index=False))
    print("\nSynthèse par station :")
    print(station_summary.to_string(index=False))
    print(f"\nÉcrit : {comparison_path}")
    print(f"Écrit : {correction_path}")
    print(f"Écrit : {station_path}")


if __name__ == "__main__":
    main()
