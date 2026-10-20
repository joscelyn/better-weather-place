#!/usr/bin/env python3
"""Download a delivered CM SAF SARAH-3 order with retries and HTTP resume."""

from __future__ import annotations

import argparse
import getpass
import hashlib
import json
import random
import shutil
import tarfile
import time
import zipfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import unquote, urlsplit, urlunsplit

import requests
from netCDF4 import Dataset


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = ROOT / "work/downloads/sarah3-monthly"
# Six attempts; the final value is unused because no wait follows the last failure.
RETRY_DELAYS_SECONDS = (5, 30, 120, 500, 1800, 3600)
CHUNK_SIZE = 1024 * 1024
EXPECTED_FILES = {
    "ORD70729.tar": {
        "bytes": 2_971_361_280,
        "md5": "b253bef2a734e52a4417c1b16a32d5ae",
        "products": 360,
    }
}


@dataclass(frozen=True)
class Download:
    url: str
    filename: str


def safe_url(url: str) -> str:
    """Remove credentials, query and fragment before logging or persisting a URL."""
    parts = urlsplit(url)
    hostname = parts.hostname or ""
    if parts.port:
        hostname = f"{hostname}:{parts.port}"
    return urlunsplit((parts.scheme, hostname, parts.path, "", ""))


def safe_filename(value: str) -> str:
    filename = Path(unquote(value.strip())).name
    if not filename or filename in {".", ".."}:
        raise ValueError(f"Nom de fichier invalide : {value!r}")
    return filename


def filename_from_url(url: str) -> str:
    filename = safe_filename(urlsplit(url).path)
    if "." not in filename:
        raise ValueError(
            "Le lien ne contient pas de nom de fichier. Utiliser une ligne "
            "« nom-fichier<TAB>URL » dans le manifeste."
        )
    return filename


def parse_manifest(path: Path) -> list[Download]:
    downloads: list[Download] = []
    for line_number, raw_line in enumerate(path.read_text().splitlines(), start=1):
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if "\t" in line:
            filename, url = line.split("\t", 1)
            filename = safe_filename(filename)
            url = url.strip()
        else:
            url = line
            filename = filename_from_url(url)
        parts = urlsplit(url)
        if parts.scheme != "https" or not parts.netloc:
            raise ValueError(f"Ligne {line_number} : URL HTTPS attendue")
        downloads.append(Download(url, filename))
    if not downloads:
        raise ValueError(f"Aucun lien trouvé dans {path}")
    duplicates = sorted(
        filename for filename in {item.filename for item in downloads}
        if sum(item.filename == filename for item in downloads) > 1
    )
    if duplicates:
        raise ValueError(f"Noms de fichiers en double : {', '.join(duplicates)}")
    return downloads


def file_digests(path: Path) -> tuple[str, str]:
    sha256_digest = hashlib.sha256()
    md5_digest = hashlib.md5(usedforsecurity=False)
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(4 * 1024 * 1024), b""):
            sha256_digest.update(chunk)
            md5_digest.update(chunk)
    return sha256_digest.hexdigest(), md5_digest.hexdigest()


def sidecar_for(path: Path) -> Path:
    return path.with_suffix(path.suffix + ".json")


def validate_netcdf(path: Path) -> dict:
    with Dataset(path) as dataset:
        variable_names = set(dataset.variables)
        sdu_name = next((name for name in variable_names if name.lower() == "sdu"), None)
        if sdu_name is None:
            for name, variable in dataset.variables.items():
                description = " ".join(
                    str(getattr(variable, attribute, ""))
                    for attribute in ("standard_name", "long_name")
                ).lower()
                if "sunshine" in description and "duration" in description:
                    sdu_name = name
                    break
        if sdu_name is None:
            raise RuntimeError(f"Variable SDU absente de {path.name}")
        variable = dataset[sdu_name]
        if variable.size == 0:
            raise RuntimeError(f"Variable SDU vide dans {path.name}")
        return {
            "content_type": "netcdf",
            "sdu_variable": sdu_name,
            "sdu_shape": list(variable.shape),
            "sdu_units": str(getattr(variable, "units", "")),
        }


def validate_payload(path: Path, logical_name: str | None = None) -> dict:
    name = (logical_name or path.name).lower()
    if name.endswith((".nc", ".nc4")):
        return validate_netcdf(path)
    if name.endswith(".zip"):
        with zipfile.ZipFile(path) as archive:
            corrupt = archive.testzip()
            if corrupt:
                raise RuntimeError(f"Archive ZIP corrompue au niveau de {corrupt}")
            members = [item for item in archive.infolist() if not item.is_dir()]
        return {"content_type": "zip", "member_count": len(members)}
    if name.endswith((".tar", ".tar.gz", ".tgz", ".tar.bz2", ".tar.xz")):
        with tarfile.open(path) as archive:
            members = [item for item in archive.getmembers() if item.isfile()]
        return {"content_type": "tar", "member_count": len(members)}
    if path.stat().st_size == 0:
        raise RuntimeError(f"Fichier vide : {path.name}")
    return {"content_type": "unknown"}


def is_completed(output: Path, job: Download) -> bool:
    final = output / job.filename
    sidecar = sidecar_for(final)
    if not final.exists() or not sidecar.exists() or final.stat().st_size == 0:
        return False
    try:
        metadata = json.loads(sidecar.read_text())
        valid = (
            metadata.get("source") == safe_url(job.url)
            and metadata.get("bytes") == final.stat().st_size
        )
        expected = EXPECTED_FILES.get(job.filename)
        if expected:
            valid = valid and metadata.get("bytes") == expected["bytes"]
            valid = valid and metadata.get("md5") == expected["md5"]
        return valid and bool(metadata.get("sha256"))
    except (OSError, ValueError, json.JSONDecodeError):
        return False


def expected_total(response: requests.Response, existing: int) -> int | None:
    content_range = response.headers.get("Content-Range", "")
    if "/" in content_range:
        total = content_range.rsplit("/", 1)[1]
        if total.isdigit():
            return int(total)
    content_length = response.headers.get("Content-Length")
    if content_length and content_length.isdigit():
        return int(content_length) + (existing if response.status_code == 206 else 0)
    return None


def download_one(session: requests.Session, output: Path, job: Download) -> dict:
    output.mkdir(parents=True, exist_ok=True)
    final = output / job.filename
    temporary = final.with_suffix(final.suffix + ".part")
    existing = temporary.stat().st_size if temporary.exists() else 0
    headers = {"Range": f"bytes={existing}-"} if existing else {}
    started = time.monotonic()
    with session.get(job.url, headers=headers, stream=True, timeout=(30, 120)) as response:
        if response.status_code == 416 and existing:
            content_range = response.headers.get("Content-Range", "")
            remote_size = content_range.rsplit("/", 1)[-1]
            if remote_size.isdigit() and int(remote_size) == existing:
                validation = validate_payload(temporary, job.filename)
                return finish(temporary, final, job, validation, started, resumed=True)
        response.raise_for_status()
        resumed = existing > 0 and response.status_code == 206
        if existing and not resumed:
            existing = 0
        expected = expected_total(response, existing)
        mode = "ab" if resumed else "wb"
        with temporary.open(mode) as stream:
            for chunk in response.iter_content(CHUNK_SIZE):
                if chunk:
                    stream.write(chunk)
    if expected is not None and temporary.stat().st_size != expected:
        raise RuntimeError(
            f"Taille reçue incorrecte pour {job.filename} : "
            f"{temporary.stat().st_size} au lieu de {expected} octets"
        )
    validation = validate_payload(temporary, job.filename)
    return finish(temporary, final, job, validation, started, resumed)


def finish(
    temporary: Path, final: Path, job: Download, validation: dict,
    started: float, resumed: bool,
) -> dict:
    size = temporary.stat().st_size
    expected = EXPECTED_FILES.get(job.filename)
    if expected and size != expected["bytes"]:
        raise RuntimeError(
            f"Taille CM SAF incorrecte pour {job.filename} : {size} au lieu de "
            f"{expected['bytes']} octets"
        )
    sha256_value, md5_value = file_digests(temporary)
    if expected and md5_value != expected["md5"]:
        raise RuntimeError(
            f"MD5 CM SAF incorrect pour {job.filename} : {md5_value}"
        )
    temporary.replace(final)
    metadata = {
        "order_id": "ORD70729", "filename": job.filename,
        "source": safe_url(job.url), "bytes": size,
        "sha256": sha256_value, "md5": md5_value,
        "expected_products": expected["products"] if expected else None,
        "resumed": resumed, **validation,
        "elapsed_seconds": round(time.monotonic() - started, 3),
        "completed_at": datetime.now(timezone.utc).isoformat(),
    }
    sidecar_for(final).write_text(json.dumps(metadata, ensure_ascii=False, indent=2) + "\n")
    return metadata


def disk_guard(output: Path, minimum_free_gb: float) -> None:
    output.mkdir(parents=True, exist_ok=True)
    free = shutil.disk_usage(output).free
    if free < minimum_free_gb * 1024**3:
        raise RuntimeError(
            f"Espace libre insuffisant : {free / 1024**3:.1f} Gio; "
            f"minimum demandé {minimum_free_gb:.1f} Gio."
        )


def append_event(output: Path, payload: dict) -> None:
    with (output / "download-events.jsonl").open("a") as stream:
        stream.write(json.dumps(payload, ensure_ascii=False) + "\n")


def main() -> int:
    parser = argparse.ArgumentParser(description="Télécharge la commande CM SAF ORD70729.")
    parser.add_argument("--url-file", type=Path, required=True)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--username", default="routcm")
    parser.add_argument("--hours", type=float, default=10.0)
    parser.add_argument("--minimum-free-gb", type=float, default=10.0)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--verify-only", action="store_true")
    args = parser.parse_args()

    jobs = parse_manifest(args.url_file)
    completed = [job for job in jobs if is_completed(args.output, job)]
    completed_set = set(completed)
    pending = [job for job in jobs if job not in completed_set]
    print(f"Commande : ORD70729")
    print(f"Destination : {args.output}")
    print(f"Fichiers : {len(jobs)} total, {len(completed)} terminés, {len(pending)} à faire")
    if args.dry_run or args.verify_only:
        return 0 if not args.verify_only or not pending else 2

    deadline = time.monotonic() + args.hours * 3600
    failures = 0
    with requests.Session() as session:
        session.headers["User-Agent"] = "better-weather-place/1.0 (CM SAF order ORD70729)"
        if args.username:
            password = getpass.getpass(f"Mot de passe HTTPS CM SAF pour {args.username} : ")
            session.auth = (args.username, password)
        for position, job in enumerate(pending, start=1):
            if time.monotonic() >= deadline:
                print("Durée maximale atteinte; arrêt propre entre deux fichiers.")
                break
            disk_guard(args.output, args.minimum_free_gb)
            print(f"[{position}/{len(pending)}] {job.filename}", flush=True)
            error: Exception | None = None
            for attempt, delay in enumerate(RETRY_DELAYS_SECONDS, start=1):
                try:
                    metadata = download_one(session, args.output, job)
                    append_event(args.output, {"status": "completed", **metadata})
                    print(
                        f"  OK {metadata['bytes'] / 1024**2:.1f} Mio "
                        f"en {metadata['elapsed_seconds']:.1f}s",
                        flush=True,
                    )
                    error = None
                    break
                except Exception as exception:
                    error = exception
                    append_event(args.output, {
                        "status": "retry", "filename": job.filename,
                        "source": safe_url(job.url), "attempt": attempt,
                        "error": repr(exception), "at": datetime.now(timezone.utc).isoformat(),
                    })
                    print(f"  échec {attempt}/{len(RETRY_DELAYS_SECONDS)} : {exception}")
                    if attempt < len(RETRY_DELAYS_SECONDS):
                        wait = delay + random.uniform(0, min(5, delay / 4))
                        print(f"  nouvel essai dans {wait:.1f}s", flush=True)
                        time.sleep(wait)
            if error is not None:
                failures += 1

    remaining = [job for job in jobs if not is_completed(args.output, job)]
    print(f"Fin : {len(jobs) - len(remaining)}/{len(jobs)} fichiers valides, {failures} échec(s).")
    return 0 if not remaining else 2


if __name__ == "__main__":
    raise SystemExit(main())
