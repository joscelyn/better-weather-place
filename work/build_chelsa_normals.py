#!/usr/bin/env python3
"""Build monthly CHELSA climatological normals from downloaded yearly clips."""

from __future__ import annotations

import argparse
import hashlib
import json
from contextlib import ExitStack
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import rasterio
from rasterio.shutil import copy as raster_copy


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_INPUT = ROOT / "work/downloads/chelsa-europe-mediterranee"
DEFAULT_OUTPUT = ROOT / "work/derived/1991-2020"
VARIABLES = ("tas", "tasmax", "tasmin", "pr")
LAYER_IDS = {"tas": "tavg", "tasmax": "tmax", "tasmin": "tmin", "pr": "precipitation"}
TEMPERATURES = {"tas", "tasmax", "tasmin"}


@dataclass(frozen=True)
class Job:
    variable: str
    month: int

    @property
    def layer_id(self) -> str:
        return LAYER_IDS[self.variable]


def parse_range(value: str, minimum: int, maximum: int) -> list[int]:
    values: set[int] = set()
    for part in value.split(","):
        part = part.strip()
        if not part:
            continue
        if ":" in part:
            start_text, end_text = part.split(":", 1)
            values.update(range(int(start_text), int(end_text) + 1))
        else:
            values.add(int(part))
    if not values or min(values) < minimum or max(values) > maximum:
        raise argparse.ArgumentTypeError(f"Valeurs attendues entre {minimum} et {maximum}")
    return sorted(values)


def half_away_from_zero(values: np.ndarray) -> np.ndarray:
    return np.where(values >= 0, np.floor(values + 0.5), np.ceil(values - 0.5))


def input_paths(root: Path, job: Job, years: list[int]) -> list[Path]:
    return [root / job.variable / str(year) / f"{job.month:02d}.tif" for year in years]


def output_paths(root: Path, job: Job) -> tuple[Path, Path, Path, Path]:
    final = root / job.layer_id / f"{job.month:02d}.tif"
    return (
        final,
        final.with_suffix(".tif.json"),
        final.with_suffix(".working.tif"),
        final.with_suffix(".building.tif"),
    )


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(4 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def validate_sources(sources: list[rasterio.DatasetReader], paths: list[Path]) -> None:
    reference = sources[0]
    for source, path in zip(sources[1:], paths[1:]):
        if (
            source.width != reference.width
            or source.height != reference.height
            or source.transform != reference.transform
            or source.crs != reference.crs
        ):
            raise RuntimeError(f"Grille incompatible : {path}")


def decode(raw: np.ndarray, source: rasterio.DatasetReader, variable: str) -> np.ndarray:
    values = raw.astype("float64") * source.scales[0] + source.offsets[0]
    if variable in TEMPERATURES:
        values -= 273.15
    return values


def encode(values: np.ndarray, variable: str) -> tuple[np.ndarray, str, int, float]:
    scaled = half_away_from_zero(values * 10)
    if variable in TEMPERATURES:
        nodata, dtype = -32768, "int16"
    else:
        nodata, dtype = 65535, "uint16"
    info = np.iinfo(dtype)
    valid_min = info.min + (1 if dtype == "int16" else 0)
    valid_max = info.max - (1 if dtype == "uint16" else 0)
    if np.any((scaled < valid_min) | (scaled > valid_max)):
        raise RuntimeError(f"Valeur hors capacité {dtype}")
    return scaled.astype(dtype), dtype, nodata, 0.1


def is_completed(output: Path, job: Job, years: list[int]) -> bool:
    final, sidecar, _, _ = output_paths(output, job)
    if not final.exists() or not sidecar.exists() or final.stat().st_size == 0:
        return False
    try:
        metadata = json.loads(sidecar.read_text())
        if metadata.get("years") != years or metadata.get("variable") != job.variable:
            return False
        if metadata.get("bytes") != final.stat().st_size:
            return False
        with rasterio.open(final) as dataset:
            return dataset.driver == "GTiff" and dataset.count == 1 and bool(dataset.overviews(1))
    except (OSError, ValueError, json.JSONDecodeError, rasterio.errors.RasterioError):
        return False


def build_normal(input_root: Path, output_root: Path, job: Job, years: list[int]) -> dict:
    paths = input_paths(input_root, job, years)
    missing = [str(path) for path in paths if not path.exists()]
    if missing:
        raise FileNotFoundError(f"{len(missing)} source(s) manquante(s), première : {missing[0]}")

    final, sidecar, working, building = output_paths(output_root, job)
    final.parent.mkdir(parents=True, exist_ok=True)
    for temporary in (working, building):
        if temporary.exists():
            temporary.unlink()

    minimum = np.inf
    maximum = -np.inf
    valid_pixels = 0
    with ExitStack() as stack:
        sources = [stack.enter_context(rasterio.open(path)) for path in paths]
        validate_sources(sources, paths)
        reference = sources[0]
        sample, dtype, nodata, scale = encode(np.array([0.0]), job.variable)
        del sample
        profile = reference.profile.copy()
        profile.update(
            driver="GTiff",
            dtype=dtype,
            nodata=nodata,
            count=1,
            tiled=True,
            blockxsize=256,
            blockysize=256,
            compress="DEFLATE",
            predictor=2,
            BIGTIFF="IF_SAFER",
        )
        with rasterio.open(working, "w", **profile) as target:
            target.scales = (scale,)
            target.offsets = (0.0,)
            target.units = ("°C" if job.variable in TEMPERATURES else "mm/month",)
            target.update_tags(
                source="CHELSA-monthly V2.1",
                source_variable=job.variable,
                reference_period=f"{years[0]}-{years[-1]}",
                month=f"{job.month:02d}",
                water_mask_applied="false",
            )
            for _, window in target.block_windows(1):
                total = np.zeros((window.height, window.width), dtype="float64")
                count = np.zeros((window.height, window.width), dtype="uint8")
                for source in sources:
                    raw = source.read(1, window=window)
                    valid = raw != source.nodata
                    values = decode(raw, source, job.variable)
                    total[valid] += values[valid]
                    count[valid] += 1
                complete = count == len(sources)
                physical = np.zeros(total.shape, dtype="float64")
                physical[complete] = total[complete] / count[complete]
                encoded, _, _, _ = encode(physical, job.variable)
                encoded[~complete] = nodata
                target.write(encoded, 1, window=window)
                if complete.any():
                    block_values = physical[complete]
                    minimum = min(minimum, float(block_values.min()))
                    maximum = max(maximum, float(block_values.max()))
                    valid_pixels += int(complete.sum())

    with rasterio.open(working) as source:
        raster_copy(
            source,
            building,
            driver="COG",
            BLOCKSIZE=256,
            COMPRESS="DEFLATE",
            PREDICTOR="YES",
            OVERVIEWS="AUTO",
            RESAMPLING="AVERAGE",
        )
    working.unlink()
    building.replace(final)

    with rasterio.open(final) as check:
        if check.scales != (0.1,) or not check.overviews(1):
            raise RuntimeError(f"Contrôle COG échoué : {final}")
    metadata = {
        "layer_id": job.layer_id,
        "variable": job.variable,
        "month": job.month,
        "years": years,
        "source_count": len(paths),
        "valid_pixels": valid_pixels,
        "minimum": round(minimum, 4),
        "maximum": round(maximum, 4),
        "unit": "°C" if job.variable in TEMPERATURES else "mm/month",
        "scale_factor": 0.1,
        "water_mask_applied": False,
        "bytes": final.stat().st_size,
        "sha256": sha256(final),
        "completed_at": datetime.now(timezone.utc).isoformat(),
    }
    sidecar.write_text(json.dumps(metadata, ensure_ascii=False, indent=2) + "\n")
    return metadata


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Calcule les normales mensuelles CHELSA.")
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--variables", default=",".join(VARIABLES))
    parser.add_argument("--years", default="1991:2020")
    parser.add_argument("--months", default="1:12")
    parser.add_argument("--strict", action="store_true", help="Échoue si un job n'a pas ses sources complètes.")
    parser.add_argument("--dry-run", action="store_true")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    variables = [item.strip() for item in args.variables.split(",") if item.strip()]
    unknown = sorted(set(variables).difference(VARIABLES))
    if unknown:
        raise SystemExit(f"Variables inconnues : {', '.join(unknown)}")
    years = parse_range(args.years, 1991, 2020)
    months = parse_range(args.months, 1, 12)
    jobs = [Job(variable, month) for variable in variables for month in months]
    ready: list[Job] = []
    incomplete: list[tuple[Job, int]] = []
    completed: list[Job] = []
    for job in jobs:
        if is_completed(args.output, job, years):
            completed.append(job)
            continue
        missing_count = sum(not path.exists() for path in input_paths(args.input, job, years))
        if missing_count:
            incomplete.append((job, missing_count))
        else:
            ready.append(job)
    print(
        f"Normales CHELSA : {len(jobs)} jobs, {len(completed)} terminés, "
        f"{len(ready)} prêts, {len(incomplete)} incomplets"
    )
    if incomplete:
        preview = ", ".join(f"{job.variable}-{job.month:02d} ({count} abs.)" for job, count in incomplete[:8])
        print(f"Sources manquantes : {preview}{'…' if len(incomplete) > 8 else ''}")
    if args.dry_run:
        return 2 if args.strict and incomplete else 0

    for index, job in enumerate(ready, start=1):
        print(f"[{index}/{len(ready)}] {job.variable}-{job.month:02d}", flush=True)
        metadata = build_normal(args.input, args.output, job, years)
        print(
            f"  OK {metadata['minimum']:.2f} à {metadata['maximum']:.2f} {metadata['unit']}, "
            f"{metadata['bytes'] / 1024**2:.1f} Mio",
            flush=True,
        )
    return 2 if args.strict and incomplete else 0


if __name__ == "__main__":
    raise SystemExit(main())
