#!/usr/bin/env python3
"""Safely extract and validate the 360 NetCDF files from CM SAF order ORD70729."""

from __future__ import annotations

import argparse
import json
import shutil
import tarfile
from pathlib import Path, PurePosixPath

from download_sarah_order import DEFAULT_OUTPUT, EXPECTED_FILES, sidecar_for, validate_netcdf


DEFAULT_ARCHIVE = DEFAULT_OUTPUT / "ORD70729.tar"
EXPECTED_PRODUCTS = EXPECTED_FILES["ORD70729.tar"]["products"]


def safe_relative_path(name: str) -> Path:
    value = PurePosixPath(name)
    if value.is_absolute() or ".." in value.parts or not value.name:
        raise RuntimeError(f"Chemin dangereux dans l'archive : {name!r}")
    return Path(*value.parts)


def validate_archive_delivery(path: Path) -> None:
    sidecar = sidecar_for(path)
    if not path.exists() or not sidecar.exists():
        raise RuntimeError(
            f"Archive validée et métadonnées attendues : {path} et {sidecar}"
        )
    metadata = json.loads(sidecar.read_text())
    expected = EXPECTED_FILES[path.name]
    if path.stat().st_size != expected["bytes"] or metadata.get("bytes") != expected["bytes"]:
        raise RuntimeError("La taille de l'archive ne correspond pas à la livraison CM SAF")
    if metadata.get("md5") != expected["md5"]:
        raise RuntimeError("Le MD5 validé de l'archive ne correspond pas à CM SAF")


def netcdf_members(archive: tarfile.TarFile) -> list[tuple[tarfile.TarInfo, Path]]:
    result: list[tuple[tarfile.TarInfo, Path]] = []
    for member in archive.getmembers():
        relative = safe_relative_path(member.name)
        if member.isdir():
            continue
        if not member.isfile():
            raise RuntimeError(f"Type de membre TAR refusé : {member.name}")
        if relative.suffix.lower() in {".nc", ".nc4"}:
            result.append((member, relative))
    if len(result) != EXPECTED_PRODUCTS:
        raise RuntimeError(
            f"{len(result)} NetCDF trouvés dans l'archive; {EXPECTED_PRODUCTS} attendus"
        )
    paths = [relative for _, relative in result]
    if len(paths) != len(set(paths)):
        raise RuntimeError("Noms NetCDF en double dans l'archive")
    return result


def completed(path: Path, expected_size: int) -> bool:
    if not path.exists() or path.stat().st_size != expected_size:
        return False
    try:
        validate_netcdf(path)
        return True
    except (OSError, RuntimeError):
        return False


def main() -> int:
    parser = argparse.ArgumentParser(description="Extrait la commande SARAH-3 ORD70729.")
    parser.add_argument("--archive", type=Path, default=DEFAULT_ARCHIVE)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--minimum-free-gb", type=float, default=10.0)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    validate_archive_delivery(args.archive)
    with tarfile.open(args.archive) as archive:
        members = netcdf_members(archive)
        ready = [
            (member, relative)
            for member, relative in members
            if completed(args.output / relative, member.size)
        ]
        pending = [item for item in members if item not in ready]
        print(
            f"Archive ORD70729 : {len(members)} NetCDF, {len(ready)} extraits, "
            f"{len(pending)} à faire"
        )
        if args.dry_run:
            return 0
        required = sum(member.size for member, _ in pending)
        free = shutil.disk_usage(args.output).free
        reserve = int(args.minimum_free_gb * 1024**3)
        if free < required + reserve:
            raise RuntimeError(
                f"Espace insuffisant : {free / 1024**3:.1f} Gio libres; "
                f"{required / 1024**3:.1f} Gio à extraire et "
                f"{args.minimum_free_gb:.1f} Gio de réserve demandés"
            )
        for position, (member, relative) in enumerate(pending, start=1):
            destination = args.output / relative
            temporary = destination.with_suffix(destination.suffix + ".part")
            destination.parent.mkdir(parents=True, exist_ok=True)
            source = archive.extractfile(member)
            if source is None:
                raise RuntimeError(f"Impossible de lire {member.name}")
            with source, temporary.open("wb") as target:
                shutil.copyfileobj(source, target, length=1024 * 1024)
            if temporary.stat().st_size != member.size:
                raise RuntimeError(f"Taille extraite incorrecte pour {member.name}")
            validate_netcdf(temporary)
            temporary.replace(destination)
            print(f"[{position}/{len(pending)}] {relative}", flush=True)
    print(f"Extraction terminée : {EXPECTED_PRODUCTS} NetCDF valides.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
