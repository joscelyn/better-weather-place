#!/usr/bin/env python3
"""Apply aligned WBM land-fraction masks to monthly climate COGs."""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import rasterio
from rasterio.shutil import copy as raster_copy


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_INPUT = ROOT / "work/derived/1991-2020"
DEFAULT_MASKS = DEFAULT_INPUT / "masks"
DEFAULT_OUTPUT = ROOT / "work/derived/1991-2020-masked"
LAYERS = ("tavg", "tmax", "tmin", "precipitation", "sunshine")
MASK_NAMES = {
    "tavg": "chelsa", "tmax": "chelsa", "tmin": "chelsa",
    "precipitation": "chelsa", "sunshine": "sarah", "rainy_days": "cerra",
}
COASTAL_WARNING_THRESHOLD = 0.80


def parse_list(value: str, allowed: set[str]) -> list[str]:
    values = [item.strip() for item in value.split(",") if item.strip()]
    unknown = sorted(set(values).difference(allowed))
    if not values or unknown:
        raise argparse.ArgumentTypeError(f"Valeurs inconnues : {', '.join(unknown)}")
    return values


def parse_months(value: str) -> list[int]:
    result: set[int] = set()
    for item in value.split(","):
        if ":" in item:
            start, end = item.split(":", 1)
            result.update(range(int(start), int(end) + 1))
        else:
            result.add(int(item))
    if not result or min(result) < 1 or max(result) > 12:
        raise argparse.ArgumentTypeError("Mois attendus entre 1 et 12")
    return sorted(result)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(4 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def output_paths(root: Path, layer: str, month: int) -> tuple[Path, Path, Path, Path]:
    final = root / layer / f"{month:02d}.tif"
    return final, final.with_suffix(".tif.json"), final.with_suffix(".working.tif"), final.with_suffix(".building.tif")


def is_complete(
    output_root: Path, layer: str, month: int, source_sha256: str, mask_sha256: str,
) -> bool:
    final, sidecar, _, _ = output_paths(output_root, layer, month)
    if not final.exists() or not sidecar.exists():
        return False
    try:
        metadata = json.loads(sidecar.read_text())
        return (
            metadata.get("water_mask_applied") is True
            and metadata.get("source_sha256") == source_sha256
            and metadata.get("land_fraction_sha256") == mask_sha256
            and metadata.get("bytes") == final.stat().st_size
        )
    except (OSError, ValueError, json.JSONDecodeError):
        return False


def build_one(
    source_path: Path, mask_path: Path, output_root: Path, layer: str, month: int,
) -> dict:
    source_sidecar = json.loads(source_path.with_suffix(".tif.json").read_text())
    mask_sidecar = json.loads(mask_path.with_suffix(".tif.json").read_text())
    source_hash = source_sidecar["sha256"]
    mask_hash = mask_sidecar["sha256"]
    final, sidecar, working, building = output_paths(output_root, layer, month)
    if is_complete(output_root, layer, month, source_hash, mask_hash):
        return json.loads(sidecar.read_text())

    final.parent.mkdir(parents=True, exist_ok=True)
    working.unlink(missing_ok=True)
    building.unlink(missing_ok=True)
    minimum = np.inf
    maximum = -np.inf
    valid_pixels = 0
    mixed_pixels = 0
    with rasterio.open(source_path) as source, rasterio.open(mask_path) as mask:
        if (
            source.shape != mask.shape or source.crs != mask.crs
            or not np.allclose(tuple(source.transform), tuple(mask.transform), rtol=0, atol=1e-10)
        ):
            raise RuntimeError(f"Masque non aligné pour {source_path}")
        profile = source.profile.copy()
        profile.update(
            driver="GTiff", tiled=True, blockxsize=256, blockysize=256,
            compress="DEFLATE", predictor=2, BIGTIFF="IF_SAFER",
        )
        with rasterio.open(working, "w", **profile) as target:
            target.scales = source.scales
            target.offsets = source.offsets
            target.units = source.units
            target.update_tags(**source.tags())
            target.update_tags(
                water_mask_applied="true",
                water_mask_source="Copernicus DEM GLO-30 WBM",
                land_fraction_mask=mask_path.relative_to(ROOT).as_posix(),
                retained_cell_rule="land fraction > 0",
                coastal_warning_threshold=str(COASTAL_WARNING_THRESHOLD),
            )
            for _, window in source.block_windows(1):
                raw = source.read(1, window=window)
                fraction = mask.read(1, window=window)
                source_valid = raw != source.nodata
                mask_valid = fraction != mask.nodata
                keep = source_valid & mask_valid & (fraction > 0)
                raw[~keep] = source.nodata
                target.write(raw, 1, window=window)
                if keep.any():
                    values = raw[keep].astype("float64") * source.scales[0] + source.offsets[0]
                    minimum = min(minimum, float(values.min()))
                    maximum = max(maximum, float(values.max()))
                    valid_pixels += int(keep.sum())
                    mixed_pixels += int(
                        (fraction[keep] < round(COASTAL_WARNING_THRESHOLD / mask.scales[0])).sum()
                    )

    with rasterio.open(working) as source:
        raster_copy(
            source, building, driver="COG", BLOCKSIZE=256, COMPRESS="DEFLATE",
            PREDICTOR="YES", OVERVIEWS="AUTO", RESAMPLING="AVERAGE",
        )
    working.unlink()
    building.replace(final)
    with rasterio.open(final) as check:
        if check.tags(ns="IMAGE_STRUCTURE").get("LAYOUT") != "COG" or not check.overviews(1):
            raise RuntimeError(f"Contrôle COG échoué : {final}")

    metadata = {
        "layer_id": layer,
        "month": month,
        "years": source_sidecar.get("years"),
        "unit": source_sidecar.get("unit"),
        "scale_factor": source_sidecar.get("scale_factor"),
        "water_mask_applied": True,
        "retained_cell_rule": "land fraction > 0",
        "coastal_warning_threshold": COASTAL_WARNING_THRESHOLD,
        "valid_pixels": valid_pixels,
        "coastal_warning_pixels": mixed_pixels,
        "minimum": round(minimum, 4),
        "maximum": round(maximum, 4),
        "source_cog": source_path.relative_to(ROOT).as_posix(),
        "source_sha256": source_hash,
        "land_fraction_cog": mask_path.relative_to(ROOT).as_posix(),
        "land_fraction_sha256": mask_hash,
        "bytes": final.stat().st_size,
        "sha256": sha256(final),
        "completed_at": datetime.now(timezone.utc).isoformat(),
    }
    sidecar.write_text(json.dumps(metadata, ensure_ascii=False, indent=2) + "\n")
    return metadata


def main() -> int:
    parser = argparse.ArgumentParser(description="Applique le masque WBM aux COG climatiques.")
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--masks", type=Path, default=DEFAULT_MASKS)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--layers", type=lambda value: parse_list(value, set(MASK_NAMES)), default=list(LAYERS))
    parser.add_argument("--months", type=parse_months, default=list(range(1, 13)))
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    jobs = [(layer, month) for layer in args.layers for month in args.months]
    missing = [
        args.input / layer / f"{month:02d}.tif"
        for layer, month in jobs
        if not (args.input / layer / f"{month:02d}.tif").exists()
    ]
    if missing:
        raise FileNotFoundError(f"{len(missing)} COG source(s) absent(s), premier : {missing[0]}")
    print(f"Masquage WBM : {len(jobs)} COG à contrôler ou produire")
    if args.dry_run:
        return 0

    for index, (layer, month) in enumerate(jobs, start=1):
        source = args.input / layer / f"{month:02d}.tif"
        mask = args.masks / f"{MASK_NAMES[layer]}-land-fraction.tif"
        metadata = build_one(source, mask, args.output, layer, month)
        print(
            f"[{index}/{len(jobs)}] {layer}/{month:02d} : "
            f"{metadata['valid_pixels']} cellules terrestres",
            flush=True,
        )
    print("COG climatiques masqués terminés.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
