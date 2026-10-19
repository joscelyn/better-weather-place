#!/usr/bin/env python3
"""Build monthly rainy-day normals from downloaded CERRA-Land tile archives."""

from __future__ import annotations

import argparse
import hashlib
import json
import tempfile
import zipfile
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import rasterio
from netCDF4 import Dataset, num2date
from rasterio.shutil import copy as raster_copy
from rasterio.transform import from_origin
from rasterio.windows import Window

from download_cerra_rain import DEFAULT_BOUNDS, DEFAULT_OUTPUT as DEFAULT_INPUT, LAND_PATH, build_jobs, download_land_reference, parse_bounds, paths_for


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = ROOT / "work/derived/1991-2020"
NODATA = 65535
SCALE = 0.1
RESOLUTION = 0.05
YEARS = np.arange(1991, 2021)


def read_tile(path: Path) -> tuple[np.ndarray, np.ndarray, dict[int, np.ndarray]]:
    with zipfile.ZipFile(path) as archive:
        members = [name for name in archive.namelist() if name.endswith(".nc")]
        if len(members) != 1:
            raise RuntimeError(f"Un NetCDF attendu dans {path}")
        payload = archive.read(members[0])
    with tempfile.NamedTemporaryFile(suffix=".nc") as temporary:
        temporary.write(payload)
        temporary.flush()
        with Dataset(temporary.name) as dataset:
            latitude = np.asarray(dataset["latitude"][:], dtype="float64")
            longitude = np.asarray(dataset["longitude"][:], dtype="float64")
            time_variable = dataset["valid_time"]
            dates = num2date(
                time_variable[:],
                time_variable.units,
                only_use_cftime_datetimes=False,
            )
            years = np.fromiter((date.year for date in dates), dtype="int16")
            months = np.fromiter((date.month for date in dates), dtype="uint8")
            precipitation = np.ma.filled(dataset["tp"][:], np.nan).astype("float32")
    if not np.isfinite(precipitation).all():
        raise RuntimeError(f"Valeurs manquantes dans {path}")
    normals: dict[int, np.ndarray] = {}
    rainy = precipitation >= 1.0
    for month in range(1, 13):
        annual = np.stack(
            [rainy[(years == year) & (months == month)].sum(axis=0) for year in YEARS]
        )
        normals[month] = annual.mean(axis=0, dtype="float64").astype("float32")
    return latitude, longitude, normals


def encode(values: np.ndarray) -> np.ndarray:
    return np.floor(values / SCALE + 0.5).astype("uint16")


def grid(bounds: tuple[float, float, float, float]) -> tuple[int, int, rasterio.Affine]:
    west, south, east, north = bounds
    width = round((east - west) / RESOLUTION)
    height = round((north - south) / RESOLUTION)
    # CDS area extracts omit the west/south edge and include east/north.
    transform = from_origin(west + RESOLUTION / 2, north + RESOLUTION / 2, RESOLUTION, RESOLUTION)
    return width, height, transform


def initialise_working(output: Path, bounds: tuple[float, float, float, float]) -> list[Path]:
    width, height, transform = grid(bounds)
    directory = output / ".rainy-days-working"
    directory.mkdir(parents=True, exist_ok=True)
    paths = [directory / f"{month:02d}.tif" for month in range(1, 13)]
    profile = {
        "driver": "GTiff", "width": width, "height": height, "count": 1,
        "dtype": "uint16", "crs": "EPSG:4326", "transform": transform,
        "nodata": NODATA, "tiled": True, "blockxsize": 256, "blockysize": 256,
        "compress": "DEFLATE", "predictor": 2, "BIGTIFF": "IF_SAFER",
    }
    for month, path in enumerate(paths, start=1):
        if path.exists():
            continue
        with rasterio.open(path, "w", **profile) as dataset:
            dataset.write(np.full((height, width), NODATA, dtype="uint16"), 1)
            dataset.scales = (SCALE,)
            dataset.offsets = (0.0,)
            dataset.units = ("days/month",)
            dataset.update_tags(
                source="CERRA-Land", threshold="daily precipitation >= 1.0 mm",
                reference_period="1991-2020", month=f"{month:02d}", water_mask_applied="false",
            )
    return paths


def state_path(output: Path) -> Path:
    return output / ".rainy-days-working/state.json"


def load_state(output: Path, bounds: tuple[float, float, float, float]) -> set[str]:
    path = state_path(output)
    if not path.exists():
        return set()
    state = json.loads(path.read_text())
    if tuple(state["bounds"]) != bounds:
        raise RuntimeError("L'emprise du travail existant diffère de la demande")
    return set(state["completed_tiles"])


def save_state(output: Path, bounds: tuple[float, float, float, float], completed: set[str]) -> None:
    path = state_path(output)
    temporary = path.with_suffix(".json.part")
    temporary.write_text(json.dumps({
        "bounds": list(bounds), "completed_tiles": sorted(completed),
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }, ensure_ascii=False, indent=2) + "\n")
    temporary.replace(path)


def write_tile(
    working: list[Path], bounds: tuple[float, float, float, float],
    latitude: np.ndarray, longitude: np.ndarray, normals: dict[int, np.ndarray],
) -> None:
    west, _, _, north = bounds
    column = round((longitude[0] - (west + RESOLUTION)) / RESOLUTION)
    row = round((north - latitude[-1]) / RESOLUTION)
    window = Window(column, row, len(longitude), len(latitude))
    for month, path in enumerate(working, start=1):
        with rasterio.open(path, "r+") as dataset:
            dataset.write(encode(normals[month])[::-1, :], 1, window=window)


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(4 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def finalise(output: Path, working: list[Path], tile_count: int) -> None:
    directory = output / "rainy_days"
    directory.mkdir(parents=True, exist_ok=True)
    for month, source_path in enumerate(working, start=1):
        final = directory / f"{month:02d}.tif"
        building = final.with_suffix(".building.tif")
        with rasterio.open(source_path) as source:
            raster_copy(
                source, building, driver="COG", BLOCKSIZE=256, COMPRESS="DEFLATE",
                PREDICTOR="YES", OVERVIEWS="AUTO", RESAMPLING="AVERAGE",
            )
        building.replace(final)
        with rasterio.open(final) as dataset:
            values = dataset.read(1, masked=True).compressed().astype("float64") * SCALE
        final.with_suffix(".tif.json").write_text(json.dumps({
            "layer_id": "rainy_days", "month": month, "period": "1991-2020",
            "threshold": "daily precipitation >= 1.0 mm", "tile_count": tile_count,
            "minimum_days": round(float(values.min()), 2),
            "maximum_days": round(float(values.max()), 2),
            "scale_factor": SCALE, "water_mask_applied": False,
            "bytes": final.stat().st_size, "sha256": file_sha256(final),
            "completed_at": datetime.now(timezone.utc).isoformat(),
        }, ensure_ascii=False, indent=2) + "\n")


def main() -> int:
    parser = argparse.ArgumentParser(description="Calcule les normales de jours de pluie CERRA-Land.")
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--bounds", type=parse_bounds, default=DEFAULT_BOUNDS)
    parser.add_argument("--strict", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    download_land_reference(LAND_PATH)
    jobs = build_jobs(args.bounds, LAND_PATH)
    available = [tile for tile in jobs if paths_for(args.input, tile)[0].exists()]
    print(f"Jours de pluie : {len(available)}/{len(jobs)} tuiles téléchargées")
    if args.dry_run:
        return 2 if args.strict and len(available) != len(jobs) else 0

    working = initialise_working(args.output, args.bounds)
    completed = load_state(args.output, args.bounds)
    pending = [tile for tile in available if tile.identifier not in completed]
    try:
        for index, tile in enumerate(pending, start=1):
            archive = paths_for(args.input, tile)[0]
            latitude, longitude, normals = read_tile(archive)
            write_tile(working, args.bounds, latitude, longitude, normals)
            completed.add(tile.identifier)
            if index % 25 == 0 or index == len(pending):
                save_state(args.output, args.bounds, completed)
                print(f"[{len(completed)}/{len(jobs)}] tuiles calculées", flush=True)
    except KeyboardInterrupt:
        save_state(args.output, args.bounds, completed)
        print("Interruption; progression enregistrée.")
        return 130

    if len(completed) == len(jobs):
        finalise(args.output, working, len(jobs))
        print("Douze COG de jours de pluie terminés.")
        return 0
    print(f"Travail partiel conservé; {len(jobs) - len(completed)} tuiles restent à télécharger/calculer.")
    return 2 if args.strict else 0


if __name__ == "__main__":
    raise SystemExit(main())
