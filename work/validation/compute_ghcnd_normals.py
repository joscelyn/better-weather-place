#!/usr/bin/env python3
"""Compute 1991-2020 monthly normals for selected GHCN-Daily stations.

Raw GHCN-Daily values use tenths of degrees Celsius for TMAX/TMIN and
tenths of millimetres for PRCP. Values carrying a non-empty NOAA quality
flag are excluded. Monthly temperature means require at least 80% of the
days; precipitation totals and rainy-day counts require at least 90%.
"""

from __future__ import annotations

from calendar import monthrange
from pathlib import Path

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[2]
CACHE = ROOT / "work" / "validation" / "cache" / "ghcnd" / "stations"
START = pd.Timestamp("1991-01-01")
END = pd.Timestamp("2020-12-31")
MIN_VALID_YEARS = 24


def clear_quality_failures(frame: pd.DataFrame, element: str) -> None:
    attributes = f"{element}_ATTRIBUTES"
    if attributes not in frame:
        return
    # NOAA attributes are MFLAG,QFLAG,SFLAG; only QFLAG invalidates a value.
    qflag = frame[attributes].fillna(",,").astype(str).str.split(",").str[1]
    frame.loc[qflag.fillna("").ne(""), element] = np.nan


def comparability(row: pd.Series) -> tuple[str, str]:
    reasons = []
    if row["minimum_coverage"] < 0.80:
        reasons.append("couverture inférieure à 80 %")
    if row["distance_km"] > 100:
        reasons.append("distance supérieure à 100 km")
    if row["elevation_difference_m"] > 500:
        reasons.append("écart d'altitude supérieur à 500 m")
    if reasons:
        return "non_comparable", "; ".join(reasons)
    if (
        row["minimum_coverage"] >= 0.90
        and row["distance_km"] <= 50
        and row["elevation_difference_m"] <= 250
    ):
        return "bonne", ""
    return "indicative", "distance, altitude ou couverture à interpréter avec prudence"


def station_monthly_normals(station_id: str) -> pd.DataFrame:
    path = CACHE / f"{station_id}.csv"
    usecols = [
        "DATE",
        "PRCP",
        "PRCP_ATTRIBUTES",
        "TMAX",
        "TMAX_ATTRIBUTES",
        "TMIN",
        "TMIN_ATTRIBUTES",
    ]
    frame = pd.read_csv(path, usecols=lambda column: column in usecols, low_memory=False)
    frame["DATE"] = pd.to_datetime(frame["DATE"])
    frame = frame[frame["DATE"].between(START, END)].copy()
    for element in ["PRCP", "TMAX", "TMIN"]:
        if element not in frame:
            frame[element] = np.nan
        clear_quality_failures(frame, element)
        frame[element] = pd.to_numeric(frame[element], errors="coerce") / 10.0

    frame["tmean_c"] = (frame["TMAX"] + frame["TMIN"]) / 2.0
    frame["year"] = frame["DATE"].dt.year
    frame["month"] = frame["DATE"].dt.month
    frame["days_in_month"] = [
        monthrange(year, month)[1]
        for year, month in zip(frame["year"], frame["month"])
    ]

    yearly_rows = []
    for (year, month), group in frame.groupby(["year", "month"]):
        days = int(group["days_in_month"].iloc[0])
        temp_days = int(group["tmean_c"].notna().sum())
        precip_days = int(group["PRCP"].notna().sum())
        yearly_rows.append(
            {
                "year": year,
                "month": month,
                "tmean_c": group["tmean_c"].mean() if temp_days / days >= 0.80 else np.nan,
                "tmax_c": group["TMAX"].mean() if group["TMAX"].notna().sum() / days >= 0.80 else np.nan,
                "tmin_c": group["TMIN"].mean() if group["TMIN"].notna().sum() / days >= 0.80 else np.nan,
                "precipitation_mm": group["PRCP"].sum() if precip_days / days >= 0.90 else np.nan,
                "rain_days_ge_1mm": (group["PRCP"] >= 1.0).sum() if precip_days / days >= 0.90 else np.nan,
            }
        )

    yearly = pd.DataFrame(yearly_rows)
    output_rows = []
    for month in range(1, 13):
        sample = yearly[yearly["month"] == month]
        row = {"station_id": station_id, "month": month}
        for variable in [
            "tmean_c",
            "tmax_c",
            "tmin_c",
            "precipitation_mm",
            "rain_days_ge_1mm",
        ]:
            valid_years = int(sample[variable].notna().sum())
            row[variable] = sample[variable].mean() if valid_years >= MIN_VALID_YEARS else np.nan
            row[f"{variable}_valid_years"] = valid_years
        output_rows.append(row)
    return pd.DataFrame(output_rows)


def main() -> None:
    selected_path = ROOT / "work" / "validation" / "ghcnd_selected_stations.csv"
    selected = pd.read_csv(selected_path)
    labels = selected.apply(comparability, axis=1, result_type="expand")
    selected[["comparability", "comparability_note"]] = labels

    unique_normals = pd.concat(
        [station_monthly_normals(station_id) for station_id in selected["station_id"].unique()],
        ignore_index=True,
    )
    normals = selected.merge(unique_normals, on="station_id", how="left")

    metadata_output = ROOT / "work" / "validation" / "ghcnd_station_metadata.csv"
    normals_output = ROOT / "work" / "validation" / "ghcnd_monthly_normals_1991_2020.csv"
    selected.to_csv(metadata_output, index=False)
    normals.to_csv(normals_output, index=False)

    print(selected[[
        "point", "station_name", "distance_km", "elevation_difference_m",
        "minimum_coverage", "comparability", "comparability_note"
    ]].to_string(index=False))
    print(f"\nÉcrit : {metadata_output}")
    print(f"Écrit : {normals_output}")
    print(f"Lignes de normales : {len(normals)}")


if __name__ == "__main__":
    main()
