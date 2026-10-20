#!/usr/bin/env python3
"""Audit completed monthly production grids on a Natural Earth land mask."""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

import numpy as np
import rasterio
from rasterio.features import rasterize


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_INPUT = ROOT / "work/derived/1991-2020"
DEFAULT_LAND = ROOT / "work/downloads/reference/ne_10m_land.geojson"
DEFAULT_OUTPUT = ROOT / "outputs/audit-grilles-production.csv"
LAYERS = {
    "tavg": {"unit": "degC", "palette_minimum": -40.0, "palette_maximum": 50.0},
    "tmax": {"unit": "degC", "palette_minimum": -40.0, "palette_maximum": 50.0},
    "tmin": {"unit": "degC", "palette_minimum": -40.0, "palette_maximum": 50.0},
    "precipitation": {"unit": "mm/month", "palette_minimum": 0.0, "palette_maximum": 400.0},
    "sunshine": {"unit": "h/month", "palette_minimum": 0.0, "palette_maximum": 400.0},
}
PERCENTILES = (1, 10, 50, 90, 99, 99.9)


def parse_layers(value: str) -> list[str]:
    layers = [item.strip() for item in value.split(",") if item.strip()]
    unknown = sorted(set(layers).difference(LAYERS))
    if not layers or unknown:
        raise argparse.ArgumentTypeError(
            "Couches attendues : " + ", ".join(sorted(LAYERS))
        )
    return layers


def load_land_geometries(path: Path) -> list[dict]:
    collection = json.loads(path.read_text())
    return [feature["geometry"] for feature in collection["features"]]


def land_mask(dataset: rasterio.DatasetReader, geometries: list[dict]) -> np.ndarray:
    return rasterize(
        ((geometry, 1) for geometry in geometries),
        out_shape=dataset.shape,
        transform=dataset.transform,
        fill=0,
        all_touched=False,
        dtype="uint8",
    ).astype(bool)


def audit_layer(input_root: Path, layer: str, geometries: list[dict] | None) -> list[dict]:
    paths = [input_root / layer / f"{month:02d}.tif" for month in range(1, 13)]
    missing = [path for path in paths if not path.exists()]
    if missing:
        raise FileNotFoundError(f"Grille manquante : {missing[0]}")

    rows: list[dict] = []
    mask: np.ndarray | None = None
    reference_grid: tuple | None = None
    palette_minimum = LAYERS[layer]["palette_minimum"]
    palette_maximum = LAYERS[layer]["palette_maximum"]
    for month, path in enumerate(paths, start=1):
        with rasterio.open(path) as dataset:
            grid = (dataset.shape, dataset.transform, dataset.crs)
            if mask is None:
                mask = (
                    land_mask(dataset, geometries)
                    if geometries is not None
                    else np.ones(dataset.shape, dtype=bool)
                )
                reference_grid = grid
            elif grid != reference_grid:
                raise RuntimeError(f"Grille incohérente dans {path}")

            raw = dataset.read(1)
            valid = mask & (raw != dataset.nodata)
            values = raw[valid].astype("float32") * dataset.scales[0] + dataset.offsets[0]
            maximum_index = int(np.argmax(np.where(valid, raw, 0)))
            maximum_row, maximum_column = np.unravel_index(maximum_index, raw.shape)
            maximum_longitude, maximum_latitude = dataset.xy(maximum_row, maximum_column)

        percentiles = np.percentile(values, PERCENTILES)
        below = values < palette_minimum
        above = values > palette_maximum
        row = {
            "layer": layer,
            "month": month,
            "unit": LAYERS[layer]["unit"],
            "land_pixel_count": values.size,
            "minimum": round(float(values.min()), 3),
            **{
                f"p{str(percentile).replace('.', '_')}": round(float(value), 3)
                for percentile, value in zip(PERCENTILES, percentiles)
            },
            "maximum": round(float(values.max()), 3),
            "maximum_longitude": round(float(maximum_longitude), 6),
            "maximum_latitude": round(float(maximum_latitude), 6),
            "palette_minimum": palette_minimum,
            "palette_maximum": palette_maximum,
            "below_palette_count": int(below.sum()),
            "below_palette_percent": round(100 * float(below.mean()), 8),
            "above_palette_count": int(above.sum()),
            "above_palette_percent": round(100 * float(above.mean()), 8),
        }
        rows.append(row)
        print(
            f"{layer} {month:02d}: {row['minimum']:.1f}–{row['maximum']:.1f}, "
            f"P99={row['p99']:.1f}, <{palette_minimum:g}={row['below_palette_percent']:.6f}%, "
            f">{palette_maximum:g}={row['above_palette_percent']:.6f}%",
            flush=True,
        )
    return rows


def main() -> int:
    parser = argparse.ArgumentParser(description="Audite les COG mensuels produits sur les terres.")
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--land", type=Path, default=DEFAULT_LAND)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--layers", type=parse_layers, default=list(LAYERS))
    parser.add_argument(
        "--valid-only", action="store_true",
        help="Utilise tous les pixels non-nodata, par exemple après application du WBM.",
    )
    args = parser.parse_args()

    geometries = None if args.valid_only else load_land_geometries(args.land)
    rows: list[dict] = []
    for layer in args.layers:
        rows.extend(audit_layer(args.input, layer, geometries))

    args.output.parent.mkdir(parents=True, exist_ok=True)
    temporary = args.output.with_suffix(args.output.suffix + ".part")
    with temporary.open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    temporary.replace(args.output)
    print(f"Audit écrit dans {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
