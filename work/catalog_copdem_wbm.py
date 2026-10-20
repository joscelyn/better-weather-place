#!/usr/bin/env python3
"""Catalog public Copernicus DEM GLO-30 WBM tiles for the project domain."""

from __future__ import annotations

import argparse
import csv
import json
import random
import re
import time
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path

import requests


ROOT = Path(__file__).resolve().parents[1]
BASE_URL = "https://copernicus-dem-30m.s3.eu-central-1.amazonaws.com"
DEFAULT_OUTPUT = ROOT / "outputs/catalogue-wbm-copdem.csv"
DEFAULT_SUMMARY = ROOT / "outputs/catalogue-wbm-copdem.json"
DEFAULT_BOUNDS = (-25, 25, 45, 72)
RETRY_DELAYS = (1, 5, 30, 120)
S3_NAMESPACE = {"s3": "http://s3.amazonaws.com/doc/2006-03-01/"}
DIRECTORY_PATTERN = re.compile(
    r"^Copernicus_DSM_COG_10_([NS])(\d{2})_00_([EW])(\d{3})_00_DEM/$"
)


def parse_bounds(value: str) -> tuple[int, int, int, int]:
    try:
        west, south, east, north = (int(item.strip()) for item in value.split(","))
    except (TypeError, ValueError) as exc:
        raise argparse.ArgumentTypeError("Emprise attendue : ouest,sud,est,nord") from exc
    if west >= east or south >= north:
        raise argparse.ArgumentTypeError("Emprise vide")
    return west, south, east, north


def latitude_token(latitude: int) -> str:
    return f"{'N' if latitude >= 0 else 'S'}{abs(latitude):02d}"


def decode_directory(prefix: str) -> tuple[int, int] | None:
    match = DIRECTORY_PATTERN.match(prefix)
    if not match:
        return None
    latitude = int(match.group(2)) * (1 if match.group(1) == "N" else -1)
    longitude = int(match.group(4)) * (1 if match.group(3) == "E" else -1)
    return latitude, longitude


def list_latitude(latitude: int) -> list[tuple[int, int, str]]:
    prefix = f"Copernicus_DSM_COG_10_{latitude_token(latitude)}_00_"
    error: Exception | None = None
    for attempt, delay in enumerate(RETRY_DELAYS, start=1):
        try:
            response = requests.get(
                BASE_URL + "/",
                params={"list-type": "2", "prefix": prefix, "delimiter": "/", "max-keys": 1000},
                timeout=60,
            )
            response.raise_for_status()
            root = ET.fromstring(response.content)
            if root.findtext("s3:IsTruncated", namespaces=S3_NAMESPACE) == "true":
                raise RuntimeError(f"Liste S3 tronquée pour {prefix}")
            results = []
            for node in root.findall("s3:CommonPrefixes/s3:Prefix", S3_NAMESPACE):
                directory = node.text or ""
                coordinates = decode_directory(directory)
                if coordinates is not None:
                    results.append((*coordinates, directory))
            return results
        except (requests.RequestException, ET.ParseError, RuntimeError) as exc:
            error = exc
            if attempt < len(RETRY_DELAYS):
                time.sleep(delay + random.uniform(0, 1))
    raise RuntimeError(f"Échec de l’index S3 pour {prefix}: {error}")


def wbm_url(directory: str) -> str:
    stem = directory.rstrip("/").removesuffix("_DEM")
    return f"{BASE_URL}/{directory}AUXFILES/{stem}_WBM.tif"


def head_tile(item: tuple[int, int, str]) -> dict:
    latitude, longitude, directory = item
    url = wbm_url(directory)
    error: Exception | None = None
    for attempt, delay in enumerate(RETRY_DELAYS, start=1):
        try:
            response = requests.head(url, timeout=60)
            response.raise_for_status()
            return {
                "south": latitude,
                "west": longitude,
                "north": latitude + 1,
                "east": longitude + 1,
                "bytes": int(response.headers["content-length"]),
                "etag": response.headers.get("etag", "").strip('"'),
                "url": url,
            }
        except (requests.RequestException, KeyError, ValueError) as exc:
            error = exc
            if attempt < len(RETRY_DELAYS):
                time.sleep(delay + random.uniform(0, 1))
    raise RuntimeError(f"Échec HEAD WBM {latitude:+d}/{longitude:+d}: {error}")


def is_canary_tile(latitude: int, longitude: int) -> bool:
    return 27 <= latitude < 30 and -19 <= longitude < -13


def atomic_json(path: Path, value: dict) -> None:
    temporary = path.with_suffix(path.suffix + ".part")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n")
    temporary.replace(path)


def main() -> int:
    parser = argparse.ArgumentParser(description="Catalogue les tuiles publiques Copernicus WBM.")
    parser.add_argument("--bounds", type=parse_bounds, default=DEFAULT_BOUNDS)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--summary", type=Path, default=DEFAULT_SUMMARY)
    parser.add_argument("--workers", type=int, default=12)
    parser.add_argument("--include-canaries", action="store_true")
    args = parser.parse_args()
    west, south, east, north = args.bounds

    directories: list[tuple[int, int, str]] = []
    with ThreadPoolExecutor(max_workers=min(args.workers, north - south)) as pool:
        futures = {pool.submit(list_latitude, latitude): latitude for latitude in range(south, north)}
        for index, future in enumerate(as_completed(futures), start=1):
            directories.extend(future.result())
            print(f"Index S3 : {index}/{len(futures)} latitudes", flush=True)

    selected = [
        item for item in directories
        if west <= item[1] < east
        and (args.include_canaries or not is_canary_tile(item[0], item[1]))
    ]
    rows: list[dict] = []
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures = {pool.submit(head_tile, item): item for item in selected}
        for index, future in enumerate(as_completed(futures), start=1):
            rows.append(future.result())
            if index % 100 == 0 or index == len(futures):
                print(f"Métadonnées WBM : {index}/{len(futures)}", flush=True)
    rows.sort(key=lambda row: (row["south"], row["west"]))

    args.output.parent.mkdir(parents=True, exist_ok=True)
    temporary = args.output.with_suffix(args.output.suffix + ".part")
    with temporary.open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    temporary.replace(args.output)

    summary = {
        "source": "Copernicus DEM GLO-30 Water Body Mask",
        "bounds": list(args.bounds),
        "canaries_included": args.include_canaries,
        "tile_count": len(rows),
        "total_bytes": sum(row["bytes"] for row in rows),
        "minimum_tile_bytes": min(row["bytes"] for row in rows),
        "maximum_tile_bytes": max(row["bytes"] for row in rows),
        "catalogued_at": datetime.now(timezone.utc).isoformat(),
        "catalogue": args.output.relative_to(ROOT).as_posix(),
    }
    atomic_json(args.summary, summary)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
