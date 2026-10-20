#!/usr/bin/env python3
"""Build land-fraction COGs from downloaded Copernicus GLO-30 WBM tiles."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import rasterio
from rasterio.enums import Resampling
from rasterio.shutil import copy as raster_copy
from rasterio.transform import from_bounds
from rasterio.vrt import WarpedVRT

from download_copdem_wbm import DEFAULT_CATALOGUE, DEFAULT_OUTPUT as DEFAULT_INPUT, Tile, paths_for


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = ROOT / "work/derived/1991-2020/masks"
DEFAULT_BOUNDS = (-25, 25, 45, 72)
PIXELS_PER_DEGREE = 120
SCALE = 0.0001
NODATA = 65535
REFERENCES = {
    "chelsa": ROOT / "work/derived/1991-2020/tavg/01.tif",
    "sarah": ROOT / "work/derived/1991-2020/sunshine/01.tif",
    "cerra": ROOT / "work/derived/1991-2020/.rainy-days-working/01.tif",
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(4 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_tiles(catalogue: Path) -> list[Tile]:
    rows = list(csv.DictReader(catalogue.open()))
    return [
        Tile(
            south=int(row["south"]), west=int(row["west"]), bytes=int(row["bytes"]),
            md5=row["etag"], url=row["url"],
        )
        for row in rows
    ]


def write_sidecar(path: Path, metadata: dict) -> None:
    metadata = {
        **metadata,
        "bytes": path.stat().st_size,
        "sha256": sha256(path),
        "completed_at": datetime.now(timezone.utc).isoformat(),
    }
    path.with_suffix(".tif.json").write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2) + "\n"
    )


def to_cog(working: Path, final: Path) -> None:
    building = final.with_suffix(".building.tif")
    with rasterio.open(working) as source:
        raster_copy(
            source, building, driver="COG", BLOCKSIZE=256, COMPRESS="DEFLATE",
            PREDICTOR="YES", OVERVIEWS="AUTO", RESAMPLING="AVERAGE",
        )
    working.unlink()
    building.replace(final)


def build_base(
    tiles: list[Tile], input_root: Path, output_root: Path,
    bounds: tuple[int, int, int, int],
) -> Path:
    final = output_root / "wbm-land-fraction-1km.tif"
    west, south, east, north = bounds
    width = (east - west) * PIXELS_PER_DEGREE
    height = (north - south) * PIXELS_PER_DEGREE
    transform = from_bounds(*bounds, width, height)
    working = final.with_suffix(".working.tif")
    final.parent.mkdir(parents=True, exist_ok=True)
    working.unlink(missing_ok=True)
    profile = {
        "driver": "GTiff", "width": width, "height": height, "count": 1,
        "dtype": "uint16", "crs": "EPSG:4326", "transform": transform,
        "tiled": True, "blockxsize": 256, "blockysize": 256,
        "compress": "DEFLATE", "predictor": 2, "BIGTIFF": "IF_SAFER",
        "sparse_ok": True,
    }
    with rasterio.open(working, "w", **profile) as target:
        target.scales = (SCALE,)
        target.offsets = (0.0,)
        target.units = ("fraction",)
        target.update_tags(
            source="Copernicus DEM GLO-30 WBM", classes="0 land; 1 ocean; 2 lake; 3 river",
            aggregation="fraction of native WBM pixels with class 0", canaries_included="false",
        )
        for index, tile in enumerate(tiles, start=1):
            path = paths_for(input_root, tile)[0]
            if not path.exists() or path.stat().st_size != tile.bytes:
                raise FileNotFoundError(f"Tuile WBM absente ou incomplète : {path}")
            with rasterio.open(path) as source:
                raw = source.read(1)
            if (
                raw.shape[0] % PIXELS_PER_DEGREE
                or raw.shape[1] % PIXELS_PER_DEGREE
                or raw.max() > 3
            ):
                raise RuntimeError(f"Tuile WBM inattendue : {path}")
            rows_per_cell = raw.shape[0] // PIXELS_PER_DEGREE
            columns_per_cell = raw.shape[1] // PIXELS_PER_DEGREE
            source_pixels_per_cell = rows_per_cell * columns_per_cell
            land_count = (raw == 0).reshape(
                PIXELS_PER_DEGREE, rows_per_cell,
                PIXELS_PER_DEGREE, columns_per_cell,
            ).sum(axis=(1, 3), dtype="uint16")
            fraction = np.floor(
                land_count.astype("float32") * (10_000 / source_pixels_per_cell) + 0.5
            ).astype("uint16")
            column = (tile.west - west) * PIXELS_PER_DEGREE
            row = (north - tile.south - 1) * PIXELS_PER_DEGREE
            target.write(
                fraction, 1,
                window=((row, row + PIXELS_PER_DEGREE), (column, column + PIXELS_PER_DEGREE)),
            )
            if index % 100 == 0 or index == len(tiles):
                print(f"Agrégation WBM : {index}/{len(tiles)}", flush=True)
    to_cog(working, final)
    write_sidecar(final, {
        "id": "wbm_land_fraction_1km", "source_tile_count": len(tiles),
        "bounds": list(bounds), "width": width, "height": height,
        "scale_factor": SCALE, "canaries_included": False,
    })
    return final


def build_aligned(base: Path, reference: Path, name: str, output_root: Path) -> Path:
    final = output_root / f"{name}-land-fraction.tif"
    working = final.with_suffix(".working.tif")
    working.unlink(missing_ok=True)
    with rasterio.open(reference) as grid, rasterio.open(base) as source:
        profile = grid.profile.copy()
        profile.update(
            driver="GTiff", dtype="uint16", nodata=NODATA, count=1,
            tiled=True, blockxsize=256, blockysize=256, compress="DEFLATE",
            predictor=2, BIGTIFF="IF_SAFER",
        )
        with WarpedVRT(
            source, crs=grid.crs, transform=grid.transform,
            width=grid.width, height=grid.height,
            resampling=Resampling.average, nodata=NODATA, dtype="uint16",
        ) as warped, rasterio.open(working, "w", **profile) as target:
            target.scales = (SCALE,)
            target.offsets = (0.0,)
            target.units = ("fraction",)
            target.update_tags(
                source="Copernicus DEM GLO-30 WBM", aligned_to=reference.relative_to(ROOT).as_posix(),
                canaries_included="false",
            )
            for _, window in target.block_windows(1):
                target.write(warped.read(1, window=window), 1, window=window)
    to_cog(working, final)
    with rasterio.open(final) as dataset:
        values = dataset.read(1, masked=True)
        valid = values.compressed()
        metadata = {
            "id": f"{name}_land_fraction", "aligned_to": reference.relative_to(ROOT).as_posix(),
            "width": dataset.width, "height": dataset.height, "scale_factor": SCALE,
            "land_cell_count": int((valid > 0).sum()),
            "mixed_cell_count": int(((valid > 0) & (valid < 10_000)).sum()),
            "water_cell_count": int((valid == 0).sum()),
            "canaries_included": False,
        }
    write_sidecar(final, metadata)
    print(f"Masque {name} : {final.name}", flush=True)
    return final


def main() -> int:
    parser = argparse.ArgumentParser(description="Construit les fractions terrestres WBM.")
    parser.add_argument("--catalogue", type=Path, default=DEFAULT_CATALOGUE)
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--base-only", action="store_true")
    args = parser.parse_args()
    tiles = load_tiles(args.catalogue)
    base = build_base(tiles, args.input, args.output, DEFAULT_BOUNDS)
    if not args.base_only:
        for name, reference in REFERENCES.items():
            if not reference.exists():
                raise FileNotFoundError(f"Grille de référence absente : {reference}")
            build_aligned(base, reference, name, args.output)
    print("Masques WBM terminés.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
