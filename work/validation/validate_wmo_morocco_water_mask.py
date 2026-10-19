#!/usr/bin/env python3
"""Check the Copernicus water mask around Moroccan WMO stations."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from validate_copdem_water_mask import analyse_point


ROOT = Path(__file__).resolve().parents[2]


def main() -> None:
    stations = pd.read_csv(
        ROOT / "outputs" / "stations-wmo-maroc-1991-2020.csv",
        dtype={"wmo_id": str},
    )
    rows = []
    for station in stations.itertuples(index=False):
        result = analyse_point(station.latitude, station.longitude)
        rows.append(
            {
                "wmo_id": station.wmo_id,
                "station": station.station,
                "latitude": station.latitude,
                "longitude": station.longitude,
                "elevation_m": station.elevation_m,
                **result,
            }
        )
        print(
            f"{station.station}: {result['surface']}, "
            f"terre dans 1 km {result['land_fraction_approx_1km']:.1%}",
            flush=True,
        )

    output = ROOT / "outputs" / "controle-masque-eau-stations-wmo-maroc.csv"
    pd.DataFrame(rows).to_csv(output, index=False)
    print(f"Écrit : {output}")


if __name__ == "__main__":
    main()
