#!/usr/bin/env python3
"""Plot the twelve-month CHELSA/CERRA-Land precipitation comparison."""

from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[2]
OUTPUTS = ROOT / "outputs"
MONTHS = ["jan", "fév", "mar", "avr", "mai", "juin", "juil", "août", "sep", "oct", "nov", "déc"]
COLORS = {
    "alpes": "#4477AA",
    "pyrenees": "#66CCEE",
    "portugal-galice": "#228833",
    "andalousie": "#CCBB44",
    "maroc": "#EE6677",
    "nord": "#AA3377",
}


def main() -> None:
    comparison = pd.read_csv(OUTPUTS / "comparaison-chelsa-cerra-land-12-mois.csv")
    summary = pd.read_csv(OUTPUTS / "synthese-chelsa-cerra-land-12-mois.csv")
    wet = comparison[comparison["wet_reference_ge_10mm"]].copy()

    plt.style.use("seaborn-v0_8-whitegrid")
    figure, axes = plt.subplots(1, 3, figsize=(17, 5.8), constrained_layout=True)
    figure.suptitle(
        "Précipitations 1991–2020 — CHELSA comparé à CERRA-Land",
        fontsize=17,
        fontweight="bold",
    )

    x = np.arange(12)
    axes[0].fill_between(
        x,
        summary["p10_ratio_wet"],
        summary["p90_ratio_wet"],
        alpha=0.22,
        color="#4477AA",
        label="10e–90e percentile",
    )
    axes[0].plot(
        x,
        summary["median_ratio_wet"],
        marker="o",
        linewidth=2.3,
        color="#225588",
        label="Rapport médian",
    )
    axes[0].axhline(1, color="#555555", linestyle="--", linewidth=1.2)
    axes[0].set_xticks(x, MONTHS, rotation=45)
    axes[0].set_ylabel("CHELSA ÷ CERRA-Land")
    axes[0].set_title("A. Biais relatif stable au fil des mois")
    axes[0].legend(frameon=True, fontsize=9)

    by_point = wet.groupby(["region", "point"], as_index=False).agg(
        median_ratio=("ratio_chelsa_to_cerra_land", "median")
    ).sort_values("median_ratio")
    axes[1].barh(
        by_point["point"],
        by_point["median_ratio"],
        color=[COLORS[region] for region in by_point["region"]],
    )
    axes[1].axvline(1, color="#555555", linestyle="--", linewidth=1.2)
    axes[1].set_xlabel("Rapport médian sur les mois humides")
    axes[1].set_title("B. Les écarts dépendent surtout du terrain")

    for region, sample in wet.groupby("region"):
        axes[2].scatter(
            sample["cerra_land_precipitation_mm"],
            sample["chelsa_precipitation_mm"],
            s=28,
            alpha=0.75,
            color=COLORS[region],
            label=region.replace("-", " "),
        )
    high = max(
        wet["cerra_land_precipitation_mm"].max(),
        wet["chelsa_precipitation_mm"].max(),
    ) * 1.04
    axes[2].plot([0, high], [0, high], color="#555555", linestyle="--", linewidth=1.2)
    axes[2].set_xlim(0, high)
    axes[2].set_ylim(0, high)
    axes[2].set_aspect("equal", adjustable="box")
    axes[2].set_xlabel("CERRA-Land (mm/mois)")
    axes[2].set_ylabel("CHELSA (mm/mois)")
    axes[2].set_title("C. 157 couples avec référence ≥ 10 mm")
    axes[2].legend(frameon=True, fontsize=7.5, loc="upper left")

    figure.text(
        0.5,
        -0.015,
        "14 points terrestres en Europe et dans le bassin méditerranéen. "
        "Canaries exclues de cette phase ; point marin d’Essaouira exclu.",
        ha="center",
        fontsize=9,
        color="#444444",
    )
    output = OUTPUTS / "comparaison-chelsa-cerra-land-12-mois.png"
    figure.savefig(output, dpi=180, bbox_inches="tight", facecolor="white")
    print(output)


if __name__ == "__main__":
    main()
