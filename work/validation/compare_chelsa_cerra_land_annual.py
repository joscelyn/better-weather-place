#!/usr/bin/env python3
"""Compare CHELSA and official CERRA-Land precipitation for all 12 months.

The Canary Islands are intentionally excluded from this phase. Essaouira is
also excluded because the test coordinate was shown by the Copernicus WBM to
fall in the ocean rather than on land.
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import numpy as np
import pandas as pd
import rasterio


ROOT = Path(__file__).resolve().parents[2]
VALIDATION = ROOT / "work" / "validation"
OUTPUTS = ROOT / "outputs"
YEARS = range(1991, 2021)
MONTHS = range(1, 13)


def chelsa_url(year: int, month: int) -> str:
    return (
        "https://os.unil.cloud.switch.ch/chelsa02/chelsa/global/monthly/"
        f"pr/{year}/CHELSA_pr_{month:02d}_{year}_V.2.1.tif"
    )


def load_points() -> pd.DataFrame:
    source = pd.read_csv(VALIDATION / "cerra_land_official_point_metadata.csv")
    source = source[(source["region"] != "canaries") & (source["point"] != "Essaouira")]
    return source[["region", "point", "requested_latitude", "requested_longitude"]].copy()


def read_month(points: pd.DataFrame, year: int, month: int) -> list[dict]:
    url = chelsa_url(year, month)
    options = {
        "GDAL_DISABLE_READDIR_ON_OPEN": "EMPTY_DIR",
        "CPL_VSIL_CURL_ALLOWED_EXTENSIONS": ".tif",
        "GDAL_HTTP_MAX_RETRY": "5",
        "GDAL_HTTP_RETRY_DELAY": "1",
    }
    coordinates = list(zip(points["requested_longitude"], points["requested_latitude"]))
    with rasterio.Env(**options), rasterio.open(url) as source:
        raw = [sample[0] for sample in source.sample(coordinates)]
        scale = source.scales[0]
        offset = source.offsets[0]
        nodata = source.nodata

    rows = []
    for point, value in zip(points.itertuples(index=False), raw):
        precipitation = np.nan if value == nodata else float(value) * scale + offset
        rows.append(
            {
                "region": point.region,
                "point": point.point,
                "latitude": point.requested_latitude,
                "longitude": point.requested_longitude,
                "year": year,
                "month": month,
                "chelsa_precipitation_mm": precipitation,
            }
        )
    return rows


def extract_chelsa(points: pd.DataFrame) -> pd.DataFrame:
    output = VALIDATION / "chelsa_precip_points_1991_2020_no_canaries.csv"
    if output.exists():
        return pd.read_csv(output)

    jobs = [(year, month) for year in YEARS for month in MONTHS]
    rows: list[dict] = []
    with ThreadPoolExecutor(max_workers=6) as pool:
        futures = {pool.submit(read_month, points, *job): job for job in jobs}
        for completed, future in enumerate(as_completed(futures), start=1):
            job = futures[future]
            try:
                rows.extend(future.result())
            except Exception as error:
                raise RuntimeError(f"Échec CHELSA pour {job}: {error}") from error
            if completed % 30 == 0 or completed == len(jobs):
                print(f"CHELSA précipitations : {completed}/{len(jobs)} mois", flush=True)

    frame = pd.DataFrame(rows).sort_values(["point", "year", "month"])
    frame.to_csv(output, index=False)
    return frame


def main() -> None:
    points = load_points()
    chelsa = extract_chelsa(points)
    chelsa_normals = chelsa.groupby(["region", "point", "month"], as_index=False).agg(
        chelsa_precipitation_mm=("chelsa_precipitation_mm", "mean"),
        chelsa_years=("year", "nunique"),
    )
    cerra = pd.read_csv(VALIDATION / "cerra_land_official_monthly_normals_1991_2020.csv")
    cerra = cerra[(cerra["region"] != "canaries") & (cerra["point"] != "Essaouira")]
    comparison = chelsa_normals.merge(
        cerra[["region", "point", "month", "precipitation_mm", "rainy_days_ge_1mm", "years"]],
        on=["region", "point", "month"],
        how="inner",
    ).rename(
        columns={
            "precipitation_mm": "cerra_land_precipitation_mm",
            "rainy_days_ge_1mm": "cerra_land_rainy_days_ge_1mm",
            "years": "cerra_land_years",
        }
    )
    comparison["difference_chelsa_minus_cerra_land_mm"] = (
        comparison["chelsa_precipitation_mm"]
        - comparison["cerra_land_precipitation_mm"]
    )
    comparison["ratio_chelsa_to_cerra_land"] = (
        comparison["chelsa_precipitation_mm"]
        / comparison["cerra_land_precipitation_mm"].replace(0, np.nan)
    )
    comparison["wet_reference_ge_10mm"] = comparison["cerra_land_precipitation_mm"] >= 10

    comparison_path = OUTPUTS / "comparaison-chelsa-cerra-land-12-mois.csv"
    comparison.to_csv(comparison_path, index=False)

    rows = []
    for month, sample in comparison.groupby("month"):
        wet = sample[sample["wet_reference_ge_10mm"]]
        dry = sample[~sample["wet_reference_ge_10mm"]]
        rows.append(
            {
                "month": month,
                "points": len(sample),
                "wet_points_ge_10mm": len(wet),
                "median_ratio_wet": wet["ratio_chelsa_to_cerra_land"].median(),
                "p10_ratio_wet": wet["ratio_chelsa_to_cerra_land"].quantile(0.1),
                "p90_ratio_wet": wet["ratio_chelsa_to_cerra_land"].quantile(0.9),
                "mae_wet_mm": wet["difference_chelsa_minus_cerra_land_mm"].abs().mean(),
                "dry_points_lt_10mm": len(dry),
                "mae_dry_mm": dry["difference_chelsa_minus_cerra_land_mm"].abs().mean(),
            }
        )
    summary = pd.DataFrame(rows)
    summary_path = OUTPUTS / "synthese-chelsa-cerra-land-12-mois.csv"
    summary.to_csv(summary_path, index=False)

    wet = comparison[comparison["wet_reference_ge_10mm"]]
    dry = comparison[~comparison["wet_reference_ge_10mm"]]
    print(f"Points terrestres hors Canaries : {comparison['point'].nunique()}")
    print(f"Couples point–mois : {len(comparison)}")
    print(
        "Référence >=10 mm — rapport médian/p10/p90 : "
        f"{wet['ratio_chelsa_to_cerra_land'].median():.2f} / "
        f"{wet['ratio_chelsa_to_cerra_land'].quantile(0.1):.2f} / "
        f"{wet['ratio_chelsa_to_cerra_land'].quantile(0.9):.2f}"
    )
    print(
        f"Référence >=10 mm — MAE : "
        f"{wet['difference_chelsa_minus_cerra_land_mm'].abs().mean():.1f} mm/mois"
    )
    print(
        f"Référence <10 mm — {len(dry)} couples, MAE : "
        f"{dry['difference_chelsa_minus_cerra_land_mm'].abs().mean():.1f} mm/mois"
    )
    print(f"Écrit : {comparison_path}")
    print(f"Écrit : {summary_path}")


if __name__ == "__main__":
    main()
