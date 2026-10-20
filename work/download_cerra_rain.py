#!/usr/bin/env python3
"""Resumable CERRA-Land daily precipitation downloader for land tiles.

The CDS time-series service limits area extracts to 0.5 x 0.5 degree. Jobs are
therefore split into independent land-intersecting tiles and downloaded in
parallel. Each archive contains daily precipitation for the complete 1991-2020
period and can be retried or resumed independently.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import random
import shutil
import tempfile
import time
import zipfile
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path

import cdsapi
import numpy as np
import requests
from netCDF4 import Dataset
from rasterio.features import rasterize
from rasterio.transform import from_bounds


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = ROOT / "work/downloads/cerra-land-daily-rain-1991-2020"
DEFAULT_BOUNDS = (-25.0, 25.0, 45.0, 72.0)  # west, south, east, north
LAND_URL = (
    "https://raw.githubusercontent.com/nvkelso/natural-earth-vector/"
    "master/geojson/ne_10m_land.geojson"
)
LAND_PATH = ROOT / "work/downloads/reference/ne_10m_land.geojson"
# Six attempts; the final value is unused because no wait follows the last failure.
RETRY_DELAYS_SECONDS = (5, 30, 120, 500, 1800, 3600)
EXPECTED_DAYS = 10_958
TILE_DEGREES = 0.5


@dataclass(frozen=True)
class Tile:
    west: float
    south: float
    east: float
    north: float

    @property
    def identifier(self) -> str:
        return f"n{self.north:+05.1f}_w{self.west:+06.1f}"

    @property
    def cds_area(self) -> list[float]:
        return [self.north, self.west, self.south, self.east]


def parse_bounds(value: str) -> tuple[float, float, float, float]:
    try:
        west, south, east, north = (float(item) for item in value.split(","))
    except ValueError as exc:
        raise argparse.ArgumentTypeError("Format attendu : ouest,sud,est,nord") from exc
    if not (-60 <= west < east <= 74.95 and 15 <= south < north <= 79.95):
        raise argparse.ArgumentTypeError("Emprise hors du domaine CERRA-Land")
    for coordinate in (west, south, east, north):
        if not np.isclose(coordinate * 2, round(coordinate * 2)):
            raise argparse.ArgumentTypeError("Les limites doivent être alignées sur 0,5 degré")
    return west, south, east, north


def download_land_reference(path: Path) -> None:
    if path.exists() and path.stat().st_size > 1_000_000:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".geojson.part")
    error: Exception | None = None
    for attempt, delay in enumerate(RETRY_DELAYS_SECONDS, start=1):
        try:
            with requests.get(LAND_URL, stream=True, timeout=60) as response:
                response.raise_for_status()
                with temporary.open("wb") as target:
                    for chunk in response.iter_content(1024 * 1024):
                        target.write(chunk)
            if temporary.stat().st_size < 1_000_000:
                raise RuntimeError("Référence terrestre Natural Earth incomplète")
            temporary.replace(path)
            return
        except Exception as exc:
            error = exc
            if temporary.exists():
                temporary.unlink()
            if attempt < len(RETRY_DELAYS_SECONDS):
                time.sleep(delay + random.uniform(0, min(5, delay / 4)))
    raise RuntimeError(f"Échec du téléchargement Natural Earth : {error}")


def is_canary_tile(tile: Tile) -> bool:
    """Keep the explicitly deferred Canary Islands out of this download."""
    return tile.west < -13 and tile.east > -19 and tile.south < 30 and tile.north > 27


def build_jobs(
    bounds: tuple[float, float, float, float], land_path: Path
) -> list[Tile]:
    west, south, east, north = bounds
    width = round((east - west) / TILE_DEGREES)
    height = round((north - south) / TILE_DEGREES)
    land = json.loads(land_path.read_text())
    mask = rasterize(
        ((feature["geometry"], 1) for feature in land["features"]),
        out_shape=(height, width),
        transform=from_bounds(west, south, east, north, width, height),
        all_touched=True,
        dtype="uint8",
    )
    jobs: list[Tile] = []
    # South first: the Mediterranean winter-sun area becomes usable earliest.
    for row in range(height - 1, -1, -1):
        tile_north = north - row * TILE_DEGREES
        tile_south = tile_north - TILE_DEGREES
        for column in range(width):
            if mask[row, column] == 0:
                continue
            tile_west = west + column * TILE_DEGREES
            tile = Tile(tile_west, tile_south, tile_west + TILE_DEGREES, tile_north)
            if not is_canary_tile(tile):
                jobs.append(tile)
    return jobs


def paths_for(output: Path, tile: Tile) -> tuple[Path, Path, Path]:
    directory = output / f"lat-{tile.south:+05.1f}"
    final = directory / f"{tile.identifier}.zip"
    return final, final.with_suffix(".zip.json"), final.with_suffix(".zip.part")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(4 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def inspect_archive(path: Path, full: bool) -> dict:
    if not zipfile.is_zipfile(path):
        raise RuntimeError("Réponse CDS invalide : archive ZIP attendue")
    with zipfile.ZipFile(path) as archive:
        members = [name for name in archive.namelist() if name.endswith(".nc")]
        if len(members) != 1:
            raise RuntimeError(f"Un NetCDF attendu, trouvé : {members}")
        if not full:
            return {"netcdf_member": members[0]}
        payload = archive.read(members[0])
    # The CDS currently packages a NetCDF-3 file. Opening it from netCDF4's
    # in-memory API emits a misleading HDF5 diagnostic, so validate a temporary
    # file instead.
    with tempfile.NamedTemporaryFile(suffix=".nc") as temporary:
        temporary.write(payload)
        temporary.flush()
        with Dataset(temporary.name) as dataset:
            if "tp" not in dataset.variables:
                raise RuntimeError("Variable tp absente du NetCDF")
            variable = dataset.variables["tp"]
            if variable.shape[0] != EXPECTED_DAYS:
                raise RuntimeError(f"{variable.shape[0]} jours reçus au lieu de {EXPECTED_DAYS}")
            return {
                "netcdf_member": members[0],
                "shape": list(variable.shape),
                "unit": getattr(variable, "units", None),
            }


def validate_completed(output: Path, tile: Tile) -> bool:
    final, sidecar, _ = paths_for(output, tile)
    if not final.exists() or not sidecar.exists() or final.stat().st_size == 0:
        return False
    try:
        metadata = json.loads(sidecar.read_text())
        if metadata.get("tile") != asdict(tile) or metadata.get("bytes") != final.stat().st_size:
            return False
        inspect_archive(final, full=False)
        return True
    except (OSError, ValueError, json.JSONDecodeError, zipfile.BadZipFile, RuntimeError):
        return False


def download_tile(output: Path, tile: Tile) -> dict:
    final, sidecar, temporary = paths_for(output, tile)
    final.parent.mkdir(parents=True, exist_ok=True)
    if temporary.exists():
        temporary.unlink()
    started = time.monotonic()
    client = cdsapi.Client(quiet=True, progress=False, wait_until_complete=True, delete=False)
    client.retrieve(
        "reanalysis-cerra-land-timeseries",
        {
            "variable": ["total_precipitation"],
            "area": tile.cds_area,
            "date": ["1991-01-01/2020-12-31"],
            "data_format": "netcdf",
        },
        str(temporary),
    )
    archive = inspect_archive(temporary, full=True)
    temporary.replace(final)
    metadata = {
        "tile": asdict(tile),
        "dataset": "reanalysis-cerra-land-timeseries",
        "variable": "total_precipitation",
        "period": "1991-01-01/2020-12-31",
        "bytes": final.stat().st_size,
        "sha256": sha256(final),
        "elapsed_seconds": round(time.monotonic() - started, 3),
        "completed_at": datetime.now(timezone.utc).isoformat(),
        **archive,
    }
    sidecar.write_text(json.dumps(metadata, ensure_ascii=False, indent=2) + "\n")
    return metadata


def append_event(output: Path, payload: dict) -> None:
    output.mkdir(parents=True, exist_ok=True)
    with (output / "download-events.jsonl").open("a") as stream:
        stream.write(json.dumps(payload, ensure_ascii=False) + "\n")


def disk_guard(output: Path, minimum_free_gb: float) -> None:
    output.mkdir(parents=True, exist_ok=True)
    free = shutil.disk_usage(output).free
    if free < int(minimum_free_gb * 1024**3):
        raise RuntimeError(
            f"Espace libre insuffisant : {free / 1024**3:.1f} Gio; "
            f"réserve demandée {minimum_free_gb:.1f} Gio."
        )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Télécharge la pluie quotidienne CERRA-Land par tuiles.")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--bounds", type=parse_bounds, default=DEFAULT_BOUNDS)
    parser.add_argument("--hours", type=float, default=10.0)
    parser.add_argument("--workers", type=int, default=8)
    parser.add_argument("--minimum-free-gb", type=float, default=15.0)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--verify-only", action="store_true")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    if args.workers < 1 or args.workers > 12:
        raise SystemExit("--workers doit être compris entre 1 et 12")
    download_land_reference(LAND_PATH)
    jobs = build_jobs(args.bounds, LAND_PATH)
    completed = [tile for tile in jobs if validate_completed(args.output, tile)]
    completed_set = set(completed)
    pending = [tile for tile in jobs if tile not in completed_set]
    print(f"Pluie quotidienne CERRA-Land : {len(jobs)} tuiles terrestres, Canaries exclues")
    print(f"État : {len(completed)} terminées, {len(pending)} à faire; {args.workers} téléchargements parallèles")
    print(f"Destination : {args.output}")
    if args.dry_run or args.verify_only:
        return 0 if not args.verify_only or not pending else 2

    deadline = time.monotonic() + args.hours * 3600
    successes = failures = downloaded_bytes = 0
    try:
        for start in range(0, len(pending), args.workers):
            if time.monotonic() >= deadline:
                print("Durée maximale atteinte; arrêt propre entre deux lots.", flush=True)
                break
            disk_guard(args.output, args.minimum_free_gb)
            batch = pending[start : start + args.workers]

            def run_with_retries(tile: Tile) -> tuple[dict | None, Exception | None]:
                error: Exception | None = None
                for attempt, delay in enumerate(RETRY_DELAYS_SECONDS, start=1):
                    try:
                        return download_tile(args.output, tile), None
                    except Exception as exc:
                        error = exc
                        if attempt < len(RETRY_DELAYS_SECONDS) and time.monotonic() < deadline:
                            time.sleep(delay + random.uniform(0, min(5, delay / 4)))
                return None, error

            with ThreadPoolExecutor(max_workers=args.workers) as pool:
                futures = {pool.submit(run_with_retries, tile): tile for tile in batch}
                for future in as_completed(futures):
                    tile = futures[future]
                    metadata, error = future.result()
                    if metadata is not None:
                        successes += 1
                        downloaded_bytes += metadata["bytes"]
                        append_event(args.output, {"status": "completed", **metadata})
                        print(
                            f"[{len(completed) + successes}/{len(jobs)}] {tile.identifier} "
                            f"OK {metadata['bytes'] / 1024**2:.1f} Mio",
                            flush=True,
                        )
                    else:
                        failures += 1
                        append_event(
                            args.output,
                            {
                                "status": "failed",
                                "tile": asdict(tile),
                                "error": repr(error),
                                "at": datetime.now(timezone.utc).isoformat(),
                            },
                        )
                        print(f"{tile.identifier} échec temporaire : {error}", flush=True)
    except KeyboardInterrupt:
        print("\nInterruption demandée; les tuiles terminées restent acquises.", flush=True)
    except RuntimeError as exc:
        print(f"Arrêt de sécurité : {exc}", flush=True)

    remaining = sum(not validate_completed(args.output, tile) for tile in jobs)
    print(
        f"Bilan pluie : {successes} nouvelles tuiles, {downloaded_bytes / 1024**3:.2f} Gio, "
        f"{failures} échecs, {remaining} restantes.",
        flush=True,
    )
    return 2 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
