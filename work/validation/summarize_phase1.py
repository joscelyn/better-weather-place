#!/usr/bin/env python3
"""Build phase-1 comparison tables from the cached validation samples."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[2]
VALIDATION = ROOT / "work" / "validation"
OUTPUTS = ROOT / "outputs"
OUTPUTS.mkdir(parents=True, exist_ok=True)

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


def aggregate_cerra_1991_2005() -> pd.DataFrame:
    cache_file = VALIDATION / "cache" / "cerra_batch_1991-01-01_2005-12-31.json"
    batches = json.loads(cache_file.read_text())
    frames = []
    for index, (region, name, lat, lon) in enumerate(POINTS):
        payload = batches[index]
        frame = pd.DataFrame(payload["daily"])
        frame["date"] = pd.to_datetime(frame["time"])
        frame["region"] = region
        frame["point"] = name
        frame["year"] = frame["date"].dt.year
        frame["month"] = frame["date"].dt.month
        frame["rain_day"] = frame["precipitation_sum"] >= 1.0
        frames.append(frame)
    daily = pd.concat(frames, ignore_index=True)
    by_year_month = (
        daily.groupby(["region", "point", "year", "month"], as_index=False)
        .agg(
            cerra_tmean_c=("temperature_2m_mean", "mean"),
            cerra_tmax_c=("temperature_2m_max", "mean"),
            cerra_tmin_c=("temperature_2m_min", "mean"),
            cerra_precip_mm=("precipitation_sum", "sum"),
            cerra_rainy_days=("rain_day", "sum"),
            cerra_sunshine_seconds=("sunshine_duration", "sum"),
        )
    )
    normals = (
        by_year_month.groupby(["region", "point", "month"], as_index=False)
        .agg(
            cerra_tmean_c=("cerra_tmean_c", "mean"),
            cerra_tmax_c=("cerra_tmax_c", "mean"),
            cerra_tmin_c=("cerra_tmin_c", "mean"),
            cerra_precip_mm=("cerra_precip_mm", "mean"),
            cerra_rainy_days=("cerra_rainy_days", "mean"),
            cerra_sunshine_seconds=("cerra_sunshine_seconds", "mean"),
            cerra_years=("year", "nunique"),
        )
    )
    normals["cerra_sunshine_hours"] = normals["cerra_sunshine_seconds"] / 3600.0
    return normals.drop(columns="cerra_sunshine_seconds")


def aggregate_chelsa(end_year: int | None = None) -> pd.DataFrame:
    chelsa = pd.read_csv(VALIDATION / "chelsa_points_jan_jul_1991_2020.csv")
    if end_year is not None:
        chelsa = chelsa[chelsa["year"] <= end_year]
    normal = (
        chelsa.groupby(["region", "point", "month", "variable"], as_index=False)
        .agg(value=("value", "mean"), chelsa_years=("year", "nunique"))
    )
    return normal.pivot(
        index=["region", "point", "month"], columns="variable", values="value"
    ).reset_index()


def main() -> None:
    cerra = aggregate_cerra_1991_2005()
    chelsa = aggregate_chelsa(end_year=2005)
    chelsa_full = aggregate_chelsa()
    cerra_land = pd.read_csv(
        VALIDATION / "cerra_land_official_monthly_normals_1991_2020.csv"
    ).rename(
        columns={
            "precipitation_mm": "cerra_land_precip_mm",
            "rainy_days_ge_1mm": "cerra_land_rainy_days",
            "years": "cerra_land_years",
        }
    )
    sarah = pd.read_csv(VALIDATION / "sarah3_sunshine_normals_points.csv")
    sample = chelsa.merge(cerra, on=["region", "point", "month"], how="left")
    sample = sample.merge(
        sarah[["region", "point", "month", "sunshine_hours_sarah3"]],
        on=["region", "point", "month"],
        how="left",
    )
    sample = sample.merge(
        chelsa_full[["region", "point", "month", "pr"]].rename(
            columns={"pr": "chelsa_precip_1991_2020_mm"}
        ),
        on=["region", "point", "month"],
        how="left",
    )
    sample = sample.merge(
        cerra_land[
            [
                "region",
                "point",
                "month",
                "cerra_land_precip_mm",
                "cerra_land_rainy_days",
                "cerra_land_years",
                "minimum_observed_days",
            ]
        ],
        on=["region", "point", "month"],
        how="left",
    )
    sample["delta_tmean_chelsa_minus_cerra_c"] = sample["tas"] - sample["cerra_tmean_c"]
    sample["delta_tmax_chelsa_minus_cerra_c"] = sample["tasmax"] - sample["cerra_tmax_c"]
    sample["delta_tmin_chelsa_minus_cerra_c"] = sample["tasmin"] - sample["cerra_tmin_c"]
    sample["precip_ratio_chelsa_to_cerra"] = sample["pr"] / sample[
        "cerra_precip_mm"
    ].replace(0, np.nan)
    sample["precip_ratio_chelsa_to_cerra_land_official"] = sample[
        "chelsa_precip_1991_2020_mm"
    ] / sample["cerra_land_precip_mm"].replace(0, np.nan)
    sample["sunshine_delta_sarah_1991_2020_minus_cerra_1991_2005_h"] = (
        sample["sunshine_hours_sarah3"] - sample["cerra_sunshine_hours"]
    )
    sample["comparison_period_temperature"] = "1991-2005"
    sample["comparison_period_precipitation_official"] = "1991-2020"
    sample["sarah_normal_period"] = "1991-2020"
    sample = sample.sort_values(["region", "point", "month"])

    work_output = VALIDATION / "comparison_phase1_jan_jul.csv"
    user_output = OUTPUTS / "resultats-zones-tests-etape-1.csv"
    sample.to_csv(work_output, index=False)
    sample.to_csv(user_output, index=False)

    metrics = {
        "points": int(sample["point"].nunique()),
        "rows": int(len(sample)),
        "temperature_mean_mae_c": float(sample["delta_tmean_chelsa_minus_cerra_c"].abs().mean()),
        "temperature_mean_median_delta_c": float(sample["delta_tmean_chelsa_minus_cerra_c"].median()),
        "temperature_mean_p90_abs_delta_c": float(sample["delta_tmean_chelsa_minus_cerra_c"].abs().quantile(0.9)),
        "temperature_max_mae_c": float(sample["delta_tmax_chelsa_minus_cerra_c"].abs().mean()),
        "temperature_min_mae_c": float(sample["delta_tmin_chelsa_minus_cerra_c"].abs().mean()),
        "precip_ratio_median": float(sample["precip_ratio_chelsa_to_cerra"].median()),
        "precip_ratio_p10": float(sample["precip_ratio_chelsa_to_cerra"].quantile(0.1)),
        "precip_ratio_p90": float(sample["precip_ratio_chelsa_to_cerra"].quantile(0.9)),
        "official_precip_ratio_median": float(
            sample["precip_ratio_chelsa_to_cerra_land_official"].median()
        ),
        "official_precip_ratio_p10": float(
            sample["precip_ratio_chelsa_to_cerra_land_official"].quantile(0.1)
        ),
        "official_precip_ratio_p90": float(
            sample["precip_ratio_chelsa_to_cerra_land_official"].quantile(0.9)
        ),
        "official_cerra_land_missing_points": int(
            sample["cerra_land_precip_mm"].isna().sum()
        ),
        "sarah_points_available": int(
            sample.dropna(subset=["sunshine_hours_sarah3"])["point"].nunique()
        ),
    }
    (VALIDATION / "phase1_metrics.json").write_text(json.dumps(metrics, indent=2))
    print(json.dumps(metrics, indent=2))
    display_columns = [
        "region",
        "point",
        "month",
        "tas",
        "cerra_tmean_c",
        "delta_tmean_chelsa_minus_cerra_c",
        "pr",
        "cerra_land_precip_mm",
        "precip_ratio_chelsa_to_cerra_land_official",
        "sunshine_hours_sarah3",
        "cerra_sunshine_hours",
    ]
    print(sample[display_columns].to_string(index=False, float_format=lambda x: f"{x:.2f}"))


if __name__ == "__main__":
    main()
