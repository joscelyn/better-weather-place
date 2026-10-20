#!/usr/bin/env python3
"""Validate and inventory completed monthly production COGs."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import rasterio


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_INPUT = ROOT / "work/derived/1991-2020"
DEFAULT_INVENTORY = ROOT / "outputs/inventaire-cogs-production.csv"
DEFAULT_SUMMARY = ROOT / "outputs/validation-cogs-production.json"
LAYERS = {
    "tavg": {"dtype": "int16", "nodata": -32768, "unit": "°C"},
    "tmax": {"dtype": "int16", "nodata": -32768, "unit": "°C"},
    "tmin": {"dtype": "int16", "nodata": -32768, "unit": "°C"},
    "precipitation": {"dtype": "uint16", "nodata": 65535, "unit": "mm/month"},
    "sunshine": {"dtype": "uint16", "nodata": 65535, "unit": "hours/month"},
}
YEARS = list(range(1991, 2021))


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(4 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def validate_one(path: Path, layer: str, month: int, verify_checksum: bool) -> dict:
    sidecar_path = path.with_suffix(".tif.json")
    if not path.exists() or not sidecar_path.exists():
        raise FileNotFoundError(f"COG ou métadonnées absents : {path}")
    sidecar = json.loads(sidecar_path.read_text())
    expected = LAYERS[layer]

    errors: list[str] = []
    if sidecar.get("layer_id") != layer:
        errors.append("layer_id")
    if sidecar.get("month") != month:
        errors.append("month")
    if sidecar.get("years") != YEARS:
        errors.append("years")
    if sidecar.get("bytes") != path.stat().st_size:
        errors.append("bytes")

    actual_sha256 = sha256(path) if verify_checksum else sidecar.get("sha256")
    if actual_sha256 != sidecar.get("sha256"):
        errors.append("sha256")

    with rasterio.open(path) as dataset:
        image_structure = dataset.tags(ns="IMAGE_STRUCTURE")
        if dataset.driver != "GTiff" or image_structure.get("LAYOUT") != "COG":
            errors.append("layout")
        if dataset.count != 1:
            errors.append("band_count")
        if dataset.crs is None or dataset.crs.to_epsg() != 4326:
            errors.append("crs")
        if dataset.dtypes[0] != expected["dtype"]:
            errors.append("dtype")
        if dataset.nodata != expected["nodata"]:
            errors.append("nodata")
        if not np.isclose(dataset.scales[0], 0.1):
            errors.append("scale")
        if dataset.units[0] != expected["unit"]:
            errors.append("unit")
        if not dataset.is_tiled or not dataset.overviews(1):
            errors.append("tiling_or_overviews")

        row = {
            "layer": layer,
            "month": month,
            "path": path.relative_to(ROOT).as_posix(),
            "bytes": path.stat().st_size,
            "sha256": actual_sha256,
            "width": dataset.width,
            "height": dataset.height,
            "dtype": dataset.dtypes[0],
            "nodata": int(dataset.nodata),
            "scale_factor": dataset.scales[0],
            "unit": dataset.units[0],
            "overview_levels": ",".join(map(str, dataset.overviews(1))),
            "valid": not errors,
            "errors": ",".join(errors),
        }
    return row


def atomic_json(path: Path, value: dict) -> None:
    temporary = path.with_suffix(path.suffix + ".part")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n")
    temporary.replace(path)


def main() -> int:
    parser = argparse.ArgumentParser(description="Valide les COG mensuels de production.")
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--inventory", type=Path, default=DEFAULT_INVENTORY)
    parser.add_argument("--summary", type=Path, default=DEFAULT_SUMMARY)
    parser.add_argument("--skip-checksum", action="store_true")
    args = parser.parse_args()

    rows = [
        validate_one(args.input / layer / f"{month:02d}.tif", layer, month, not args.skip_checksum)
        for layer in LAYERS
        for month in range(1, 13)
    ]
    args.inventory.parent.mkdir(parents=True, exist_ok=True)
    temporary = args.inventory.with_suffix(args.inventory.suffix + ".part")
    with temporary.open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    temporary.replace(args.inventory)

    invalid = [row for row in rows if not row["valid"]]
    summary = {
        "status": "valid" if not invalid else "invalid",
        "reference_period": "1991-2020",
        "layers": list(LAYERS),
        "expected_files": len(LAYERS) * 12,
        "validated_files": len(rows) - len(invalid),
        "invalid_files": len(invalid),
        "total_bytes": sum(row["bytes"] for row in rows),
        "checksums_verified": not args.skip_checksum,
        "water_mask_applied": False,
        "validated_at": datetime.now(timezone.utc).isoformat(),
        "inventory": args.inventory.relative_to(ROOT).as_posix(),
    }
    atomic_json(args.summary, summary)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    if invalid:
        for row in invalid:
            print(f"INVALIDE {row['path']}: {row['errors']}")
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
