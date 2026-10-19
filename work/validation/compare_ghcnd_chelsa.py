#!/usr/bin/env python3
"""Compare monthly CHELSA 1991-2020 normals with independent GHCN observations."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[2]
WORK = ROOT / "work" / "validation"


def main() -> None:
    raw = pd.read_csv(WORK / "chelsa_at_ghcnd_1991_2020.csv")
    chelsa = (
        raw.groupby(["station_id", "station_name", "month", "variable"], as_index=False)["value"]
        .mean()
        .pivot(index=["station_id", "station_name", "month"], columns="variable", values="value")
        .reset_index()
        .rename_axis(columns=None)
    )
    station_normals = pd.read_csv(WORK / "ghcnd_monthly_normals_1991_2020.csv")
    observed = station_normals.drop_duplicates(["station_id", "month"])[
        [
            "station_id", "month", "tmean_c", "tmax_c", "tmin_c",
            "precipitation_mm", "rain_days_ge_1mm",
        ]
    ]
    station_comparison = chelsa.merge(observed, on=["station_id", "month"], how="left")
    station_comparison["delta_tmean_c"] = station_comparison["tas"] - station_comparison["tmean_c"]
    station_comparison["delta_tmax_c"] = station_comparison["tasmax"] - station_comparison["tmax_c"]
    station_comparison["delta_tmin_c"] = station_comparison["tasmin"] - station_comparison["tmin_c"]
    station_comparison["precipitation_ratio"] = (
        station_comparison["pr"] / station_comparison["precipitation_mm"]
    )

    metadata = pd.read_csv(WORK / "ghcnd_station_metadata.csv")
    comparison = metadata.merge(station_comparison, on=["station_id", "station_name"], how="left")
    output = WORK / "ghcnd_chelsa_comparison_1991_2020.csv"
    comparison.to_csv(output, index=False)

    valid = comparison[comparison["comparability"].isin(["bonne", "indicative"])]
    temp = valid.dropna(subset=["delta_tmean_c"])
    precip = valid.dropna(subset=["precipitation_mm", "pr"]).copy()
    wet_precip = precip[precip["precipitation_mm"] >= 10.0].copy()
    wet_precip = wet_precip[np.isfinite(wet_precip["precipitation_ratio"])]
    dry_precip = precip[precip["precipitation_mm"] < 10.0].copy()
    metrics = {
        "comparison_period": "1991-2020",
        "months": list(range(1, 13)),
        "comparable_points": int(valid["point"].nunique()),
        "good_points": int(valid.loc[valid["comparability"] == "bonne", "point"].nunique()),
        "indicative_points": int(valid.loc[valid["comparability"] == "indicative", "point"].nunique()),
        "non_comparable_points": int(
            comparison.loc[comparison["comparability"] == "non_comparable", "point"].nunique()
        ),
        "temperature_pairs": int(len(temp)),
        "temperature_mean_bias_chelsa_minus_station_c": float(temp["delta_tmean_c"].mean()),
        "temperature_mae_c": float(temp["delta_tmean_c"].abs().mean()),
        "temperature_p90_absolute_error_c": float(temp["delta_tmean_c"].abs().quantile(0.90)),
        "precipitation_pairs": int(len(precip)),
        "precipitation_wet_pairs_station_ge_10mm": int(len(wet_precip)),
        "precipitation_wet_ratio_median_chelsa_to_station": float(wet_precip["precipitation_ratio"].median()),
        "precipitation_wet_ratio_p10": float(wet_precip["precipitation_ratio"].quantile(0.10)),
        "precipitation_wet_ratio_p90": float(wet_precip["precipitation_ratio"].quantile(0.90)),
        "precipitation_wet_mae_mm": float((wet_precip["pr"] - wet_precip["precipitation_mm"]).abs().mean()),
        "precipitation_dry_pairs_station_lt_10mm": int(len(dry_precip)),
        "precipitation_dry_mae_mm": float((dry_precip["pr"] - dry_precip["precipitation_mm"]).abs().mean()),
    }
    for month in range(1, 13):
        month_temp = temp[temp["month"] == month]
        month_precip = wet_precip[wet_precip["month"] == month]
        metrics[f"month_{month:02d}"] = {
            "temperature_pairs": int(len(month_temp)),
            "temperature_bias_c": float(month_temp["delta_tmean_c"].mean()),
            "temperature_mae_c": float(month_temp["delta_tmean_c"].abs().mean()),
            "precipitation_wet_pairs": int(len(month_precip)),
            "precipitation_wet_ratio_median": float(month_precip["precipitation_ratio"].median()),
        }
    metrics_path = WORK / "ghcnd_validation_metrics.json"
    metrics_path.write_text(json.dumps(metrics, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps(metrics, ensure_ascii=False, indent=2))
    print(f"Écrit : {output}")
    print(f"Écrit : {metrics_path}")


if __name__ == "__main__":
    main()
