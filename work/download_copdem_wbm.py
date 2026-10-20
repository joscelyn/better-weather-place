#!/usr/bin/env python3
"""Download the catalogued Copernicus DEM GLO-30 WBM tiles with resume and retry."""

from __future__ import annotations

import argparse
import csv
import hashlib
import random
import shutil
import threading
import time
from concurrent.futures import FIRST_COMPLETED, Future, ThreadPoolExecutor, wait
from dataclasses import dataclass
from pathlib import Path

import requests


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CATALOGUE = ROOT / "outputs/catalogue-wbm-copdem.csv"
DEFAULT_OUTPUT = ROOT / "work/downloads/copdem-wbm"
RETRY_DELAYS_SECONDS = (5, 30, 120, 500, 1_800)


@dataclass(frozen=True)
class Tile:
    south: int
    west: int
    bytes: int
    md5: str
    url: str

    @property
    def name(self) -> str:
        latitude = f"{'N' if self.south >= 0 else 'S'}{abs(self.south):02d}"
        longitude = f"{'E' if self.west >= 0 else 'W'}{abs(self.west):03d}"
        return f"{latitude}_{longitude}_WBM.tif"


def load_catalogue(path: Path) -> list[Tile]:
    rows = list(csv.DictReader(path.open()))
    tiles = [
        Tile(
            south=int(row["south"]),
            west=int(row["west"]),
            bytes=int(row["bytes"]),
            md5=row["etag"].lower(),
            url=row["url"],
        )
        for row in rows
    ]
    if not tiles:
        raise RuntimeError(f"Catalogue WBM vide : {path}")
    return tiles


def paths_for(root: Path, tile: Tile) -> tuple[Path, Path]:
    final = root / f"lat-{tile.south:+03d}" / tile.name
    return final, final.with_suffix(".tif.part")


def md5(path: Path) -> str:
    digest = hashlib.md5(usedforsecurity=False)
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def is_valid(path: Path, tile: Tile, checksum: bool = True) -> bool:
    if not path.exists() or path.stat().st_size != tile.bytes:
        return False
    return not checksum or md5(path) == tile.md5


def free_gib(path: Path) -> float:
    return shutil.disk_usage(path).free / 1024**3


def download(tile: Tile, root: Path, deadline: float, minimum_free_gb: float) -> tuple[bool, str]:
    final, temporary = paths_for(root, tile)
    if is_valid(final, tile):
        return True, "déjà valide"
    final.parent.mkdir(parents=True, exist_ok=True)
    error: Exception | None = None
    for attempt, delay in enumerate((*RETRY_DELAYS_SECONDS, None), start=1):
        if time.monotonic() >= deadline:
            return False, "délai atteint"
        if free_gib(root) < minimum_free_gb:
            return False, "espace disque minimal atteint"
        try:
            existing = temporary.stat().st_size if temporary.exists() else 0
            if existing > tile.bytes:
                temporary.unlink()
                existing = 0
            headers = {"Range": f"bytes={existing}-"} if existing else {}
            with requests.get(tile.url, headers=headers, stream=True, timeout=(30, 120)) as response:
                if existing and response.status_code == 200:
                    temporary.unlink(missing_ok=True)
                    existing = 0
                elif response.status_code not in (200, 206):
                    response.raise_for_status()
                with temporary.open("ab" if existing else "wb") as stream:
                    for chunk in response.iter_content(256 * 1024):
                        if chunk:
                            stream.write(chunk)
            if temporary.stat().st_size != tile.bytes:
                raise RuntimeError(f"taille {temporary.stat().st_size}, attendu {tile.bytes}")
            if md5(temporary) != tile.md5:
                temporary.unlink(missing_ok=True)
                raise RuntimeError("MD5 différent de l’ETag S3")
            temporary.replace(final)
            return True, "OK"
        except (OSError, requests.RequestException, RuntimeError) as exc:
            error = exc
            if delay is None:
                break
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                break
            time.sleep(min(delay + random.uniform(0, min(5, delay / 4)), remaining))
    return False, str(error)


def main() -> int:
    parser = argparse.ArgumentParser(description="Télécharge le masque WBM Copernicus de façon reprenable.")
    parser.add_argument("--catalogue", type=Path, default=DEFAULT_CATALOGUE)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--hours", type=float, default=2.0)
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--limit", type=int, help="Limite le catalogue, utile pour un essai.")
    parser.add_argument("--minimum-free-gb", type=float, default=15.0)
    parser.add_argument("--verify-only", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    tiles = load_catalogue(args.catalogue)
    if args.limit is not None:
        tiles = tiles[: max(0, args.limit)]
    valid = [tile for tile in tiles if is_valid(paths_for(args.output, tile)[0], tile)]
    pending = [tile for tile in tiles if tile not in valid]
    print(
        f"WBM Copernicus : {len(tiles)} tuiles, {len(valid)} valides, {len(pending)} à télécharger, "
        f"{sum(tile.bytes for tile in pending) / 1024**2:.1f} Mio restants",
        flush=True,
    )
    if args.dry_run or args.verify_only or not pending:
        return 0 if not pending else 2

    deadline = time.monotonic() + max(0, args.hours) * 3600
    lock = threading.Lock()
    finished = len(valid)
    failures = 0
    iterator = iter(pending)
    futures: dict[Future, Tile] = {}
    with ThreadPoolExecutor(max_workers=max(1, args.workers)) as pool:
        while len(futures) < args.workers:
            try:
                tile = next(iterator)
            except StopIteration:
                break
            futures[pool.submit(download, tile, args.output, deadline, args.minimum_free_gb)] = tile

        while futures:
            done, _ = wait(futures, return_when=FIRST_COMPLETED)
            for future in done:
                tile = futures.pop(future)
                ok, message = future.result()
                with lock:
                    if ok:
                        finished += 1
                    else:
                        failures += 1
                    print(f"[{finished}/{len(tiles)}] {tile.name} {message}", flush=True)
                if time.monotonic() < deadline:
                    try:
                        next_tile = next(iterator)
                    except StopIteration:
                        continue
                    futures[pool.submit(
                        download, next_tile, args.output, deadline, args.minimum_free_gb
                    )] = next_tile

    remaining = sum(not is_valid(paths_for(args.output, tile)[0], tile, checksum=False) for tile in tiles)
    print(f"Fin WBM : {len(tiles) - remaining}/{len(tiles)} présents, {failures} échec(s).")
    return 0 if remaining == 0 else 2


if __name__ == "__main__":
    raise SystemExit(main())
