#!/usr/bin/env python3
"""Run all currently available overnight downloads within one shared deadline."""

from __future__ import annotations

import argparse
import subprocess
import sys
import time
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def run(script: str, hours: float, extra: list[str]) -> int:
    command = [sys.executable, str(ROOT / "work" / script), "--hours", f"{hours:.4f}", *extra]
    print(f"\n=== {script} — jusqu’à {hours:.2f} h disponibles ===", flush=True)
    return subprocess.run(command, cwd=ROOT, check=False).returncode


def main() -> int:
    parser = argparse.ArgumentParser(description="Téléchargement nocturne CHELSA puis pluie CERRA-Land.")
    parser.add_argument("--hours", type=float, default=10.0)
    parser.add_argument("--minimum-free-gb", type=float, default=15.0)
    parser.add_argument("--rain-workers", type=int, default=8)
    args = parser.parse_args()
    started = time.monotonic()
    reserve = ["--minimum-free-gb", str(args.minimum_free_gb)]

    chelsa_code = run("download_overnight.py", args.hours, reserve)
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

    print(f"\nFin de nuit : CHELSA={chelsa_code}, pluie quotidienne={rain_code}", flush=True)
    return 2 if chelsa_code != 0 or rain_code != 0 else 0


if __name__ == "__main__":
    raise SystemExit(main())
