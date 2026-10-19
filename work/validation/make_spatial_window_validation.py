#!/usr/bin/env python3
"""Validate complete CHELSA map windows against Copernicus DEM relief.

The output is deliberately a data-quality figure rather than application UI.
It checks whether the 1991-2020 temperature normals preserve meaningful
valley/summit and coast/island structure at map scale.
"""

from __future__ import annotations

import math
from pathlib import Path

import matplotlib.pyplot as plt
from matplotlib.colors import LightSource, Normalize
import numpy as np
import pandas as pd
import rasterio
from rasterio.enums import Resampling
from rasterio.windows import from_bounds


ROOT = Path(__file__).resolve().parents[2]
CACHE = ROOT / "work" / "validation" / "cache" / "spatial_windows"
CACHE.mkdir(parents=True, exist_ok=True)

REGIONS = {
    "Alpes": {
        "bounds": (5.75, 45.45, 7.30, 46.35),
        "points": [
            ("Annecy", 6.129, 45.899),
            ("Chamonix", 6.870, 45.924),
            ("Mont-Blanc", 6.865, 45.833),
        ],
    },
    "Pyrénées orientales": {
        "bounds": (1.55, 42.15, 3.25, 42.95),
        "points": [
            ("Perpignan", 2.894, 42.688),
            ("Font-Romeu", 2.040, 42.505),
        ],
    },
    "Atlas marocain": {
        "bounds": (-8.55, 30.85, -7.10, 32.00),
        "points": [
            ("Marrakech", -8.009, 31.630),
            ("Toubkal", -7.915, 31.061),
        ],
    },
    "Tenerife": {
        "bounds": (-16.95, 27.90, -16.05, 28.65),
        "points": [
            ("La Laguna", -16.316, 28.488),
            ("Costa Adeje", -16.735, 28.087),
            ("Teide", -16.643, 28.272),
        ],
    },
    "Tromsø": {
        "bounds": (18.30, 69.40, 19.50, 69.90),
        "points": [
            ("Tromsø", 18.956, 69.649),
        ],
    },
}
MONTHS = {1: "janvier", 7: "juillet"}
YEARS = range(1991, 2021)
ENV = {
    "GDAL_DISABLE_READDIR_ON_OPEN": "EMPTY_DIR",
    "CPL_VSIL_CURL_ALLOWED_EXTENSIONS": ".tif",
    "GDAL_HTTP_MAX_RETRY": "5",
    "GDAL_HTTP_RETRY_DELAY": "2",
}


def chelsa_url(year: int, month: int) -> str:
    return (
        "https://os.unil.cloud.switch.ch/chelsa02/chelsa/global/monthly/"
        f"tas/{year}/CHELSA_tas_{month:02d}_{year}_V.2.1.tif"
    )


def coordinate_token(value: int, positive: str, negative: str, width: int) -> str:
    hemisphere = positive if value >= 0 else negative
    return f"{hemisphere}{abs(value):0{width}d}_00"


def dem_tile_name(south: int, west: int) -> str:
    lat_token = coordinate_token(south, "N", "S", 2)
    lon_token = coordinate_token(west, "E", "W", 3)
    return f"Copernicus_DSM_COG_10_{lat_token}_{lon_token}_DEM"


def dem_url(south: int, west: int) -> str:
    tile = dem_tile_name(south, west)
    return f"https://copernicus-dem-30m.s3.eu-central-1.amazonaws.com/{tile}/{tile}.tif"


def wbm_url(south: int, west: int) -> str:
    tile = dem_tile_name(south, west)
    wbm = tile.replace("_DEM", "_WBM")
    return (
        "https://copernicus-dem-30m.s3.eu-central-1.amazonaws.com/"
        f"{tile}/AUXFILES/{wbm}.tif"
    )


def grid_shape(bounds: tuple[float, float, float, float], width: int = 720) -> tuple[int, int]:
    west, south, east, north = bounds
    mid_latitude = (south + north) / 2
    height = round(width * (north - south) / ((east - west) * math.cos(math.radians(mid_latitude))))
    return max(height, 300), width


def read_chelsa_normal(region: str, bounds, month: int, shape) -> np.ndarray:
    cache_path = CACHE / f"{region.lower().replace(' ', '_').replace('é', 'e')}_tas_{month:02d}.npy"
    if cache_path.exists():
        return np.load(cache_path)
    height, width = shape
    values = []
    for number, year in enumerate(YEARS, start=1):
        with rasterio.Env(**ENV), rasterio.open(chelsa_url(year, month)) as source:
            window = from_bounds(*bounds, transform=source.transform)
            data = source.read(
                1,
                window=window,
                out_shape=(height, width),
                masked=True,
                resampling=Resampling.bilinear,
            ).astype("float64")
            data = data * source.scales[0] + source.offsets[0] - 273.15
            values.append(data.filled(np.nan))
        if number % 10 == 0:
            print(f"CHELSA {region} {MONTHS[month]} : {number}/30", flush=True)
    normal = np.nanmean(np.stack(values), axis=0)
    np.save(cache_path, normal)
    return normal


def read_dem(region: str, bounds, shape) -> np.ndarray:
    cache_path = CACHE / f"{region.lower().replace(' ', '_').replace('é', 'e')}_dem.npy"
    if cache_path.exists():
        return np.load(cache_path)
    west, south, east, north = bounds
    height, width = shape
    output = np.full((height, width), np.nan, dtype="float32")

    def x_index(longitude: float) -> int:
        return round((longitude - west) / (east - west) * width)

    def y_index(latitude: float) -> int:
        return round((north - latitude) / (north - south) * height)

    for tile_south in range(math.floor(south), math.ceil(north)):
        for tile_west in range(math.floor(west), math.ceil(east)):
            left, right = max(west, tile_west), min(east, tile_west + 1)
            bottom, top = max(south, tile_south), min(north, tile_south + 1)
            x0, x1 = max(0, x_index(left)), min(width, x_index(right))
            y0, y1 = max(0, y_index(top)), min(height, y_index(bottom))
            if x1 <= x0 or y1 <= y0:
                continue
            with rasterio.Env(**ENV), rasterio.open(dem_url(tile_south, tile_west)) as source:
                window = from_bounds(left, bottom, right, top, transform=source.transform)
                data = source.read(
                    1,
                    window=window,
                    out_shape=(y1 - y0, x1 - x0),
                    masked=True,
                    resampling=Resampling.bilinear,
                )
                output[y0:y1, x0:x1] = data.filled(np.nan)
            print(f"DEM {region}: tuile {tile_south:+03d}/{tile_west:+04d}", flush=True)
    np.save(cache_path, output)
    return output


def read_water_mask(region: str, bounds, shape) -> np.ndarray:
    cache_path = CACHE / f"{region.lower().replace(' ', '_').replace('é', 'e')}_wbm.npy"
    if cache_path.exists():
        return np.load(cache_path)
    west, south, east, north = bounds
    height, width = shape
    output = np.full((height, width), 255, dtype="uint8")

    def x_index(longitude: float) -> int:
        return round((longitude - west) / (east - west) * width)

    def y_index(latitude: float) -> int:
        return round((north - latitude) / (north - south) * height)

    for tile_south in range(math.floor(south), math.ceil(north)):
        for tile_west in range(math.floor(west), math.ceil(east)):
            left, right = max(west, tile_west), min(east, tile_west + 1)
            bottom, top = max(south, tile_south), min(north, tile_south + 1)
            x0, x1 = max(0, x_index(left)), min(width, x_index(right))
            y0, y1 = max(0, y_index(top)), min(height, y_index(bottom))
            if x1 <= x0 or y1 <= y0:
                continue
            with rasterio.Env(**ENV), rasterio.open(wbm_url(tile_south, tile_west)) as source:
                window = from_bounds(left, bottom, right, top, transform=source.transform)
                data = source.read(
                    1,
                    window=window,
                    out_shape=(y1 - y0, x1 - x0),
                    masked=True,
                    resampling=Resampling.nearest,
                )
                output[y0:y1, x0:x1] = data.filled(255)
            print(f"WBM {region}: tuile {tile_south:+03d}/{tile_west:+04d}", flush=True)
    np.save(cache_path, output)
    return output


def diagnostics(
    region: str,
    month: int,
    temperature: np.ndarray,
    elevation: np.ndarray,
    water_mask: np.ndarray,
) -> dict:
    # WBM values: 0 land, 1 ocean, 2 lake, 3 river.
    valid = np.isfinite(temperature) & np.isfinite(elevation) & (water_mask == 0)
    temp_values = temperature[valid]
    elevation_values = elevation[valid]
    slope, intercept = np.polyfit(elevation_values / 1000.0, temp_values, 1)
    correlation = np.corrcoef(elevation_values, temp_values)[0, 1]
    return {
        "region": region,
        "month": month,
        "temperature_min_c": float(np.nanpercentile(temp_values, 1)),
        "temperature_mean_c": float(np.nanmean(temp_values)),
        "temperature_max_c": float(np.nanpercentile(temp_values, 99)),
        "elevation_min_m": float(np.nanpercentile(elevation_values, 1)),
        "elevation_max_m": float(np.nanpercentile(elevation_values, 99)),
        "temperature_elevation_correlation": float(correlation),
        "lapse_rate_c_per_1000m": float(slope),
        "valid_land_pixels": int(valid.sum()),
        "land_fraction": float(valid.mean()),
    }


def main() -> None:
    results = {}
    rows = []
    for region, config in REGIONS.items():
        shape = grid_shape(config["bounds"])
        elevation = read_dem(region, config["bounds"], shape)
        water_mask = read_water_mask(region, config["bounds"], shape)
        for month in MONTHS:
            temperature = read_chelsa_normal(region, config["bounds"], month, shape)
            results[(region, month)] = (temperature, elevation, water_mask)
            rows.append(diagnostics(region, month, temperature, elevation, water_mask))

    metrics = pd.DataFrame(rows)
    metrics_path = ROOT / "outputs" / "controle-fenetres-cartographiques.csv"
    metrics.to_csv(metrics_path, index=False)

    figure, axes = plt.subplots(len(REGIONS), len(MONTHS), figsize=(14, 22))
    cmap = plt.get_cmap("turbo")
    normalizer = Normalize(vmin=-15, vmax=30)
    image = None
    for row_index, (region, config) in enumerate(REGIONS.items()):
        west, south, east, north = config["bounds"]
        for column_index, month in enumerate(MONTHS):
            ax = axes[row_index, column_index]
            temperature, elevation, water_mask = results[(region, month)]
            land = np.isfinite(temperature) & np.isfinite(elevation) & (water_mask == 0)
            latitude = (south + north) / 2
            dx = (east - west) / temperature.shape[1] * 111_320 * math.cos(math.radians(latitude))
            dy = (north - south) / temperature.shape[0] * 111_320
            safe_elevation = np.where(np.isfinite(elevation), elevation, 0)
            shade = LightSource(azdeg=315, altdeg=40).hillshade(safe_elevation, dx=dx, dy=dy, vert_exag=1.4)
            extent = (west, east, south, north)
            ax.set_facecolor("#d9eef5")
            ax.imshow(np.ma.masked_where(~land, shade), extent=extent, cmap="gray", origin="upper", vmin=0, vmax=1)
            image = ax.imshow(
                np.ma.masked_where(~land, temperature),
                extent=extent,
                cmap=cmap,
                norm=normalizer,
                origin="upper",
                alpha=0.73,
                interpolation="bilinear",
            )
            for name, longitude, latitude_point in config["points"]:
                ax.plot(longitude, latitude_point, "o", markersize=4.5, color="white", markeredgecolor="#202020", markeredgewidth=0.8)
                ax.annotate(
                    name,
                    (longitude, latitude_point),
                    xytext=(5, 4),
                    textcoords="offset points",
                    fontsize=8.5,
                    color="#111",
                    path_effects=[],
                )
            metric = metrics[(metrics["region"] == region) & (metrics["month"] == month)].iloc[0]
            ax.set_title(
                f"{region} — {MONTHS[month]}\n"
                f"gradient altitudinal {metric['lapse_rate_c_per_1000m']:.1f} °C/1 000 m",
                fontsize=10.5,
            )
            ax.set_xlim(west, east)
            ax.set_ylim(south, north)
            ax.set_xlabel("longitude")
            ax.set_ylabel("latitude")
            ax.grid(color="white", alpha=0.22, linewidth=0.6)
            ax.set_aspect(1 / math.cos(math.radians((south + north) / 2)))

    figure.suptitle(
        "Fenêtres tests — température CHELSA 1991–2020 et relief Copernicus DEM GLO-30",
        fontsize=16,
        fontweight="bold",
    )
    colorbar_axis = figure.add_axes([0.25, 0.062, 0.50, 0.012])
    colorbar = figure.colorbar(image, cax=colorbar_axis, orientation="horizontal")
    colorbar.set_label("Température moyenne mensuelle (°C)")
    figure.text(
        0.5,
        0.022,
        "Couleur : température à ≈1 km · Ombrage et masque d’eau WBM : Copernicus DEM à ≈30 m",
        ha="center",
        fontsize=10,
    )
    figure.subplots_adjust(left=0.07, right=0.98, top=0.945, bottom=0.105, hspace=0.48, wspace=0.14)
    figure_path = ROOT / "outputs" / "fenetres-cartographiques-hybrides.png"
    figure.savefig(figure_path, dpi=180, bbox_inches="tight")
    print(metrics.to_string(index=False))
    print(f"Écrit : {metrics_path}")
    print(f"Écrit : {figure_path}")


if __name__ == "__main__":
    main()
