#!/usr/bin/env python3
"""Run all currently available overnight downloads within one shared deadline."""

from __future__ import annotations

import argparse
import subprocess
import sys
import time
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SARAH_MANIFEST = ROOT / "work/downloads/sarah3-ORD70729-urls.txt"
DEFAULT_CERRA_DOWNLOADS = ROOT / "work/downloads/cerra-land-daily-rain-1991-2020"


def run(script: str, hours: float, extra: list[str]) -> int:
    command = [sys.executable, str(ROOT / "work" / script), "--hours", f"{hours:.4f}", *extra]
    print(f"\n=== {script} — jusqu’à {hours:.2f} h disponibles ===", flush=True)
    return subprocess.run(command, cwd=ROOT, check=False).returncode


def run_rain_builder() -> int:
    command = [sys.executable, str(ROOT / "work/build_cerra_rainy_days.py")]
    print("\n=== build_cerra_rainy_days.py — traitement des tuiles disponibles ===", flush=True)
    return subprocess.run(command, cwd=ROOT, check=False).returncode


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Téléchargement nocturne SARAH-3, CHELSA puis pluie CERRA-Land."
    )
    parser.add_argument("--hours", type=float, default=10.0)
    parser.add_argument("--minimum-free-gb", type=float, default=15.0)
    parser.add_argument(
        "--rain-workers",
        type=int,
        default=1,
        help="Requêtes CERRA-Land simultanées (défaut : 1, limite recommandée par le CDS).",
    )
    parser.add_argument("--sarah-url-file", type=Path, default=DEFAULT_SARAH_MANIFEST)
    args = parser.parse_args()
    started = time.monotonic()
    reserve = ["--minimum-free-gb", str(args.minimum_free_gb)]

    sarah_code = 0
    if args.sarah_url_file.exists():
        sarah_code = run(
            "download_sarah_order.py",
            args.hours,
            [*reserve, "--url-file", str(args.sarah_url_file)],
        )
    else:
        print(f"SARAH-3 ignoré : manifeste absent ({args.sarah_url_file}).")

    remaining = max(0.0, args.hours - (time.monotonic() - started) / 3600)
    chelsa_code = 0
    if remaining > 0.01:
        chelsa_code = run("download_overnight.py", remaining, reserve)
    else:
        print("Aucun temps restant pour CHELSA; cette phase reprendra au prochain lancement.")

    remaining = max(0.0, args.hours - (time.monotonic() - started) / 3600)
    wbm_code = 0
    if remaining > 0.01:
        wbm_code = run("download_copdem_wbm.py", remaining, reserve)
    else:
        print("Aucun temps restant pour le WBM; cette phase reprendra au prochain lancement.")

    remaining = max(0.0, args.hours - (time.monotonic() - started) / 3600)
    rain_code = 0
    if remaining > 0.01:
        rain_code = run(
            "download_cerra_rain.py",
            remaining,
            [*reserve, "--workers", str(args.rain_workers)],
        )
    else:
        print("Aucun temps restant pour la phase CERRA-Land; elle reprendra au prochain lancement.")

    rain_build_code = 0
    if DEFAULT_CERRA_DOWNLOADS.exists() and any(DEFAULT_CERRA_DOWNLOADS.rglob("*.zip")):
        rain_build_code = run_rain_builder()
    else:
        print("Calcul des jours de pluie ignoré : aucune archive CERRA-Land disponible.")

    print(
        f"\nFin de nuit : SARAH-3={sarah_code}, CHELSA={chelsa_code}, "
        f"WBM={wbm_code}, pluie quotidienne={rain_code}, "
        f"normales jours de pluie={rain_build_code}",
        flush=True,
    )
    return 2 if any(
        code != 0 for code in (sarah_code, chelsa_code, wbm_code, rain_code, rain_build_code)
    ) else 0


if __name__ == "__main__":
    raise SystemExit(main())
