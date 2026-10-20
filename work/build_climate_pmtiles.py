#!/usr/bin/env python3
"""Build resumable production PMTiles from the WBM-masked climate COGs."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path

import mercantile
import numpy as np
import rasterio
from PIL import Image
from pmtiles.convert import disk_to_pmtiles
from pmtiles.reader import MmapSource, Reader, all_tiles
from rasterio.enums import Resampling
from rasterio.transform import from_bounds
from rasterio.warp import reproject


ROOT = Path(__file__).resolve().parents[1]
CONTRACT_PATH = ROOT / "outputs/contrat-donnees-v1.json"
DEFAULT_SOURCE = ROOT / "work/derived/1991-2020-masked"
DEFAULT_OUTPUT = ROOT / "work/tiles/1991-2020"
DEFAULT_INVENTORY = ROOT / "outputs/inventaire-pmtiles-production.csv"
AVAILABLE_LAYERS = ("tavg", "tmax", "tmin", "precipitation", "sunshine")
TILE_SIZE = 256
MIN_ZOOM = 3
WEBP_QUALITY = 85
WEBP_METHOD = 4
RENDER_BUFFER = 2


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(4 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def parse_csv(value: str) -> list[str]:
    return [item.strip() for item in value.split(",") if item.strip()]


def parse_months(value: str) -> list[int]:
    months = [int(item) for item in parse_csv(value)]
    if not months or any(month < 1 or month > 12 for month in months):
        raise argparse.ArgumentTypeError("Mois attendus entre 1 et 12, séparés par des virgules")
    return sorted(set(months))


def load_contract() -> tuple[dict, dict[str, dict]]:
    contract = json.loads(CONTRACT_PATH.read_text())
    return contract, {layer["id"]: layer for layer in contract["layers"]}


def palette_for(layer: dict, layers: dict[str, dict]) -> list[list]:
    palette = layer.get("palette")
    if palette is None:
        palette = layers[layer["palette_ref"]]["palette"]
    return palette["stops"]


def colorize(values: np.ndarray, stops: list[list]) -> np.ndarray:
    stop_values = np.asarray([stop[0] for stop in stops], dtype="float32")
    stop_colors = np.asarray(
        [[int(color[index : index + 2], 16) for index in (1, 3, 5)] for _, color in stops],
        dtype="float32",
    )
    clipped = np.clip(values, stop_values[0], stop_values[-1])
    rgb = np.empty(values.shape + (3,), dtype="uint8")
    for channel in range(3):
        rgb[..., channel] = np.rint(
            np.interp(clipped, stop_values, stop_colors[:, channel])
        ).astype("uint8")
    return rgb


def source_identity(path: Path) -> str:
    sidecar = path.with_suffix(path.suffix + ".json")
    if sidecar.exists():
        metadata = json.loads(sidecar.read_text())
        if metadata.get("sha256"):
            return metadata["sha256"]
    return sha256(path)


def expected_build(
    source: Path,
    layer_id: str,
    month: int,
    min_zoom: int,
    max_zoom: int,
    quality: int,
    method: int,
    stops: list[list],
) -> dict:
    return {
        "schema_version": 1,
        "source_sha256": source_identity(source),
        "layer_id": layer_id,
        "month": month,
        "min_zoom": min_zoom,
        "max_zoom": max_zoom,
        "tile_size": TILE_SIZE,
        "format": "webp",
        "webp_quality": quality,
        "webp_method": method,
        "render_buffer_pixels": RENDER_BUFFER,
        "palette_stops": stops,
        "alpha": "opaque-valid-transparent-nodata",
        "resampling": "bilinear",
    }


def inspect_pmtiles(path: Path) -> dict:
    with path.open("rb") as stream:
        source = MmapSource(stream)
        reader = Reader(source)
        header = reader.header()
        metadata = reader.metadata()
        enumerated = sum(1 for _ in all_tiles(source))
    return {
        "tile_count": header["addressed_tiles_count"],
        "enumerated_tile_count": enumerated,
        "min_zoom": header["min_zoom"],
        "max_zoom": header["max_zoom"],
        "tile_type": str(header["tile_type"]).split(".")[-1].lower(),
        "metadata": metadata,
    }


def is_current(output: Path, expected: dict) -> bool:
    sidecar = output.with_suffix(output.suffix + ".json")
    if not output.exists() or not sidecar.exists() or output.stat().st_size == 0:
        return False
    try:
        metadata = json.loads(sidecar.read_text())
        if any(metadata.get(key) != value for key, value in expected.items()):
            return False
        if metadata.get("bytes") != output.stat().st_size:
            return False
        if metadata.get("sha256") != sha256(output):
            return False
        inspection = inspect_pmtiles(output)
        return (
            inspection["tile_count"] == metadata.get("tile_count")
            and inspection["enumerated_tile_count"] == metadata.get("tile_count")
            and inspection["min_zoom"] == expected["min_zoom"]
            and inspection["max_zoom"] == expected["max_zoom"]
        )
    except (OSError, ValueError, KeyError, json.JSONDecodeError):
        return False


def render_tile(
    dataset: rasterio.io.DatasetReader,
    tile: mercantile.Tile,
    stops: list[list],
) -> np.ndarray | None:
    bounds = mercantile.xy_bounds(tile)
    render_size = TILE_SIZE + 2 * RENDER_BUFFER
    pixel_width = (bounds.right - bounds.left) / TILE_SIZE
    pixel_height = (bounds.top - bounds.bottom) / TILE_SIZE
    buffered_bounds = (
        bounds.left - RENDER_BUFFER * pixel_width,
        bounds.bottom - RENDER_BUFFER * pixel_height,
        bounds.right + RENDER_BUFFER * pixel_width,
        bounds.top + RENDER_BUFFER * pixel_height,
    )
    raw = np.full((render_size, render_size), dataset.nodata, dtype="float32")
    reproject(
        source=rasterio.band(dataset, 1),
        destination=raw,
        src_transform=dataset.transform,
        src_crs=dataset.crs,
        src_nodata=dataset.nodata,
        dst_transform=from_bounds(*buffered_bounds, render_size, render_size),
        dst_crs="EPSG:3857",
        dst_nodata=dataset.nodata,
        resampling=Resampling.bilinear,
    )
    raw = raw[
        RENDER_BUFFER : RENDER_BUFFER + TILE_SIZE,
        RENDER_BUFFER : RENDER_BUFFER + TILE_SIZE,
    ]
    valid = np.isfinite(raw) & (raw != dataset.nodata)
    if not valid.any():
        return None
    values = raw * dataset.scales[0] + dataset.offsets[0]
    rgba = np.zeros((TILE_SIZE, TILE_SIZE, 4), dtype="uint8")
    rgb = colorize(values, stops)
    rgba[..., :3][valid] = rgb[valid]
    rgba[..., 3] = np.where(valid, 255, 0).astype("uint8")
    return rgba


def build_one(
    source: Path,
    output: Path,
    layer: dict,
    layers: dict[str, dict],
    month: int,
    min_zoom: int,
    quality: int,
    method: int,
    force: bool,
) -> tuple[str, dict]:
    max_zoom = layer["native_max_zoom"]
    stops = palette_for(layer, layers)
    expected = expected_build(
        source, layer["id"], month, min_zoom, max_zoom, quality, method, stops
    )
    if not force and is_current(output, expected):
        return "current", json.loads(output.with_suffix(output.suffix + ".json").read_text())

    started = time.monotonic()
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary_archive = output.with_suffix(".building.pmtiles")
    temporary_archive.unlink(missing_ok=True)
    tile_sizes: list[int] = []

    with rasterio.open(source) as dataset, tempfile.TemporaryDirectory(
        prefix=f"pmtiles-{layer['id']}-{month:02d}-", dir=output.parent
    ) as temporary_directory:
        tile_directory = Path(temporary_directory)
        source_bounds = dataset.bounds
        for tile in mercantile.tiles(
            source_bounds.left,
            source_bounds.bottom,
            source_bounds.right,
            source_bounds.top,
            zooms=range(min_zoom, max_zoom + 1),
            truncate=True,
        ):
            rgba = render_tile(dataset, tile, stops)
            if rgba is None:
                continue
            tile_path = tile_directory / str(tile.z) / str(tile.x) / f"{tile.y}.webp"
            tile_path.parent.mkdir(parents=True, exist_ok=True)
            Image.fromarray(rgba).save(tile_path, "WEBP", quality=quality, method=method)
            tile_sizes.append(tile_path.stat().st_size)

        if not tile_sizes:
            raise RuntimeError(f"Aucune tuile valide produite depuis {source}")
        metadata = {
            "name": f"{layer['id']}-{month:02d}-1991-2020",
            "description": f"{layer['label_fr']} — normale climatique 1991–2020",
            "format": "webp",
            "bounds": ",".join(str(value) for value in source_bounds),
            "center": "10,48,4",
            "minzoom": min_zoom,
            "maxzoom": max_zoom,
            "attribution": layer["source"],
            "type": "overlay",
            "layer_id": layer["id"],
            "month": month,
            "unit": layer["unit"],
            "reference_period": "1991-2020",
        }
        (tile_directory / "metadata.json").write_text(
            json.dumps(metadata, ensure_ascii=False) + "\n"
        )
        disk_to_pmtiles(
            str(tile_directory), str(temporary_archive), "auto", tile_format="webp"
        )

    temporary_archive.replace(output)
    inspection = inspect_pmtiles(output)
    if inspection["enumerated_tile_count"] != len(tile_sizes):
        raise RuntimeError(
            f"Archive incohérente : {inspection['enumerated_tile_count']} tuiles lues, "
            f"{len(tile_sizes)} écrites"
        )
    result = {
        **expected,
        "tile_count": len(tile_sizes),
        "unpacked_tile_bytes": sum(tile_sizes),
        "median_tile_bytes": int(np.median(tile_sizes)),
        "p90_tile_bytes": int(np.percentile(tile_sizes, 90)),
        "bytes": output.stat().st_size,
        "sha256": sha256(output),
        "elapsed_seconds": round(time.monotonic() - started, 3),
        "completed_at": datetime.now(timezone.utc).isoformat(),
        "source_cog": str(source.relative_to(ROOT)),
        "pmtiles": str(output.relative_to(ROOT)),
    }
    output.with_suffix(output.suffix + ".json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    )
    return "built", result


def inventory(output_root: Path, destination: Path) -> list[dict]:
    rows = []
    for sidecar in sorted(output_root.glob("*/*.pmtiles.json")):
        metadata = json.loads(sidecar.read_text())
        archive = sidecar.with_suffix("")
        if not archive.exists():
            continue
        rows.append(metadata)
    columns = [
        "layer_id", "month", "min_zoom", "max_zoom", "tile_count", "bytes",
        "sha256", "source_sha256", "webp_quality", "webp_method",
        "render_buffer_pixels", "elapsed_seconds", "pmtiles",
    ]
    destination.parent.mkdir(parents=True, exist_ok=True)
    with destination.open("w", newline="") as stream:
        writer = csv.DictWriter(
            stream, fieldnames=columns, extrasaction="ignore", lineterminator="\n"
        )
        writer.writeheader()
        writer.writerows(rows)
    return rows


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Construit les archives PMTiles climatiques WebP à partir des COG masqués."
    )
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--inventory", type=Path, default=DEFAULT_INVENTORY)
    parser.add_argument("--layers", type=parse_csv, default=list(AVAILABLE_LAYERS))
    parser.add_argument("--months", type=parse_months, default=list(range(1, 13)))
    parser.add_argument("--min-zoom", type=int, default=MIN_ZOOM)
    parser.add_argument("--quality", type=int, default=WEBP_QUALITY)
    parser.add_argument("--method", type=int, default=WEBP_METHOD)
    parser.add_argument("--force", action="store_true")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    unknown = sorted(set(args.layers) - set(AVAILABLE_LAYERS))
    if unknown:
        raise SystemExit(f"Couches inconnues : {', '.join(unknown)}")
    if args.min_zoom < 0 or not 1 <= args.quality <= 100 or not 0 <= args.method <= 6:
        raise SystemExit("Zoom ou qualité WebP invalide")

    _, layer_contracts = load_contract()
    jobs = [(layer_id, month) for layer_id in args.layers for month in args.months]
    failures = 0
    for index, (layer_id, month) in enumerate(jobs, start=1):
        layer = layer_contracts[layer_id]
        source = args.source / layer_id / f"{month:02d}.tif"
        output = args.output / layer_id / f"{month:02d}.pmtiles"
        if not source.exists():
            print(f"[{index}/{len(jobs)}] absent : {source}", flush=True)
            failures += 1
            continue
        try:
            status, metadata = build_one(
                source, output, layer, layer_contracts, month,
                args.min_zoom, args.quality, args.method, args.force,
            )
            print(
                f"[{index}/{len(jobs)}] {layer_id}/{month:02d} {status} — "
                f"{metadata['tile_count']} tuiles, {metadata['bytes'] / 1024**2:.2f} Mio",
                flush=True,
            )
        except Exception as exc:
            failures += 1
            print(f"[{index}/{len(jobs)}] {layer_id}/{month:02d} échec : {exc}", flush=True)
    rows = inventory(args.output, args.inventory)
    print(f"Inventaire : {len(rows)} archives dans {args.inventory}", flush=True)
    return 2 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
