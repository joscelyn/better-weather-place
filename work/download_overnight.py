#!/usr/bin/env python3
"""Resumable overnight download of the CHELSA source windows needed by the project.

The remote CHELSA files are Cloud Optimized GeoTIFFs. Reading a spatial window
downloads only the corresponding byte ranges instead of the complete global
file. Each completed clip is validated and accompanied by a JSON sidecar; an
interrupted run can therefore be restarted without repeating completed jobs.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import random
import shutil
import sys
import time
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import rasterio
from rasterio.enums import Resampling
from rasterio.windows import from_bounds as window_from_bounds


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = ROOT / "work/downloads/chelsa-europe-mediterranee"
DEFAULT_BOUNDS = (-25.0, 25.0, 45.0, 72.0)  # west, south, east, north; Canaries excluded.
VARIABLES = ("tas", "tasmax", "tasmin", "pr")
# Six attempts; the final value is unused because no wait follows the last failure.
RETRY_DELAYS_SECONDS = (5, 30, 120, 500, 1800, 3600)
GDAL_ENV = {
    "GDAL_DISABLE_READDIR_ON_OPEN": "EMPTY_DIR",
    "CPL_VSIL_CURL_ALLOWED_EXTENSIONS": ".tif",
    "GDAL_HTTP_MAX_RETRY": "5",
    "GDAL_HTTP_RETRY_DELAY": "2",
    "GDAL_HTTP_MULTIRANGE": "YES",
    "VSI_CACHE": "TRUE",
    "VSI_CACHE_SIZE": 16 * 1024 * 1024,
}


@dataclass(frozen=True)
class Job:
    variable: str
    year: int
    month: int

    @property
    def identifier(self) -> str:
        return f"{self.variable}-{self.year}-{self.month:02d}"


def parse_range(value: str, minimum: int, maximum: int) -> list[int]:
    values: set[int] = set()
    for part in value.split(","):
        part = part.strip()
        if not part:
            continue
        if ":" in part:
            start_text, end_text = part.split(":", 1)
            start, end = int(start_text), int(end_text)
            values.update(range(start, end + 1))
        else:
            values.add(int(part))
    if not values or min(values) < minimum or max(values) > maximum:
        raise argparse.ArgumentTypeError(
            f"Plage invalide {value!r}; valeurs attendues entre {minimum} et {maximum}."
        )
    return sorted(values)


def parse_bounds(value: str) -> tuple[float, float, float, float]:
    try:
        west, south, east, north = (float(item) for item in value.split(","))
    except ValueError as exc:
        raise argparse.ArgumentTypeError("Format attendu : ouest,sud,est,nord") from exc
    if not (-180 <= west < east <= 180 and -90 <= south < north <= 90):
        raise argparse.ArgumentTypeError("Emprise géographique invalide")
    return west, south, east, north


def chelsa_url(job: Job) -> str:
    return (
        "https://os.unil.cloud.switch.ch/chelsa02/chelsa/global/monthly/"
        f"{job.variable}/{job.year}/"
        f"CHELSA_{job.variable}_{job.month:02d}_{job.year}_V.2.1.tif"
    )


def paths_for(output: Path, job: Job) -> tuple[Path, Path, Path]:
    directory = output / job.variable / str(job.year)
    final = directory / f"{job.month:02d}.tif"
    return final, final.with_suffix(".tif.json"), final.with_suffix(".tif.part")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(4 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def validate_completed(output: Path, job: Job, bounds: tuple[float, float, float, float]) -> bool:
    final, sidecar, _ = paths_for(output, job)
    if not final.exists() or not sidecar.exists() or final.stat().st_size == 0:
        return False
    try:
        metadata = json.loads(sidecar.read_text())
        if metadata.get("job") != asdict(job):
            return False
        if tuple(metadata.get("requested_bounds", ())) != tuple(bounds):
            return False
        if metadata.get("bytes") != final.stat().st_size:
            return False
        with rasterio.open(final) as dataset:
            if dataset.count != 1 or dataset.width < 1 or dataset.height < 1:
                return False
            dataset.read(1, window=((0, 1), (0, 1)))
        return True
    except (OSError, ValueError, json.JSONDecodeError, rasterio.errors.RasterioError):
        return False


def download_clip(
    output: Path,
    job: Job,
    bounds: tuple[float, float, float, float],
) -> dict:
    final, sidecar, temporary = paths_for(output, job)
    final.parent.mkdir(parents=True, exist_ok=True)
    url = chelsa_url(job)
    started = time.monotonic()

    with rasterio.Env(**GDAL_ENV), rasterio.open(url) as source:
        window = window_from_bounds(*bounds, transform=source.transform)
        window = window.round_offsets().round_lengths()
        window = window.intersection(rasterio.windows.Window(0, 0, source.width, source.height))
        data = source.read(1, window=window, resampling=Resampling.nearest)
        transform = source.window_transform(window)
        profile = source.profile.copy()
        profile.update(
            driver="GTiff",
            width=data.shape[1],
            height=data.shape[0],
            transform=transform,
            count=1,
            tiled=True,
            blockxsize=256,
            blockysize=256,
            compress="DEFLATE",
            predictor=2,
            BIGTIFF="IF_SAFER",
        )
        with rasterio.open(temporary, "w", **profile) as target:
            target.write(data, 1)
            target.scales = source.scales
            target.offsets = source.offsets
            target.units = source.units
            target.update_tags(
                source_url=url,
                requested_bounds=",".join(str(value) for value in bounds),
                downloaded_at=datetime.now(timezone.utc).isoformat(),
            )

    with rasterio.open(temporary) as check:
        if check.width != data.shape[1] or check.height != data.shape[0]:
            raise RuntimeError(f"Contrôle dimensionnel échoué pour {job.identifier}")
        check.read(1, window=((0, 1), (0, 1)))

    temporary.replace(final)
    metadata = {
        "job": asdict(job),
        "source_url": url,
        "requested_bounds": list(bounds),
        "bytes": final.stat().st_size,
        "sha256": sha256(final),
        "elapsed_seconds": round(time.monotonic() - started, 3),
        "completed_at": datetime.now(timezone.utc).isoformat(),
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
    required = int(minimum_free_gb * 1024**3)
    if free < required:
        raise RuntimeError(
            f"Espace libre insuffisant : {free / 1024**3:.1f} Gio; "
            f"minimum demandé {minimum_free_gb:.1f} Gio."
        )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Télécharge de façon reprenable les fenêtres CHELSA 1991–2020 utiles au projet."
    )
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument(
        "--bounds",
        type=parse_bounds,
        default=DEFAULT_BOUNDS,
        metavar="OUEST,SUD,EST,NORD",
        help="Emprise EPSG:4326; défaut: -25,25,45,72 (Europe et Méditerranée, sans Canaries).",
    )
    parser.add_argument("--variables", default=",".join(VARIABLES))
    parser.add_argument("--years", default="1991:2020")
    parser.add_argument("--months", default="1:12")
    parser.add_argument(
        "--hours",
        type=float,
        default=10.0,
        help="Durée maximale. Le job en cours est terminé avant l’arrêt.",
    )
    parser.add_argument("--minimum-free-gb", type=float, default=20.0)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--verify-only", action="store_true")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    variables = [item.strip() for item in args.variables.split(",") if item.strip()]
    unknown = sorted(set(variables).difference(VARIABLES))
    if unknown:
        raise SystemExit(f"Variables inconnues : {', '.join(unknown)}")
    years = parse_range(args.years, 1991, 2020)
    months = parse_range(args.months, 1, 12)
    jobs = [Job(variable, year, month) for variable in variables for month in months for year in years]
    completed = [job for job in jobs if validate_completed(args.output, job, args.bounds)]
    pending = [job for job in jobs if job not in set(completed)]

    print(f"Emprise : {args.bounds}")
    print(f"Destination : {args.output}")
    print(f"Jobs : {len(jobs)} total, {len(completed)} terminés, {len(pending)} à faire")
    print("Ordre : variable, mois, puis les 30 années — un mois complet devient vite exploitable.")
    if args.dry_run or args.verify_only:
        return 0 if not args.verify_only or not pending else 2

    disk_guard(args.output, args.minimum_free_gb)
    deadline = time.monotonic() + args.hours * 3600
    successes = 0
    failures = 0
    downloaded_bytes = 0

    try:
        for position, job in enumerate(pending, start=1):
            if time.monotonic() >= deadline:
                print("Durée maximale atteinte; arrêt propre entre deux fichiers.", flush=True)
                break
            disk_guard(args.output, args.minimum_free_gb)
            print(f"[{position}/{len(pending)}] {job.identifier}", flush=True)
            error: Exception | None = None
            for attempt, delay in enumerate(RETRY_DELAYS_SECONDS, start=1):
                try:
                    metadata = download_clip(args.output, job, args.bounds)
                    successes += 1
                    downloaded_bytes += metadata["bytes"]
                    append_event(args.output, {"status": "completed", **metadata})
                    print(
                        f"  OK {metadata['bytes'] / 1024**2:.1f} Mio "
                        f"en {metadata['elapsed_seconds']:.1f}s",
                        flush=True,
                    )
                    error = None
                    break
                except Exception as exc:
                    error = exc
                    event = {
                        "status": "retry",
                        "job": asdict(job),
                        "attempt": attempt,
                        "error": repr(exc),
                        "at": datetime.now(timezone.utc).isoformat(),
                    }
                    append_event(args.output, event)
                    print(f"  échec {attempt}/{len(RETRY_DELAYS_SECONDS)} : {exc}", flush=True)
                    if attempt < len(RETRY_DELAYS_SECONDS):
                        wait = delay + random.uniform(0, min(5, delay / 4))
                        print(f"  nouvel essai dans {wait:.1f}s", flush=True)
                        time.sleep(wait)
            if error is not None:
                failures += 1
                append_event(
                    args.output,
                    {
                        "status": "failed",
                        "job": asdict(job),
                        "error": repr(error),
                        "at": datetime.now(timezone.utc).isoformat(),
                    },
                )
                print("  ABANDON TEMPORAIRE; le prochain lancement réessaiera ce fichier.", flush=True)
    except KeyboardInterrupt:
        print("\nInterruption demandée; les fichiers terminés restent acquis.", flush=True)

    remaining = sum(not validate_completed(args.output, job, args.bounds) for job in jobs)
    print(
        f"Bilan : {successes} nouveaux fichiers, {downloaded_bytes / 1024**3:.2f} Gio locaux, "
        f"{failures} échecs, {remaining} restants.",
        flush=True,
    )
    return 2 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
