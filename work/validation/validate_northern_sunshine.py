#!/usr/bin/env python3
"""Test whether CERRA sunshine can be calibrated to SARAH-3 north of 65°N.

SARAH-3 1991-2020 normals are compared with CERRA-derived sunshine duration
for 1991-2005 in an overlap band. Open-Meteo is used only as a validation
adapter for CERRA, never as an application dependency.
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

POINTS = [
    ("Reykjavik", 64.147, -21.943, False),
    ("Torshavn", 62.010, -6.774, True),
    ("Lerwick", 60.155, -1.145, True),
    ("Bergen", 60.392, 5.323, True),
    ("Oslo", 59.914, 10.752, True),
    ("Stockholm", 59.329, 18.069, True),
    ("Helsinki", 60.170, 24.938, True),
    ("Tallinn", 59.437, 24.754, True),
    ("Trondheim", 63.430, 10.395, True),
    ("Sundsvall", 62.391, 17.306, True),
    ("Turku", 60.451, 22.267, True),
    ("Saint-Petersbourg", 59.934, 30.335, True),
    ("Tromso", 69.649, 18.956, False),
]


def fetch_sarah(name: str, latitude: float, longitude: float) -> dict:
    path = CACHE / f"sarah_{name.lower().replace('-', '_')}.json"
    if path.exists():
        return json.loads(path.read_text())
    response = requests.get(
        "https://can.eumetsat.int/wms",
        params={
            "request": "GetTimeSeries",
            "service": "WMS",
            "version": "1.1.1",
            "lon": longitude,
            "lat": latitude,
            "units": "h",
            "layers": "Normals/CM/SDU",
            "HORIZONTAL_DEGREES_SPACING": "0.05",
        },
        timeout=90,
    )
    response.raise_for_status()
    data = response.json()
    path.write_text(json.dumps(data))
    return data


def sarah_rows() -> list[dict]:
    rows = []
    for name, latitude, longitude, calibration in POINTS:
        if latitude > 65:
            continue
        data = fetch_sarah(name, latitude, longitude)
        annual_cycle = data.get("model", {}).get("annualCycle", {})
        for month in range(1, 13):
            month_data = annual_cycle.get(str(month), {})
            value = next(iter(month_data.values()), None)
            rows.append(
                {
                    "point": name,
                    "latitude": latitude,
                    "longitude": longitude,
                    "calibration_point": calibration,
                    "month": month,
                    "sarah_1991_2020_hours": value,
                }
            )
        print(f"SARAH-3 : {name}", flush=True)
    return rows


def fetch_cerra_batch() -> list[dict]:
    path = CACHE / "cerra_sunshine_1991_2005.json"
    if path.exists():
        return json.loads(path.read_text())
    params = {
        "latitude": ",".join(str(point[1]) for point in POINTS),
        "longitude": ",".join(str(point[2]) for point in POINTS),
        "start_date": "1991-01-01",
        "end_date": "2005-12-31",
        "daily": "sunshine_duration",
        "models": "cerra",
        "timezone": "GMT",
        "elevation": ",".join("nan" for _ in POINTS),
    }
    for attempt, delay in enumerate((5, 15, 30, 60), start=1):
        response = requests.get(
            "https://archive-api.open-meteo.com/v1/archive",
            params=params,
            timeout=300,
        )
        if response.status_code == 429:
            print(f"CERRA limité, nouvel essai {attempt} dans {delay}s", flush=True)
            time.sleep(delay)
            continue
        response.raise_for_status()
        data = response.json()
        if not isinstance(data, list) or len(data) != len(POINTS):
            raise RuntimeError("Réponse CERRA multi-points inattendue")
        path.write_text(json.dumps(data))
        return data
    raise RuntimeError("Limitation CERRA persistante")


def cerra_rows() -> list[dict]:
    data = fetch_cerra_batch()
    rows = []
    for point, payload in zip(POINTS, data):
        name, latitude, longitude, calibration = point
        daily = pd.DataFrame(payload["daily"])
        daily["time"] = pd.to_datetime(daily["time"])
        daily["year"] = daily["time"].dt.year
        daily["month"] = daily["time"].dt.month
        daily["sunshine_hours"] = daily["sunshine_duration"] / 3600.0
        yearly = daily.groupby(["year", "month"], as_index=False)["sunshine_hours"].sum()
        normal = yearly.groupby("month", as_index=False)["sunshine_hours"].mean()
        for row in normal.itertuples(index=False):
            rows.append(
                {
                    "point": name,
                    "latitude": latitude,
                    "longitude": longitude,
                    "calibration_point": calibration,
                    "month": int(row.month),
                    "cerra_1991_2005_hours": float(row.sunshine_hours),
                }
            )
        print(f"CERRA : {name}", flush=True)
    return rows


def main() -> None:
    sarah = pd.DataFrame(sarah_rows())
    cerra = pd.DataFrame(cerra_rows())
    comparison = cerra.merge(
        sarah[["point", "month", "sarah_1991_2020_hours"]],
        on=["point", "month"],
        how="left",
    )
    comparison["difference_sarah_minus_cerra_hours"] = (
        comparison["sarah_1991_2020_hours"] - comparison["cerra_1991_2005_hours"]
    )
    comparison["ratio_sarah_to_cerra"] = (
        comparison["sarah_1991_2020_hours"] / comparison["cerra_1991_2005_hours"]
    )
    comparison_path = ROOT / "outputs" / "comparaison-ensoleillement-nord.csv"
    comparison.to_csv(comparison_path, index=False)

    calibration = comparison[
        comparison["calibration_point"]
        & comparison["sarah_1991_2020_hours"].notna()
        & comparison["cerra_1991_2005_hours"].notna()
    ].copy()
    correction_rows = []
    for month in range(1, 13):
        sample = calibration[calibration["month"] == month]
        x = sample["cerra_1991_2005_hours"].to_numpy()
        y = sample["sarah_1991_2020_hours"].to_numpy()
        factor = float(np.dot(x, y) / np.dot(x, x))
        corrected = x * factor
        correction_rows.append(
            {
                "month": month,
                "calibration_points": len(sample),
                "multiplicative_factor": factor,
                "mae_uncorrected_hours": float(np.mean(np.abs(x - y))),
                "mae_corrected_hours": float(np.mean(np.abs(corrected - y))),
                "max_corrected_error_hours": float(np.max(np.abs(corrected - y))),
            }
        )
    corrections = pd.DataFrame(correction_rows)
    corrections_path = ROOT / "outputs" / "correction-ensoleillement-nord.csv"
    corrections.to_csv(corrections_path, index=False)

    tromso = comparison[comparison["point"] == "Tromso"].merge(corrections, on="month")
    tromso["sunshine_corrected_hours"] = (
        tromso["cerra_1991_2005_hours"] * tromso["multiplicative_factor"]
    )
    tromso["method_status"] = "rejected_after_wmo_validation"
    tromso["reason"] = (
        "single_overlap_factor_not_spatially_stable_north_of_65N"
    )
    tromso_path = ROOT / "outputs" / "estimation-ensoleillement-tromso.csv"
    tromso[[
        "point", "month", "cerra_1991_2005_hours", "multiplicative_factor",
        "sunshine_corrected_hours", "method_status", "reason",
    ]].to_csv(tromso_path, index=False)

    print("\nCorrection mensuelle :")
    print(corrections.to_string(index=False))
    print("\nEstimation Tromsø :")
    print(tromso[["month", "cerra_1991_2005_hours", "sunshine_corrected_hours"]].to_string(index=False))
    print(f"Écrit : {comparison_path}")
    print(f"Écrit : {corrections_path}")
    print(f"Écrit : {tromso_path}")


if __name__ == "__main__":
    main()
