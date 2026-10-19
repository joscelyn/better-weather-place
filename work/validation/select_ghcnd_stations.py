#!/usr/bin/env python3
"""Select complete NOAA GHCN-Daily stations near the validation points.

Candidates must advertise PRCP, TMAX and TMIN coverage over 1991-2020. The
script then checks their actual daily CSV data and favours stations that are
both geographically close and reasonably similar in elevation.
"""

from __future__ import annotations

import math
from pathlib import Path

import pandas as pd
import requests


ROOT = Path(__file__).resolve().parents[2]
CACHE = ROOT / "work" / "validation" / "cache" / "ghcnd"
CACHE.mkdir(parents=True, exist_ok=True)

BASE = "https://www.ncei.noaa.gov/pub/data/ghcn/daily"
ACCESS = (
    "https://www.ncei.noaa.gov/data/"
    "global-historical-climatology-network-daily/access"
)
PERIOD_START = pd.Timestamp("1991-01-01")
PERIOD_END = pd.Timestamp("2020-12-31")
REQUIRED_ELEMENTS = {"PRCP", "TMAX", "TMIN"}


def download(url: str, path: Path) -> None:
    if path.exists() and path.stat().st_size:
        return
    partial = path.with_suffix(path.suffix + ".part")
    with requests.get(url, stream=True, timeout=180) as response:
        response.raise_for_status()
        with partial.open("wb") as target:
            for chunk in response.iter_content(1024 * 1024):
                target.write(chunk)
    partial.replace(path)


def parse_stations(path: Path) -> pd.DataFrame:
    rows = []
    for line in path.read_text(errors="replace").splitlines():
        try:
            rows.append(
                {
                    "station_id": line[0:11].strip(),
                    "latitude": float(line[12:20]),
                    "longitude": float(line[21:30]),
                    "elevation_m": float(line[31:37]),
                    "station_name": line[41:71].strip(),
                }
            )
        except ValueError:
            continue
    return pd.DataFrame(rows)


def parse_inventory(path: Path) -> pd.DataFrame:
    rows = []
    for line in path.read_text(errors="replace").splitlines():
        try:
            rows.append(
                {
                    "station_id": line[0:11].strip(),
                    "element": line[31:35].strip(),
                    "first_year": int(line[36:40]),
                    "last_year": int(line[41:45]),
                }
            )
        except ValueError:
            continue
    return pd.DataFrame(rows)


def haversine_km(lat1: float, lon1: float, lat2, lon2):
    radius_km = 6371.0088
    phi1 = math.radians(lat1)
    phi2 = pd.Series(lat2).map(math.radians)
    d_phi = phi2 - phi1
    d_lambda = pd.Series(lon2).map(lambda value: math.radians(value - lon1))
    a = (
        (d_phi / 2).map(math.sin) ** 2
        + math.cos(phi1) * phi2.map(math.cos) * (d_lambda / 2).map(math.sin) ** 2
    )
    return 2 * radius_km * a.map(math.sqrt).map(math.asin)


def candidate_stations() -> pd.DataFrame:
    stations_path = CACHE / "ghcnd-stations.txt"
    inventory_path = CACHE / "ghcnd-inventory.txt"
    download(f"{BASE}/ghcnd-stations.txt", stations_path)
    download(f"{BASE}/ghcnd-inventory.txt", inventory_path)

    stations = parse_stations(stations_path)
    inventory = parse_inventory(inventory_path)
    eligible = inventory[
        inventory["element"].isin(REQUIRED_ELEMENTS)
        & (inventory["first_year"] <= 1991)
        & (inventory["last_year"] >= 2020)
    ]
    coverage = eligible.groupby("station_id")["element"].agg(set)
    station_ids = coverage[coverage.map(REQUIRED_ELEMENTS.issubset)].index
    return stations[stations["station_id"].isin(station_ids)].copy()


def actual_completeness(station_id: str) -> dict:
    path = CACHE / "stations" / f"{station_id}.csv"
    path.parent.mkdir(exist_ok=True)
    download(f"{ACCESS}/{station_id}.csv", path)
    frame = pd.read_csv(path, low_memory=False)
    frame["DATE"] = pd.to_datetime(frame["DATE"])
    frame = frame[frame["DATE"].between(PERIOD_START, PERIOD_END)]
    result = {"station_rows": len(frame)}
    expected_days = (PERIOD_END - PERIOD_START).days + 1
    for element in sorted(REQUIRED_ELEMENTS):
        available = int(frame[element].notna().sum()) if element in frame else 0
        result[f"{element.lower()}_available_days"] = available
        result[f"{element.lower()}_coverage"] = available / expected_days
    result["minimum_coverage"] = min(
        result[f"{element.lower()}_coverage"] for element in REQUIRED_ELEMENTS
    )
    return result


def main() -> None:
    candidates = candidate_stations()
    points = pd.read_csv(ROOT / "outputs" / "altitudes-points-tests.csv")
    selected_rows = []

    for _, point in points.iterrows():
        nearby = candidates.copy()
        nearby["distance_km"] = haversine_km(
            point["latitude"],
            point["longitude"],
            nearby["latitude"],
            nearby["longitude"],
        ).values
        nearby["elevation_difference_m"] = (
            nearby["elevation_m"] - point["elevation_m"]
        ).abs()
        nearby = nearby[nearby["distance_km"] <= 150].copy()
        nearby["selection_score"] = (
            nearby["distance_km"] + 0.02 * nearby["elevation_difference_m"]
        )
        nearby = nearby.sort_values(["selection_score", "distance_km"]).head(8)

        checked = []
        for _, station in nearby.iterrows():
            try:
                completeness = actual_completeness(station["station_id"])
            except (requests.RequestException, pd.errors.ParserError) as exc:
                print(f"Station ignorée {station['station_id']}: {exc}", flush=True)
                continue
            checked.append({**station.to_dict(), **completeness})
            if completeness["minimum_coverage"] >= 0.90:
                break

        if not checked:
            print(f"Aucune station utilisable pour {point['point']}", flush=True)
            continue

        checked_frame = pd.DataFrame(checked)
        complete = checked_frame[checked_frame["minimum_coverage"] >= 0.80]
        pool = complete if not complete.empty else checked_frame
        selected = pool.sort_values(
            ["selection_score", "minimum_coverage"], ascending=[True, False]
        ).iloc[0]
        selected_rows.append(
            {
                "region": point["region"],
                "point": point["point"],
                "point_latitude": point["latitude"],
                "point_longitude": point["longitude"],
                "point_elevation_m": point["elevation_m"],
                **selected.to_dict(),
            }
        )
        print(
            f"{point['point']}: {selected['station_name']} "
            f"({selected['distance_km']:.1f} km, {selected['minimum_coverage']:.1%})",
            flush=True,
        )

    output = ROOT / "work" / "validation" / "ghcnd_selected_stations.csv"
    pd.DataFrame(selected_rows).to_csv(output, index=False)
    print(f"Écrit : {output}")


if __name__ == "__main__":
    main()
