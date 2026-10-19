#!/usr/bin/env python3
"""Create the diagnostic figure for northern sunshine validation."""

from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[2]
OUTPUTS = ROOT / "outputs"
MONTHS = ["jan", "fév", "mar", "avr", "mai", "juin", "juil", "août", "sep", "oct", "nov", "déc"]


def main() -> None:
    monthly = pd.read_csv(OUTPUTS / "correction-cerra-wmo-ensoleillement-nord.csv")
    overlap = pd.read_csv(OUTPUTS / "correction-ensoleillement-nord.csv")
    stations = pd.read_csv(OUTPUTS / "synthese-stations-ensoleillement-nord.csv")

    plt.style.use("seaborn-v0_8-whitegrid")
    figure, axes = plt.subplots(1, 3, figsize=(17, 5.7), constrained_layout=True)
    figure.suptitle(
        "Ensoleillement au nord de 65° N — validation de CERRA",
        fontsize=17,
        fontweight="bold",
    )

    x = np.arange(12)
    axes[0].plot(x, monthly["mae_raw_hours"], marker="o", linewidth=2.2, label="CERRA brut")
    axes[0].plot(
        x,
        monthly["mae_leave_one_station_out_hours"],
        marker="o",
        linewidth=2.2,
        label="Correction testée hors échantillon",
    )
    axes[0].set_xticks(x, MONTHS, rotation=45)
    axes[0].set_ylabel("Erreur absolue moyenne (h/mois)")
    axes[0].set_title("A. La correction n’est pas stable toute l’année")
    axes[0].legend(frameon=True)

    low = min(stations["wmo_annual_hours"].min(), stations["cerra_annual_hours"].min()) - 80
    high = max(stations["wmo_annual_hours"].max(), stations["cerra_annual_hours"].max()) + 80
    axes[1].plot([low, high], [low, high], linestyle="--", color="#555555", linewidth=1.4)
    axes[1].scatter(
        stations["wmo_annual_hours"],
        stations["cerra_annual_hours"],
        s=52,
        color="#d95f02",
        edgecolor="white",
        linewidth=0.7,
        zorder=3,
    )
    for row in stations.itertuples(index=False):
        label = row.station.replace("_Sol", "").replace("_Aut", "")
        axes[1].annotate(
            label,
            (row.wmo_annual_hours, row.cerra_annual_hours),
            xytext=(4, 3),
            textcoords="offset points",
            fontsize=7.5,
        )
    axes[1].set_xlim(low, high)
    axes[1].set_ylim(low, high)
    axes[1].set_aspect("equal", adjustable="box")
    axes[1].set_xlabel("Stations WMO 1991–2020 (h/an)")
    axes[1].set_ylabel("CERRA 1991–2020 (h/an)")
    axes[1].set_title("B. Le biais dépend fortement du lieu")

    axes[2].plot(
        x,
        overlap["multiplicative_factor"],
        marker="o",
        linewidth=2.2,
        label="Bande 59–63,5° N (SARAH-3)",
    )
    axes[2].plot(
        x,
        monthly["multiplicative_factor"],
        marker="o",
        linewidth=2.2,
        label="Stations 65–70° N (WMO)",
    )
    axes[2].axhline(1, color="#555555", linestyle="--", linewidth=1.2)
    axes[2].set_xticks(x, MONTHS, rotation=45)
    axes[2].set_ylim(0, 1.1)
    axes[2].set_ylabel("Facteur SARAH/WMO ÷ CERRA")
    axes[2].set_title("C. Une couture simple créerait des écarts")
    axes[2].legend(frameon=True, fontsize=8.5)

    figure.text(
        0.5,
        -0.015,
        "Références : normales WMO/NCEI 1991–2020 (10 stations, ≥24 ans) et SARAH-3. "
        "Open-Meteo sert uniquement d’adaptateur de validation CERRA.",
        ha="center",
        fontsize=9,
        color="#444444",
    )
    output = OUTPUTS / "validation-ensoleillement-nord.png"
    figure.savefig(output, dpi=180, bbox_inches="tight", facecolor="white")
    print(output)


if __name__ == "__main__":
    main()
