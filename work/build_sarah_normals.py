#!/usr/bin/env python3
"""Build 1991-2020 monthly sunshine normals from SARAH-3 NetCDF files."""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import rasterio
from netCDF4 import Dataset, num2date
from rasterio.shutil import copy as raster_copy
from rasterio.transform import from_origin


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_INPUT = ROOT / "work/downloads/sarah3-monthly"
DEFAULT_OUTPUT = ROOT / "work/derived/1991-2020"
DEFAULT_BOUNDS = (-25.0, 25.0, 45.0, 65.0)
YEARS = tuple(range(1991, 2021))
NODATA = 65535
SCALE = 0.1


@dataclass(frozen=True)
class Record:
    path: Path
    time_index: int
    year: int
    month: int


def parse_bounds(value: str) -> tuple[float, float, float, float]:
    try:
        west, south, east, north = (float(item) for item in value.split(","))
    except ValueError as error:
        raise argparse.ArgumentTypeError("Format attendu : ouest,sud,est,nord") from error
    if not (-180 <= west < east <= 180 and -90 <= south < north <= 90):
        raise argparse.ArgumentTypeError("Emprise géographique invalide")
    return west, south, east, north


def find_coordinate(dataset: Dataset, standard_name: str, common_names: tuple[str, ...]):
    for name in common_names:
        if name in dataset.variables:
            return dataset[name]
    for variable in dataset.variables.values():
        if getattr(variable, "standard_name", "").lower() == standard_name:
            return variable
    raise RuntimeError(f"Coordonnée {standard_name} introuvable dans {dataset.filepath()}")


def find_sdu(dataset: Dataset):
    for name in ("SDU", "sdu"):
        if name in dataset.variables:
            return dataset[name]
    for variable in dataset.variables.values():
        description = " ".join(
            str(getattr(variable, attribute, ""))
            for attribute in ("standard_name", "long_name")
        ).lower()
        if "sunshine" in description and "duration" in description:
            return variable
    raise RuntimeError(f"Variable SDU introuvable dans {dataset.filepath()}")


def find_time(dataset: Dataset):
    return find_coordinate(dataset, "time", ("time", "valid_time"))


def discover(input_root: Path) -> list[Record]:
    paths = sorted({*input_root.rglob("*.nc"), *input_root.rglob("*.nc4")})
    if not paths:
        raise FileNotFoundError(f"Aucun fichier NetCDF trouvé sous {input_root}")
    records: list[Record] = []
    for path in paths:
        with Dataset(path) as dataset:
            find_sdu(dataset)
            time = find_time(dataset)
            dates = num2date(
                time[:], time.units, getattr(time, "calendar", "standard"),
                only_use_cftime_datetimes=False,
            )
            for index, date in enumerate(np.atleast_1d(dates)):
                if date.year in YEARS:
                    records.append(Record(path, index, date.year, date.month))
    return records


def validate_inventory(records: list[Record]) -> dict[int, list[Record]]:
    by_month: dict[int, list[Record]] = defaultdict(list)
    seen: dict[tuple[int, int], Record] = {}
    for record in records:
        key = (record.year, record.month)
        if key in seen:
            raise RuntimeError(
                f"Doublon {record.year}-{record.month:02d} : {seen[key].path} et {record.path}"
            )
        seen[key] = record
        by_month[record.month].append(record)
    missing = [
        f"{year}-{month:02d}"
        for year in YEARS for month in range(1, 13)
        if (year, month) not in seen
    ]
    if missing:
        preview = ", ".join(missing[:6])
        raise RuntimeError(f"{len(missing)} mois source manquants, premiers : {preview}")
    for month in by_month:
        by_month[month].sort(key=lambda record: record.year)
    return by_month


def coordinate_indices(values: np.ndarray, low: float, high: float) -> np.ndarray:
    indices = np.flatnonzero((values >= low - 1e-8) & (values <= high + 1e-8))
    if indices.size == 0:
        raise RuntimeError(f"L'emprise demandée [{low}, {high}] ne rencontre pas la grille")
    if not np.array_equal(indices, np.arange(indices[0], indices[-1] + 1)):
        raise RuntimeError("La sélection de coordonnées n'est pas contiguë")
    return indices


def unit_factor(unit: str) -> float:
    normalized = unit.strip().lower()
    if normalized in {"h", "hr", "hour", "hours"}:
        return 1.0
    if normalized in {"s", "sec", "second", "seconds"}:
        return 1.0 / 3600.0
    if normalized in {"min", "minute", "minutes"}:
        return 1.0 / 60.0
    raise RuntimeError(f"Unité SDU non reconnue : {unit!r}")


def read_slice(record: Record, bounds: tuple[float, float, float, float]):
    west, south, east, north = bounds
    with Dataset(record.path) as dataset:
        latitude = np.asarray(find_coordinate(dataset, "latitude", ("lat", "latitude"))[:])
        longitude = np.asarray(find_coordinate(dataset, "longitude", ("lon", "longitude"))[:])
        lat_indices = coordinate_indices(latitude, south, north)
        lon_indices = coordinate_indices(longitude, west, east)
        variable = find_sdu(dataset)
        dimensions = tuple(variable.dimensions)
        time_coordinate = find_time(dataset)
        latitude_coordinate = find_coordinate(dataset, "latitude", ("lat", "latitude"))
        longitude_coordinate = find_coordinate(dataset, "longitude", ("lon", "longitude"))
        time_name = time_coordinate.dimensions[0]
        lat_name = latitude_coordinate.dimensions[0]
        lon_name = longitude_coordinate.dimensions[0]
        selection = []
        for dimension in dimensions:
            if dimension == time_name:
                selection.append(record.time_index)
            elif dimension == lat_name:
                selection.append(slice(int(lat_indices[0]), int(lat_indices[-1]) + 1))
            elif dimension == lon_name:
                selection.append(slice(int(lon_indices[0]), int(lon_indices[-1]) + 1))
            else:
                raise RuntimeError(f"Dimension SDU inattendue {dimension!r} dans {record.path}")
        raw = np.ma.asarray(variable[tuple(selection)], dtype="float64")
        remaining = [dimension for dimension in dimensions if dimension != time_name]
        if remaining == [lon_name, lat_name]:
            raw = raw.T
        elif remaining != [lat_name, lon_name]:
            raise RuntimeError(f"Ordre des dimensions SDU inattendu dans {record.path}")
        values = np.ma.filled(raw, np.nan) * unit_factor(getattr(variable, "units", ""))
    selected_latitude = latitude[lat_indices]
    selected_longitude = longitude[lon_indices]
    if selected_latitude[0] < selected_latitude[-1]:
        selected_latitude = selected_latitude[::-1]
        values = values[::-1, :]
    if selected_longitude[0] > selected_longitude[-1]:
        selected_longitude = selected_longitude[::-1]
        values = values[:, ::-1]
    return selected_latitude, selected_longitude, values


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(4 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def completed(
    path: Path, bounds: tuple[float, float, float, float], minimum_valid_years: int
) -> bool:
    sidecar = path.with_suffix(".tif.json")
    if not path.exists() or not sidecar.exists():
        return False
    try:
        metadata = json.loads(sidecar.read_text())
        with rasterio.open(path) as dataset:
            overview_valid = bool(dataset.overviews(1)) or max(dataset.width, dataset.height) <= 256
            return (
                metadata.get("years") == list(YEARS)
                and metadata.get("bounds_requested") == list(bounds)
                and metadata.get("minimum_valid_years") == minimum_valid_years
                and metadata.get("bytes") == path.stat().st_size
                and dataset.scales == (SCALE,)
                and overview_valid
            )
    except (OSError, ValueError, json.JSONDecodeError, rasterio.errors.RasterioError):
        return False


def build_month(
    records: list[Record], output_root: Path, month: int,
    bounds: tuple[float, float, float, float], minimum_valid_years: int,
) -> dict:
    output = output_root / "sunshine" / f"{month:02d}.tif"
    output.parent.mkdir(parents=True, exist_ok=True)
    building = output.with_suffix(".building.tif")
    working = output.with_suffix(".working.tif")
    for temporary in (building, working):
        temporary.unlink(missing_ok=True)

    latitude = longitude = total = count = None
    for index, record in enumerate(records, start=1):
        current_latitude, current_longitude, values = read_slice(record, bounds)
        if latitude is None:
            latitude, longitude = current_latitude, current_longitude
            total = np.zeros(values.shape, dtype="float64")
            count = np.zeros(values.shape, dtype="uint8")
        elif not (
            np.array_equal(latitude, current_latitude)
            and np.array_equal(longitude, current_longitude)
            and total.shape == values.shape
        ):
            raise RuntimeError(f"Grille incompatible : {record.path}")
        valid = np.isfinite(values)
        total[valid] += values[valid]
        count[valid] += 1
        print(f"  {month:02d} : {index:02d}/{len(records)} ({record.year})", flush=True)

    assert latitude is not None and longitude is not None and total is not None and count is not None
    normal = np.full(total.shape, np.nan, dtype="float64")
    accepted = count >= minimum_valid_years
    normal[accepted] = total[accepted] / count[accepted]
    if accepted.any() and (np.nanmin(normal) < 0 or np.nanmax(normal) > 744):
        raise RuntimeError(f"Valeurs physiques invraisemblables pour le mois {month:02d}")
    encoded = np.full(total.shape, NODATA, dtype="uint16")
    encoded[accepted] = np.floor(normal[accepted] / SCALE + 0.5).astype("uint16")
    resolution_lon = float(np.median(np.diff(longitude)))
    resolution_lat = abs(float(np.median(np.diff(latitude))))
    transform = from_origin(
        float(longitude[0] - resolution_lon / 2),
        float(latitude[0] + resolution_lat / 2),
        resolution_lon, resolution_lat,
    )
    profile = {
        "driver": "GTiff", "width": encoded.shape[1], "height": encoded.shape[0],
        "count": 1, "dtype": "uint16", "crs": "EPSG:4326", "transform": transform,
        "nodata": NODATA, "tiled": True, "blockxsize": 256, "blockysize": 256,
        "compress": "DEFLATE", "predictor": 2, "BIGTIFF": "IF_SAFER",
    }
    with rasterio.open(working, "w", **profile) as dataset:
        dataset.write(encoded, 1)
        dataset.scales = (SCALE,)
        dataset.offsets = (0.0,)
        dataset.units = ("hours/month",)
        dataset.update_tags(
            source="CM SAF SARAH-3 SDU monthly sum", source_variable="SDU",
            reference_period="1991-2020", month=f"{month:02d}",
            minimum_valid_years=str(minimum_valid_years), water_mask_applied="false",
        )
    with rasterio.open(working) as source:
        raster_copy(
            source, building, driver="COG", BLOCKSIZE=256, COMPRESS="DEFLATE",
            PREDICTOR="YES", OVERVIEWS="AUTO", RESAMPLING="AVERAGE",
        )
    working.unlink()
    building.replace(output)
    valid_values = normal[accepted]
    metadata = {
        "layer_id": "sunshine", "month": month, "years": list(YEARS),
        "source_count": len(records), "minimum_valid_years": minimum_valid_years,
        "valid_pixels": int(accepted.sum()), "minimum_hours": round(float(valid_values.min()), 4),
        "maximum_hours": round(float(valid_values.max()), 4), "unit": "hours/month",
        "scale_factor": SCALE, "bounds_requested": list(bounds), "water_mask_applied": False,
        "bytes": output.stat().st_size, "sha256": sha256(output),
        "completed_at": datetime.now(timezone.utc).isoformat(),
    }
    output.with_suffix(".tif.json").write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2) + "\n"
    )
    return metadata


def main() -> int:
    parser = argparse.ArgumentParser(description="Calcule les normales mensuelles SARAH-3 SDU.")
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--bounds", type=parse_bounds, default=DEFAULT_BOUNDS)
    parser.add_argument("--minimum-valid-years", type=int, default=30, choices=range(1, 31))
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    records = discover(args.input)
    by_month = validate_inventory(records)
    print(f"SARAH-3 : {len(records)} mois trouvés, inventaire 1991-2020 complet.")
    if args.dry_run:
        return 0
    for month in range(1, 13):
        output = args.output / "sunshine" / f"{month:02d}.tif"
        if completed(output, args.bounds, args.minimum_valid_years):
            print(f"[{month:02d}/12] déjà terminé")
            continue
        metadata = build_month(
            by_month[month], args.output, month, args.bounds, args.minimum_valid_years
        )
        print(
            f"[{month:02d}/12] terminé : {metadata['minimum_hours']} à "
            f"{metadata['maximum_hours']} h/mois"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
