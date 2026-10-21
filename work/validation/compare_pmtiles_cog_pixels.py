#!/usr/bin/env python3
"""Compare deterministic PMTiles pixels with colors computed from their source COG."""

from __future__ import annotations

import argparse
import csv
import io
import json
from dataclasses import dataclass
from pathlib import Path

import mercantile
import numpy as np
import rasterio
from PIL import Image
from pmtiles.reader import MmapSource, Reader
from rasterio.enums import Resampling
from rasterio.transform import from_bounds
from rasterio.warp import reproject


ROOT = Path(__file__).resolve().parents[2]
CONTRACT_PATH = ROOT / "outputs/contrat-donnees-v1.json"
COG_ROOT = ROOT / "work/derived/1991-2020-masked"
PMTILES_ROOT = ROOT / "work/tiles/1991-2020"
CSV_PATH = ROOT / "outputs/comparaison-pixels-pmtiles-cog.csv"
REPORT_PATH = ROOT / "outputs/comparaison-pixels-pmtiles-cog.md"
TILE_SIZE = 256
RENDER_BUFFER = 2


@dataclass(frozen=True)
class Case:
    place: str
    longitude: float
    latitude: float
    layer: str
    month: int


CASES = (
    Case("Lisbonne", -9.1393, 38.7223, "comfort", 1),
    Case("Annecy", 6.1294, 45.8992, "tavg", 1),
    Case("Athènes", 23.7275, 37.9838, "tmax", 7),
    Case("Stockholm", 18.0686, 59.3293, "tmin", 1),
    Case("Valence", -0.3763, 39.4699, "precipitation", 10),
    Case("Marrakech", -7.9811, 31.6295, "sunshine", 7),
)


def palettes() -> tuple[dict[str, dict], dict[str, list[list]]]:
    contract = json.loads(CONTRACT_PATH.read_text())
    layers = {layer["id"]: layer for layer in contract["layers"]}
    resolved: dict[str, list[list]] = {}
    for layer_id, layer in layers.items():
        palette = layer.get("palette")
        if palette is None:
            palette = layers[layer["palette_ref"]]["palette"]
        resolved[layer_id] = palette["stops"]
    return layers, resolved


def colorize(value: float, stops: list[list]) -> tuple[int, int, int]:
    values = np.asarray([stop[0] for stop in stops], dtype="float32")
    colors = np.asarray(
        [[int(color[index:index + 2], 16) for index in (1, 3, 5)] for _, color in stops],
        dtype="float32",
    )
    value = float(np.clip(value, values[0], values[-1]))
    return tuple(int(np.rint(np.interp(value, values, colors[:, channel]))) for channel in range(3))


def cog_tile_values(dataset: rasterio.io.DatasetReader, tile: mercantile.Tile) -> tuple[np.ndarray, np.ndarray]:
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
    raw = raw[RENDER_BUFFER:RENDER_BUFFER + TILE_SIZE, RENDER_BUFFER:RENDER_BUFFER + TILE_SIZE]
    valid = np.isfinite(raw) & (raw != dataset.nodata)
    return raw * dataset.scales[0] + dataset.offsets[0], valid


def tile_pixel(longitude: float, latitude: float, tile: mercantile.Tile) -> tuple[int, int]:
    point_x, point_y = mercantile.xy(longitude, latitude)
    bounds = mercantile.xy_bounds(tile)
    x = int((point_x - bounds.left) / (bounds.right - bounds.left) * TILE_SIZE)
    y = int((bounds.top - point_y) / (bounds.top - bounds.bottom) * TILE_SIZE)
    return min(TILE_SIZE - 1, max(0, x)), min(TILE_SIZE - 1, max(0, y))


def run(max_channel_error: int) -> list[dict]:
    layers, layer_palettes = palettes()
    rows: list[dict] = []
    for case in CASES:
        zoom = layers[case.layer]["native_max_zoom"]
        tile = mercantile.tile(case.longitude, case.latitude, zoom)
        pmtiles_path = PMTILES_ROOT / case.layer / f"{case.month:02d}.pmtiles"
        cog_path = COG_ROOT / case.layer / f"{case.month:02d}.tif"
        with pmtiles_path.open("rb") as stream:
            tile_bytes = Reader(MmapSource(stream)).get(tile.z, tile.x, tile.y)
        if tile_bytes is None:
            raise RuntimeError(f"Tuile absente : {pmtiles_path} {tile}")
        actual = np.asarray(Image.open(io.BytesIO(tile_bytes)).convert("RGBA"))
        with rasterio.open(cog_path) as dataset:
            values, valid = cog_tile_values(dataset, tile)
        center_x, center_y = tile_pixel(case.longitude, case.latitude, tile)
        for dy in (-1, 0, 1):
            for dx in (-1, 0, 1):
                x, y = center_x + dx, center_y + dy
                if not (0 <= x < TILE_SIZE and 0 <= y < TILE_SIZE) or not valid[y, x]:
                    continue
                expected_rgb = colorize(float(values[y, x]), layer_palettes[case.layer])
                actual_rgb = tuple(int(value) for value in actual[y, x, :3])
                errors = [abs(a - e) for a, e in zip(actual_rgb, expected_rgb)]
                rows.append({
                    "place": case.place,
                    "layer": case.layer,
                    "month": case.month,
                    "zoom": tile.z,
                    "tile_x": tile.x,
                    "tile_y": tile.y,
                    "pixel_x": x,
                    "pixel_y": y,
                    "offset_x": dx,
                    "offset_y": dy,
                    "cog_value": round(float(values[y, x]), 3),
                    "expected_rgb": ",".join(map(str, expected_rgb)),
                    "pmtiles_rgb": ",".join(map(str, actual_rgb)),
                    "max_channel_error": max(errors),
                    "mean_channel_error": round(sum(errors) / 3, 2),
                    "alpha": int(actual[y, x, 3]),
                    "status": "OK" if max(errors) <= max_channel_error and actual[y, x, 3] == 255 else "FAIL",
                })
    return rows


def write_results(rows: list[dict], max_channel_error: int) -> None:
    CSV_PATH.parent.mkdir(parents=True, exist_ok=True)
    with CSV_PATH.open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]), lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
    groups: list[str] = []
    for case in CASES:
        selected = [row for row in rows if row["place"] == case.place and row["layer"] == case.layer]
        worst = max(row["max_channel_error"] for row in selected)
        mean = sum(row["mean_channel_error"] for row in selected) / len(selected)
        status = "OK" if all(row["status"] == "OK" for row in selected) else "ÉCHEC"
        center = min(selected, key=lambda row: abs(row["offset_x"]) + abs(row["offset_y"]))
        groups.append(
            f"| {case.place} | {case.layer} | {case.month:02d} | {center['cog_value']} | "
            f"{center['expected_rgb']} | {center['pmtiles_rgb']} | {worst} | {mean:.2f} | {status} |"
        )
    failed = sum(row["status"] == "FAIL" for row in rows)
    REPORT_PATH.write_text(
        "# Comparaison PMTiles / COG\n\n"
        "Contrôle déterministe de blocs 3 × 3 pixels autour de six lieux. La valeur COG est "
        "ré-échantillonnée exactement comme lors de la génération des tuiles, puis convertie avec "
        "la palette du contrat. Une petite différence RGB est normale à cause de la compression WebP avec pertes.\n\n"
        f"Résultat : **{len(rows) - failed}/{len(rows)} pixels conformes**, tolérance maximale "
        f"de {max_channel_error} niveaux par canal.\n\n"
        "| Lieu | Couche | Mois | Valeur COG centrale | RGB attendu | RGB PMTiles | Écart max | Écart moyen | Statut |\n"
        "|---|---:|---:|---:|---|---|---:|---:|---|\n"
        + "\n".join(groups)
        + "\n\nLe détail pixel par pixel est dans `outputs/comparaison-pixels-pmtiles-cog.csv`.\n"
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--max-channel-error", type=int, default=12)
    args = parser.parse_args()
    rows = run(args.max_channel_error)
    write_results(rows, args.max_channel_error)
    failures = [row for row in rows if row["status"] == "FAIL"]
    print(f"{len(rows) - len(failures)}/{len(rows)} pixels conformes; rapport: {REPORT_PATH}")
    if failures:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
