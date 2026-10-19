#!/usr/bin/env python3
"""Benchmark a separate higher-resolution relief layer for three mountain regions."""

from __future__ import annotations

import json
import math
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import mercantile
import numpy as np
import pandas as pd
import rasterio
from matplotlib import pyplot as plt
from matplotlib.colors import LightSource
from PIL import Image
from pmtiles.convert import disk_to_pmtiles
from rasterio.enums import Resampling
from rasterio.errors import RasterioIOError
from rasterio.transform import from_bounds
from rasterio.warp import reproject
from rasterio.windows import from_bounds as window_from_bounds
from scipy.ndimage import distance_transform_edt

from make_spatial_window_validation import ENV, dem_url, wbm_url


ROOT = Path(__file__).resolve().parents[2]
CACHE = ROOT / "work/validation/cache/pilot_relief_90m"
OUTPUT = ROOT / "outputs/pilot-etape-2b"
CACHE.mkdir(parents=True, exist_ok=True)
OUTPUT.mkdir(parents=True, exist_ok=True)

PIXELS_PER_DEGREE = 1200
ZOOMS = range(8, 11)
REGIONS = {
    "alpes": {"label": "Alpes", "bounds": (5.0, 44.0, 8.0, 47.0)},
    "pyrenees": {"label": "Pyrénées", "bounds": (-2.0, 41.0, 4.0, 44.0)},
    "atlas": {"label": "Haut Atlas", "bounds": (-10.0, 29.0, -5.0, 33.0)},
}


def read_source_tile(south: int, west: int) -> tuple[np.ndarray, np.ndarray]:
    cache = CACHE / "source_tiles" / f"{south:+03d}_{west:+04d}.npz"
    if cache.exists():
        data = np.load(cache)
        return data["dem"], data["water"]

    shape = (PIXELS_PER_DEGREE, PIXELS_PER_DEGREE)
    bounds = (west, south, west + 1, south + 1)
    try:
        with rasterio.Env(**ENV), rasterio.open(dem_url(south, west)) as source:
            window = window_from_bounds(*bounds, transform=source.transform)
            dem = source.read(
                1,
                window=window,
                out_shape=shape,
                masked=True,
                resampling=Resampling.bilinear,
            ).filled(np.nan).astype("float32")
        with rasterio.Env(**ENV), rasterio.open(wbm_url(south, west)) as source:
            window = window_from_bounds(*bounds, transform=source.transform)
            water = source.read(
                1,
                window=window,
                out_shape=shape,
                masked=True,
                resampling=Resampling.nearest,
            ).filled(255).astype("uint8")
    except RasterioIOError as exc:
        if "404" not in str(exc):
            raise
        dem = np.zeros(shape, dtype="float32")
        water = np.ones(shape, dtype="uint8")
    cache.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(cache, dem=dem, water=water)
    return dem, water


def build_region_mosaic(name: str, bounds: tuple[float, float, float, float]) -> tuple[np.ndarray, np.ndarray]:
    cache = CACHE / f"{name}_mosaic.npz"
    if cache.exists():
        data = np.load(cache)
        return data["dem"], data["water"]

    west, south, east, north = [int(value) for value in bounds]
    width = (east - west) * PIXELS_PER_DEGREE
    height = (north - south) * PIXELS_PER_DEGREE
    dem = np.full((height, width), np.nan, dtype="float32")
    water = np.full((height, width), 255, dtype="uint8")
    jobs = [(lat, lon) for lat in range(south, north) for lon in range(west, east)]
    with ThreadPoolExecutor(max_workers=6) as pool:
        futures = {pool.submit(read_source_tile, *job): job for job in jobs}
        for index, future in enumerate(as_completed(futures), start=1):
            tile_south, tile_west = futures[future]
            tile_dem, tile_water = future.result()
            x0 = (tile_west - west) * PIXELS_PER_DEGREE
            y0 = (north - tile_south - 1) * PIXELS_PER_DEGREE
            dem[y0 : y0 + PIXELS_PER_DEGREE, x0 : x0 + PIXELS_PER_DEGREE] = tile_dem
            water[y0 : y0 + PIXELS_PER_DEGREE, x0 : x0 + PIXELS_PER_DEGREE] = tile_water
            print(f"{name}: {index}/{len(jobs)} tuiles source", flush=True)
    np.savez_compressed(cache, dem=dem, water=water)
    return dem, water


def make_hillshade(
    dem: np.ndarray,
    water: np.ndarray,
    bounds: tuple[float, float, float, float],
) -> np.ndarray:
    land = (water == 0) & np.isfinite(dem)
    nearest = distance_transform_edt(~land, return_distances=False, return_indices=True)
    filled = dem[tuple(nearest)]
    latitude = (bounds[1] + bounds[3]) / 2
    dx = (bounds[2] - bounds[0]) / dem.shape[1] * 111_320 * math.cos(math.radians(latitude))
    dy = (bounds[3] - bounds[1]) / dem.shape[0] * 111_320
    return LightSource(azdeg=315, altdeg=40).hillshade(
        filled, dx=dx, dy=dy, vert_exag=1.25
    ).astype("float32")


def downsample_1km(array: np.ndarray, mode: str) -> np.ndarray:
    height = array.shape[0] // 10 * 10
    width = array.shape[1] // 10 * 10
    blocks = array[:height, :width].reshape(height // 10, 10, width // 10, 10)
    if mode == "mean":
        return np.nanmean(blocks, axis=(1, 3)).astype("float32")
    return blocks[:, 5, :, 5].astype("uint8")


def reproject_tile(
    source: np.ndarray,
    source_transform,
    tile: mercantile.Tile,
    resampling: Resampling,
    nodata: float,
    dtype: str,
) -> np.ndarray:
    bounds = mercantile.xy_bounds(tile)
    destination = np.full((256, 256), nodata, dtype=dtype)
    reproject(
        source=source,
        destination=destination,
        src_transform=source_transform,
        src_crs="EPSG:4326",
        src_nodata=nodata,
        dst_transform=from_bounds(bounds.left, bounds.bottom, bounds.right, bounds.top, 256, 256),
        dst_crs="EPSG:3857",
        dst_nodata=nodata,
        resampling=resampling,
    )
    return destination


def save_relief_tile(path: Path, shade: np.ndarray, land: np.ndarray) -> int:
    gray = np.clip(shade * 255, 0, 255).astype("uint8")
    rgba = np.zeros((256, 256, 4), dtype="uint8")
    rgba[..., :3] = gray[..., None]
    rgba[..., 3] = np.where(land, 88, 0).astype("uint8")
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.fromarray(rgba, mode="RGBA").save(path, "WEBP", quality=85, method=6)
    return path.stat().st_size


def build_pmtiles(region_data: dict[str, dict]) -> dict:
    sizes = []
    tile_keys = set()
    with tempfile.TemporaryDirectory(prefix="relief-90m-", dir=CACHE) as temp:
        directory = Path(temp)
        for name, data in region_data.items():
            bounds = REGIONS[name]["bounds"]
            transform = from_bounds(*bounds, data["shade"].shape[1], data["shade"].shape[0])
            for tile in mercantile.tiles(*bounds, zooms=ZOOMS, truncate=True):
                key = (tile.z, tile.x, tile.y)
                if key in tile_keys:
                    continue
                tile_keys.add(key)
                tile_water = reproject_tile(
                    data["water"], transform, tile, Resampling.nearest, 255, "uint8"
                )
                land = tile_water == 0
                if not land.any():
                    continue
                tile_shade = reproject_tile(
                    data["shade"], transform, tile, Resampling.bilinear, -9999, "float32"
                )
                path = directory / str(tile.z) / str(tile.x) / f"{tile.y}.webp"
                sizes.append(save_relief_tile(path, tile_shade, land))

        all_bounds = (-10.0, 29.0, 8.0, 47.0)
        metadata = {
            "name": "relief-separate-90m-mountain-pilot",
            "description": "Higher-resolution relief pilot for Better Weather Place",
            "format": "webp",
            "bounds": ",".join(str(value) for value in all_bounds),
            "center": "-1,38,8",
            "minzoom": min(ZOOMS),
            "maxzoom": max(ZOOMS),
            "attribution": "Copernicus DEM GLO-30",
            "type": "overlay",
        }
        (directory / "metadata.json").write_text(json.dumps(metadata, ensure_ascii=False))
        output = OUTPUT / "relief-separate-90m-montagnes.pmtiles"
        disk_to_pmtiles(str(directory), str(output), "auto", tile_format="webp")

    return {
        "asset": output.name,
        "tile_count": len(sizes),
        "unpacked_tile_bytes": sum(sizes),
        "median_tile_bytes": int(np.median(sizes)),
        "p90_tile_bytes": int(np.percentile(sizes, 90)),
        "pmtiles_bytes": output.stat().st_size,
    }


def make_comparison(region_data: dict[str, dict]) -> None:
    figure, axes = plt.subplots(3, 2, figsize=(12, 14), constrained_layout=True)
    for row, (name, data) in enumerate(region_data.items()):
        bounds = REGIONS[name]["bounds"]
        dem_low = downsample_1km(data["dem"], "mean")
        water_low = downsample_1km(data["water"], "nearest")
        shade_low = make_hillshade(dem_low, water_low, bounds)
        displays = (
            ("≈ 1 km, zooms bas", shade_low, water_low),
            ("≈ 90 m, zooms 8–10", data["shade"], data["water"]),
        )
        for column, (resolution, shade, water) in enumerate(displays):
            masked = np.ma.masked_where(water != 0, shade)
            axes[row, column].imshow(
                masked,
                cmap="gray",
                vmin=0,
                vmax=1,
                extent=(bounds[0], bounds[2], bounds[1], bounds[3]),
                origin="upper",
            )
            axes[row, column].set_facecolor("#dceef4")
            axes[row, column].set_title(f"{REGIONS[name]['label']} — {resolution}")
            axes[row, column].set_xlabel("longitude")
            axes[row, column].set_ylabel("latitude")
    figure.suptitle("Résolution du relief séparé", fontsize=16)
    figure.savefig(ROOT / "outputs/pilot-relief-haute-resolution.png", dpi=180)
    plt.close(figure)


def main() -> None:
    started = time.monotonic()
    region_data = {}
    for name, config in REGIONS.items():
        dem, water = build_region_mosaic(name, config["bounds"])
        region_data[name] = {
            "dem": dem,
            "water": water,
            "shade": make_hillshade(dem, water, config["bounds"]),
        }
    metrics = build_pmtiles(region_data)
    metrics["elapsed_seconds_cache_dependent"] = time.monotonic() - started
    pd.DataFrame([metrics]).to_csv(ROOT / "outputs/pilot-relief-haute-resolution-metriques.csv", index=False)
    make_comparison(region_data)
    print(metrics)


if __name__ == "__main__":
    main()
