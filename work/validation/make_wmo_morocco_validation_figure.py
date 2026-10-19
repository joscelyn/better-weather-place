#!/usr/bin/env python3
"""Create the summary figure for WMO-based validation in Morocco."""

from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[2]
OUTPUTS = ROOT / "outputs"
MONTHS = ["jan", "fév", "mar", "avr", "mai", "juin", "juil", "août", "sep", "oct", "nov", "déc"]
TEMP_COLORS = {"TAVG": "#4477AA", "TMAX": "#EE6677", "TMIN": "#228833"}


def main() -> None:
    climate = pd.read_csv(OUTPUTS / "comparaison-chelsa-wmo-maroc.csv")
    rainy = pd.read_csv(OUTPUTS / "comparaison-cerra-land-wmo-jours-pluie-maroc.csv")

    plt.style.use("seaborn-v0_8-whitegrid")
    figure, axes = plt.subplots(2, 2, figsize=(14.5, 10), constrained_layout=True)
    figure.suptitle(
        "Validation climatique au Maroc — normales WMO 1991–2020",
        fontsize=18,
        fontweight="bold",
    )

    temperatures = climate[
        climate["wmo_variable"].isin(TEMP_COLORS) & climate["wmo_value"].notna()
    ]
    low = min(temperatures["wmo_value"].min(), temperatures["chelsa_value"].min()) - 1
    high = max(temperatures["wmo_value"].max(), temperatures["chelsa_value"].max()) + 1
    for variable, sample in temperatures.groupby("wmo_variable"):
        axes[0, 0].scatter(
            sample["wmo_value"],
            sample["chelsa_value"],
            s=18,
            alpha=0.55,
            color=TEMP_COLORS[variable],
            label=variable,
        )
    axes[0, 0].plot([low, high], [low, high], color="#555555", linestyle="--")
    axes[0, 0].set_xlim(low, high)
    axes[0, 0].set_ylim(low, high)
    axes[0, 0].set_aspect("equal", adjustable="box")
    axes[0, 0].set_xlabel("Station WMO (°C)")
    axes[0, 0].set_ylabel("CHELSA (°C)")
    axes[0, 0].set_title("A. Températures mensuelles")
    axes[0, 0].legend(frameon=True)

    for variable, sample in temperatures.groupby("wmo_variable"):
        monthly = sample.groupby("month")["difference_chelsa_minus_wmo"].agg(
            lambda values: float(np.mean(np.abs(values)))
        )
        axes[0, 1].plot(
            np.arange(12),
            monthly,
            marker="o",
            linewidth=2,
            color=TEMP_COLORS[variable],
            label=variable,
        )
    axes[0, 1].set_xticks(np.arange(12), MONTHS, rotation=45)
    axes[0, 1].set_ylabel("Erreur absolue moyenne (°C)")
    axes[0, 1].set_title("B. Erreur thermique selon le mois")
    axes[0, 1].legend(frameon=True)

    precipitation = climate[
        (climate["wmo_variable"] == "PRCP") & climate["wmo_value"].notna()
    ]
    precip_high = max(precipitation["wmo_value"].max(), precipitation["chelsa_value"].max()) * 1.05
    axes[1, 0].scatter(
        precipitation["wmo_value"],
        precipitation["chelsa_value"],
        s=25,
        alpha=0.65,
        color="#4477AA",
    )
    axes[1, 0].plot([0, precip_high], [0, precip_high], color="#555555", linestyle="--")
    axes[1, 0].set_xlim(0, precip_high)
    axes[1, 0].set_ylim(0, precip_high)
    axes[1, 0].set_aspect("equal", adjustable="box")
    axes[1, 0].set_xlabel("Station WMO (mm/mois)")
    axes[1, 0].set_ylabel("CHELSA (mm/mois)")
    axes[1, 0].set_title("C. Précipitations mensuelles")

    regular = rainy[rainy["station"] != "IFRANE"]
    ifrane = rainy[rainy["station"] == "IFRANE"]
    axes[1, 1].scatter(
        regular["wmo_rainy_days_ge_1mm"],
        regular["cerra_land_rainy_days"],
        s=25,
        alpha=0.65,
        color="#228833",
        label="24 stations",
    )
    axes[1, 1].scatter(
        ifrane["wmo_rainy_days_ge_1mm"],
        ifrane["cerra_land_rainy_days"],
        s=42,
        color="#CC3311",
        label="Ifrane",
        zorder=3,
    )
    rain_high = max(
        rainy["wmo_rainy_days_ge_1mm"].max(), rainy["cerra_land_rainy_days"].max()
    ) * 1.08
    axes[1, 1].plot([0, rain_high], [0, rain_high], color="#555555", linestyle="--")
    axes[1, 1].set_xlim(0, rain_high)
    axes[1, 1].set_ylim(0, rain_high)
    axes[1, 1].set_aspect("equal", adjustable="box")
    axes[1, 1].set_xlabel("Station WMO (jours/mois ≥ 1 mm)")
    axes[1, 1].set_ylabel("CERRA-Land (jours/mois ≥ 1 mm)")
    axes[1, 1].set_title("D. Jours de pluie — Ifrane ressort nettement")
    axes[1, 1].legend(frameon=True)

    figure.text(
        0.5,
        -0.01,
        "25 stations WMO marocaines ; CHELSA ≈ 1 km, CERRA-Land 5,5 km. "
        "Contrôle limité au Maroc, sans traitement des Canaries.",
        ha="center",
        fontsize=9,
        color="#444444",
    )
    output = OUTPUTS / "validation-wmo-maroc.png"
    figure.savefig(output, dpi=180, bbox_inches="tight", facecolor="white")
    print(output)


if __name__ == "__main__":
    main()
