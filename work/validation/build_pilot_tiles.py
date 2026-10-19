#!/usr/bin/env python3
"""Build the step 2B raster-tile pilot without application code."""

from __future__ import annotations

import json
import math
import shutil
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import mercantile
import numpy as np
import pandas as pd
import rasterio
from rasterio.errors import RasterioIOError
from rasterio.io import MemoryFile
from rasterio.shutil import copy as raster_copy
from matplotlib import pyplot as plt
from matplotlib.colors import LightSource
from PIL import Image
from pmtiles.convert import disk_to_pmtiles
from rasterio.enums import Resampling
from rasterio.transform import Affine, from_bounds
from rasterio.warp import reproject
from rasterio.windows import from_bounds as window_from_bounds
from scipy.ndimage import distance_transform_edt

from make_spatial_window_validation import ENV, dem_url, wbm_url


ROOT = Path(__file__).resolve().parents[2]
CACHE = ROOT / "work/validation/cache/pilot_etape_2b"
OUTPUT = ROOT / "outputs/pilot-etape-2b"
CACHE.mkdir(parents=True, exist_ok=True)
OUTPUT.mkdir(parents=True, exist_ok=True)

BOUNDS = (-10.0, 29.0, 8.0, 47.0)
WIDTH = 2160
HEIGHT = 2160
TRANSFORM = Affine(
    0.0083333333,
    0.0,
    -10.000139568850017,
    0.0,
    -0.0083333333,
    46.99986056315001,
)
CRS = "EPSG:4326"
YEARS = range(1991, 2021)
MONTHS = (1, 7)
ZOOMS = range(3, 8)
NODATA_TEMPERATURE = -32768

TEMPERATURE_STOPS = [
    (-30, "#313695"), (-20, "#4575b4"), (-10, "#74add1"),
    (-5, "#abd9e9"), (0, "#e0f3f8"), (5, "#ffffbf"),
    (10, "#fee090"), (15, "#fdae61"), (20, "#f46d43"),
    (25, "#d73027"), (35, "#a50026"), (40, "#67001f"),
]


def chelsa_url(year: int, month: int) -> str:
    return (
        "https://os.unil.cloud.switch.ch/chelsa02/chelsa/global/monthly/"
        f"tas/{year}/CHELSA_tas_{month:02d}_{year}_V.2.1.tif"
    )


def read_temperature_normal(month: int) -> np.ndarray:
    path = CACHE / f"tavg_{month:02d}_1991_2020.npy"
    if path.exists():
        return np.load(path)

    total = np.zeros((HEIGHT, WIDTH), dtype="float64")
    count = np.zeros((HEIGHT, WIDTH), dtype="uint8")
    for index, year in enumerate(YEARS, start=1):
        with rasterio.Env(**ENV), rasterio.open(chelsa_url(year, month)) as source:
            window = window_from_bounds(*BOUNDS, transform=source.transform).round_offsets().round_lengths()
            raw = source.read(1, window=window)
            if raw.shape != (HEIGHT, WIDTH):
                raise RuntimeError(f"Unexpected CHELSA pilot shape: {raw.shape}")
            valid = raw != source.nodata
            celsius = raw.astype("float32") * source.scales[0] + source.offsets[0] - 273.15
            total[valid] += celsius[valid]
            count[valid] += 1
        if index % 5 == 0:
            print(f"CHELSA mois {month:02d}: {index}/30", flush=True)

    normal = np.full((HEIGHT, WIDTH), np.nan, dtype="float32")
    valid = count == len(YEARS)
    normal[valid] = (total[valid] / count[valid]).astype("float32")
    np.save(path, normal)
    return normal


def read_copdem_tile(south: int, west: int) -> tuple[int, int, np.ndarray, np.ndarray]:
    shape = (120, 120)
    bounds = (west, south, west + 1, south + 1)
    tile_cache = CACHE / "copdem_tiles" / f"{south:+03d}_{west:+04d}.npz"
    if tile_cache.exists():
        cached = np.load(tile_cache)
        return south, west, cached["dem"], cached["water"]
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
        # Copernicus does not publish every fully oceanic one-degree tile.
        dem = np.zeros(shape, dtype="float32")
        water = np.ones(shape, dtype="uint8")
    tile_cache.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(tile_cache, dem=dem, water=water)
    return south, west, dem, water


def read_relief_and_water() -> tuple[np.ndarray, np.ndarray]:
    path = CACHE / "copdem_wbm_1km.npz"
    if path.exists():
        data = np.load(path)
        return data["dem"], data["water"]

    dem = np.full((HEIGHT, WIDTH), np.nan, dtype="float32")
    water = np.full((HEIGHT, WIDTH), 255, dtype="uint8")
    jobs = [
        (south, west)
        for south in range(int(BOUNDS[1]), int(BOUNDS[3]))
        for west in range(int(BOUNDS[0]), int(BOUNDS[2]))
    ]
    with ThreadPoolExecutor(max_workers=8) as pool:
        futures = {pool.submit(read_copdem_tile, *job): job for job in jobs}
        for index, future in enumerate(as_completed(futures), start=1):
            south, west, tile_dem, tile_water = future.result()
            x0 = (west - int(BOUNDS[0])) * 120
            y0 = (int(BOUNDS[3]) - south - 1) * 120
            dem[y0 : y0 + 120, x0 : x0 + 120] = tile_dem
            water[y0 : y0 + 120, x0 : x0 + 120] = tile_water
            if index % 25 == 0 or index == len(jobs):
                print(f"Copernicus DEM/WBM: {index}/{len(jobs)}", flush=True)
    np.savez_compressed(path, dem=dem, water=water)
    return dem, water


def hillshade(dem: np.ndarray, water: np.ndarray) -> np.ndarray:
    land = (water == 0) & np.isfinite(dem)
    nearest = distance_transform_edt(~land, return_distances=False, return_indices=True)
    filled = dem[tuple(nearest)]
    latitude = (BOUNDS[1] + BOUNDS[3]) / 2
    dx = (BOUNDS[2] - BOUNDS[0]) / WIDTH * 111_320 * math.cos(math.radians(latitude))
    dy = (BOUNDS[3] - BOUNDS[1]) / HEIGHT * 111_320
    return LightSource(azdeg=315, altdeg=40).hillshade(
        filled, dx=dx, dy=dy, vert_exag=1.4
    ).astype("float32")


def write_cog(path: Path, data: np.ndarray, dtype: str, nodata: int, scale: float) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    profile = {
        "driver": "GTiff",
        "width": WIDTH,
        "height": HEIGHT,
        "count": 1,
        "dtype": dtype,
        "crs": CRS,
        "transform": TRANSFORM,
        "nodata": nodata,
        "tiled": True,
        "blockxsize": 256,
        "blockysize": 256,
        "compress": "deflate",
        "predictor": 2,
    }
    temporary = path.with_suffix(".building.tif")
    with MemoryFile() as memory:
        with memory.open(**profile) as dataset:
            dataset.write(data, 1)
            dataset.scales = (scale,)
            dataset.offsets = (0.0,)
        with memory.open() as source:
            raster_copy(
                source,
                temporary,
                driver="COG",
                BLOCKSIZE=256,
                COMPRESS="DEFLATE",
                PREDICTOR="YES",
                OVERVIEWS="AUTO",
                RESAMPLING="AVERAGE",
            )
    temporary.replace(path)


def colorize(values: np.ndarray) -> np.ndarray:
    stop_values = np.asarray([item[0] for item in TEMPERATURE_STOPS], dtype="float32")
    stop_colors = np.asarray(
        [[int(color[index : index + 2], 16) for index in (1, 3, 5)] for _, color in TEMPERATURE_STOPS],
        dtype="float32",
    )
    clipped = np.clip(values, stop_values[0], stop_values[-1])
    rgb = np.empty(values.shape + (3,), dtype="uint8")
    for channel in range(3):
        rgb[..., channel] = np.interp(clipped, stop_values, stop_colors[:, channel]).astype("uint8")
    return rgb


def tile_array(source: np.ndarray, tile: mercantile.Tile, resampling: Resampling, nodata: float) -> np.ndarray:
    bounds = mercantile.xy_bounds(tile)
    destination = np.full((256, 256), nodata, dtype="float32")
    reproject(
        source=source,
        destination=destination,
        src_transform=TRANSFORM,
        src_crs=CRS,
        src_nodata=nodata,
        dst_transform=from_bounds(bounds.left, bounds.bottom, bounds.right, bounds.top, 256, 256),
        dst_crs="EPSG:3857",
        dst_nodata=nodata,
        resampling=resampling,
    )
    return destination


def tile_water(source: np.ndarray, tile: mercantile.Tile) -> np.ndarray:
    bounds = mercantile.xy_bounds(tile)
    destination = np.full((256, 256), 255, dtype="uint8")
    reproject(
        source=source,
        destination=destination,
        src_transform=TRANSFORM,
        src_crs=CRS,
        src_nodata=255,
        dst_transform=from_bounds(bounds.left, bounds.bottom, bounds.right, bounds.top, 256, 256),
        dst_crs="EPSG:3857",
        dst_nodata=255,
        resampling=Resampling.nearest,
    )
    return destination


def save_webp(path: Path, rgba: np.ndarray) -> int:
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.fromarray(rgba, mode="RGBA").save(path, "WEBP", quality=85, method=6)
    return path.stat().st_size


def build_tileset(
    name: str,
    temperature: np.ndarray | None,
    shade: np.ndarray,
    water: np.ndarray,
    variant: str,
    month: int | None,
) -> dict:
    with tempfile.TemporaryDirectory(prefix=f"{name}-", dir=CACHE) as temp:
        directory = Path(temp)
        sizes = []
        for tile in mercantile.tiles(*BOUNDS, zooms=ZOOMS, truncate=True):
            tile_land = tile_water(water, tile) == 0
            if not tile_land.any():
                continue
            tile_shade = tile_array(shade, tile, Resampling.bilinear, -9999)
            if variant == "relief":
                gray = np.clip(tile_shade * 255, 0, 255).astype("uint8")
                rgba = np.zeros((256, 256, 4), dtype="uint8")
                rgba[..., :3] = gray[..., None]
                rgba[..., 3] = np.where(tile_land, 88, 0).astype("uint8")
            else:
                assert temperature is not None
                tile_temperature = tile_array(
                    temperature, tile, Resampling.bilinear, float(NODATA_TEMPERATURE)
                )
                valid = tile_land & (tile_temperature != NODATA_TEMPERATURE)
                rgb = colorize(tile_temperature)
                if variant == "integrated":
                    factor = np.clip(0.68 + 0.48 * tile_shade, 0.62, 1.12)
                    rgb = np.clip(rgb.astype("float32") * factor[..., None], 0, 255).astype("uint8")
                rgba = np.zeros((256, 256, 4), dtype="uint8")
                rgba[..., :3] = rgb
                rgba[..., 3] = np.where(valid, 230, 0).astype("uint8")
            tile_path = directory / str(tile.z) / str(tile.x) / f"{tile.y}.webp"
            sizes.append(save_webp(tile_path, rgba))

        metadata = {
            "name": name,
            "description": "Better Weather Place step 2B pilot",
            "format": "webp",
            "bounds": ",".join(str(value) for value in BOUNDS),
            "center": "-1,38,5",
            "minzoom": min(ZOOMS),
            "maxzoom": max(ZOOMS),
            "attribution": "CHELSA; Copernicus DEM GLO-30",
            "type": "overlay",
        }
        (directory / "metadata.json").write_text(json.dumps(metadata, ensure_ascii=False))
        output_path = OUTPUT / f"{name}.pmtiles"
        disk_to_pmtiles(str(directory), str(output_path), "auto", tile_format="webp")

    return {
        "asset": output_path.name,
        "month": month,
        "variant": variant,
        "tile_count": len(sizes),
        "unpacked_tile_bytes": int(sum(sizes)),
        "median_tile_bytes": int(np.median(sizes)),
        "p90_tile_bytes": int(np.percentile(sizes, 90)),
        "pmtiles_bytes": output_path.stat().st_size,
    }


def make_preview(temperatures: dict[int, np.ndarray], shade: np.ndarray, water: np.ndarray) -> None:
    land = water == 0
    figure, axes = plt.subplots(2, 2, figsize=(13, 12), constrained_layout=True)
    for row, month in enumerate(MONTHS):
        rgb = colorize(temperatures[month])
        integrated = np.clip(
            rgb.astype("float32") * np.clip(0.68 + 0.48 * shade, 0.62, 1.12)[..., None],
            0,
            255,
        ).astype("uint8")
        separate = np.clip(
            rgb.astype("float32") * (0.80 + 0.30 * shade[..., None]), 0, 255
        ).astype("uint8")
        for column, (title, image) in enumerate(
            (("Relief intégré", integrated), ("Relief séparé simulé", separate))
        ):
            rgba = np.dstack([image, np.where(land, 255, 0).astype("uint8")])
            axes[row, column].imshow(
                rgba,
                extent=(BOUNDS[0], BOUNDS[2], BOUNDS[1], BOUNDS[3]),
                origin="upper",
            )
            axes[row, column].set_facecolor("#dceef4")
            axes[row, column].set_title(f"{title} — {'janvier' if month == 1 else 'juillet'}")
            axes[row, column].set_xlabel("longitude")
            axes[row, column].set_ylabel("latitude")
    figure.suptitle("Lot témoin 2B — température moyenne CHELSA 1991–2020", fontsize=16)
    figure.savefig(ROOT / "outputs/pilot-etape-2b-apercu.png", dpi=180)
    plt.close(figure)


def make_detail_preview(
    temperatures: dict[int, np.ndarray], shade: np.ndarray, water: np.ndarray
) -> None:
    regions = {
        "Alpes": (5.4, 44.8, 7.6, 46.6),
        "Pyrénées": (-1.2, 41.8, 3.5, 43.6),
        "Haut Atlas": (-9.2, 30.0, -5.3, 32.6),
    }
    figure, axes = plt.subplots(3, 4, figsize=(18, 13), constrained_layout=True)
    for row, (region, bounds) in enumerate(regions.items()):
        window = window_from_bounds(*bounds, transform=TRANSFORM).round_offsets().round_lengths()
        row0, col0 = int(window.row_off), int(window.col_off)
        row1, col1 = row0 + int(window.height), col0 + int(window.width)
        region_shade = shade[row0:row1, col0:col1]
        region_land = water[row0:row1, col0:col1] == 0
        for month_index, month in enumerate(MONTHS):
            region_temperature = temperatures[month][row0:row1, col0:col1]
            rgb = colorize(region_temperature)
            variants = (
                (
                    "intégré",
                    np.clip(
                        rgb.astype("float32")
                        * np.clip(0.68 + 0.48 * region_shade, 0.62, 1.12)[..., None],
                        0,
                        255,
                    ).astype("uint8"),
                ),
                (
                    "séparé simulé",
                    np.clip(
                        rgb.astype("float32") * (0.80 + 0.30 * region_shade[..., None]),
                        0,
                        255,
                    ).astype("uint8"),
                ),
            )
            for variant_index, (variant, image) in enumerate(variants):
                column = month_index * 2 + variant_index
                rgba = np.dstack([image, np.where(region_land, 255, 0).astype("uint8")])
                axes[row, column].imshow(
                    rgba,
                    extent=(bounds[0], bounds[2], bounds[1], bounds[3]),
                    origin="upper",
                )
                axes[row, column].set_facecolor("#dceef4")
                month_name = "janvier" if month == 1 else "juillet"
                axes[row, column].set_title(f"{region} — {month_name}, {variant}")
                axes[row, column].set_xlabel("longitude")
                axes[row, column].set_ylabel("latitude")
    figure.suptitle("Détails du relief — lot témoin 2B", fontsize=16)
    figure.savefig(ROOT / "outputs/pilot-etape-2b-details-relief.png", dpi=180)
    plt.close(figure)


def validate_pilot_values() -> dict:
    points = [
        ("Essaouira", 31.509, -9.770),
        ("Marrakech", 31.630, -8.009),
        ("Ifrane", 33.522, -5.110),
        ("Font-Romeu", 42.505, 2.040),
        ("Chamonix", 45.924, 6.870),
    ]
    reference = pd.read_csv(ROOT / "work/validation/chelsa_points_jan_jul_1991_2020.csv")
    errors = []
    cog_bytes = 0
    cog_layouts = []
    for month in MONTHS:
        path = OUTPUT / f"data/1991-2020/tavg/{month:02d}.tif"
        cog_bytes += path.stat().st_size
        with rasterio.open(path) as dataset:
            cog_layouts.append(dataset.tags(ns="IMAGE_STRUCTURE").get("LAYOUT"))
            pixels = dataset.sample([(longitude, latitude) for _, latitude, longitude in points])
            for (name, _, _), pixel in zip(points, pixels):
                value = float(pixel[0]) * dataset.scales[0]
                expected = reference.loc[
                    (reference["point"] == name)
                    & (reference["month"] == month)
                    & (reference["variable"] == "tas"),
                    "value",
                ].mean()
                errors.append(abs(value - expected))
    return {
        "maximum_point_error_c": max(errors),
        "cog_bytes": cog_bytes,
        "all_cogs_strict": all(layout == "COG" for layout in cog_layouts),
    }


def write_report(metrics: pd.DataFrame, elapsed_seconds: float, validation: dict) -> None:
    metrics.to_csv(ROOT / "outputs/pilot-etape-2b-metriques.csv", index=False)
    integrated = metrics[metrics["variant"] == "integrated"]["pmtiles_bytes"].sum()
    plain = metrics[metrics["variant"] == "plain"]["pmtiles_bytes"].sum()
    relief = metrics[metrics["variant"] == "relief"]["pmtiles_bytes"].sum()
    average_integrated = integrated / len(MONTHS)
    average_plain = plain / len(MONTHS)
    break_even_layers = relief / (average_integrated - average_plain)
    report = f"""# Étape 2B — Lot de tuiles témoin

Date : 19 octobre 2026

## Périmètre

- variable : température moyenne CHELSA 1991–2020 ;
- mois : janvier et juillet ;
- emprise : 10° O–8° E et 29–47° N ;
- tuiles : zooms 3 à 7, WebP qualité 85, archives PMTiles ;
- masque terre/eau et relief : Copernicus DEM GLO-30 ré-échantillonné à environ 1 km pour ce témoin.

## Résultats de volume

- deux archives avec relief intégré : **{integrated / 1024**2:.2f} Mio** ;
- deux archives climatiques sans relief : **{plain / 1024**2:.2f} Mio** ;
- archive de relief séparée et réutilisable : **{relief / 1024**2:.2f} Mio** ;
- option séparée complète pour les deux mois : **{(plain + relief) / 1024**2:.2f} Mio** ;
- durée de l’exécution courante, dépendante de l’état du cache local : **{elapsed_seconds / 60:.1f} min**.

Le poids d’une archive entière n’est pas le volume chargé à l’ouverture : PMTiles récupère uniquement l’index et les plages d’octets correspondant aux tuiles visibles.

Chaque archive contient **91 tuiles**. La taille médiane va d’environ **1,4 à 2,4 ko** selon la variante. Les deux COG numériques occupent ensemble **{validation['cog_bytes'] / 1024**2:.2f} Mio**.

## Contrôles techniques

- les cinq archives sont des PMTiles version 3 contenant des tuiles WebP, zooms 3 à 7 ;
- les deux fichiers numériques sont des COG stricts : **{'oui' if validation['all_cogs_strict'] else 'non'}** ;
- le contrôle sur Essaouira, Marrakech, Ifrane, Font-Romeu et Chamonix donne un écart maximal COG/source de **{validation['maximum_point_error_c']:.3f} °C**, entièrement expliqué par l’arrondi au dixième ;
- deux points marins de contrôle sont sans donnée tandis que Madrid et Marrakech restent terrestres ;
- la comparaison détaillée des Alpes, des Pyrénées et du Haut Atlas est fournie dans `pilot-etape-2b-details-relief.png`.

## Interprétation

Le relief intégré économise une source et une requête par tuile, mais il faut recalculer le relief dans chaque mois et il ne peut plus être réglé indépendamment. Le relief séparé ajoute une archive commune, réutilisable par toutes les variables et tous les mois. La comparaison visuelle de `pilot-etape-2b-apercu.png` doit guider le choix, en complément des tailles détaillées du CSV.

Sur ce témoin, le surcoût fixe du relief séparé est amorti après environ **{break_even_layers:.1f} couches**. Le produit final en prévoit 72. Les détails montrent une qualité visuelle très proche entre les deux variantes.

**Décision pour la maquette : conserver le relief dans une couche séparée.** Le premier affichage demande une source supplémentaire, mais elle reste ensuite en cache lors des changements de mois ou de variable. Cette solution réduit la répétition des données, permet de régler l’intensité du relief et évite de recalculer le même ombrage dans chaque archive climatique.

Ce témoin ne sert pas encore de couche de production : le relief a été ramené à la grille climatique d’environ 1 km. Un test local à plus haute résolution sera nécessaire avant de fixer les zooms du relief final.
"""
    (ROOT / "outputs/pilot-etape-2b-rapport.md").write_text(report)


def main() -> None:
    started = time.monotonic()
    temperatures = {month: read_temperature_normal(month) for month in MONTHS}
    dem, water = read_relief_and_water()
    shade = hillshade(dem, water)

    data_dir = OUTPUT / "data/1991-2020/tavg"
    for month, temperature in temperatures.items():
        stored = np.full(temperature.shape, NODATA_TEMPERATURE, dtype="int16")
        valid = np.isfinite(temperature) & (water == 0)
        stored[valid] = np.rint(temperature[valid] * 10).astype("int16")
        write_cog(data_dir / f"{month:02d}.tif", stored, "int16", NODATA_TEMPERATURE, 0.1)

    metrics = []
    for month, temperature in temperatures.items():
        for variant in ("plain", "integrated"):
            metrics.append(
                build_tileset(
                    f"tavg-{month:02d}-{variant}", temperature, shade, water, variant, month
                )
            )
    metrics.append(build_tileset("relief-separate", None, shade, water, "relief", None))

    make_preview(temperatures, shade, water)
    make_detail_preview(temperatures, shade, water)
    validation = validate_pilot_values()
    write_report(pd.DataFrame(metrics), time.monotonic() - started, validation)
    shutil.rmtree(CACHE / "unused", ignore_errors=True)
    print(f"Lot témoin écrit dans {OUTPUT}")


if __name__ == "__main__":
    main()
