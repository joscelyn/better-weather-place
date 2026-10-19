#!/usr/bin/env python3
"""Create a compact diagnostic figure for the phase-1 source comparison."""

from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[2]
data = pd.read_csv(ROOT / "work" / "validation" / "comparison_phase1_jan_jul.csv")

regions = list(data["region"].unique())
palette = plt.get_cmap("tab10")
colors = {region: palette(index) for index, region in enumerate(regions)}

fig, axes = plt.subplots(1, 3, figsize=(15, 6.2))
fig.subplots_adjust(left=0.055, right=0.985, top=0.82, bottom=0.22, wspace=0.27)


def scatter_by_region(axis, x, y):
    for region in regions:
        subset = data[data["region"] == region]
        axis.scatter(
            subset[x],
            subset[y],
            s=42,
            alpha=0.82,
            color=colors[region],
            edgecolor="white",
            linewidth=0.5,
            label=region,
        )


# Temperature comparison
ax = axes[0]
scatter_by_region(ax, "cerra_tmean_c", "tas")
lo = min(data["cerra_tmean_c"].min(), data["tas"].min()) - 1
hi = max(data["cerra_tmean_c"].max(), data["tas"].max()) + 1
ax.plot([lo, hi], [lo, hi], color="#344054", linestyle="--", linewidth=1)
ax.set(xlim=(lo, hi), ylim=(lo, hi), xlabel="CERRA 5,5 km (°C)", ylabel="CHELSA ≈1 km (°C)")
ax.set_title("Température moyenne\njanvier et juillet")
for _, row in data[data["delta_tmean_chelsa_minus_cerra_c"].abs() > 3].iterrows():
    ax.annotate(row["point"], (row["cerra_tmean_c"], row["tas"]), fontsize=7, xytext=(3, 3), textcoords="offset points")

# Precipitation comparison
ax = axes[1]
scatter_by_region(ax, "cerra_land_precip_mm", "chelsa_precip_1991_2020_mm")
limit = max(
    data["cerra_land_precip_mm"].max(),
    data["chelsa_precip_1991_2020_mm"].max(),
) * 1.06
ax.plot([0, limit], [0, limit], color="#344054", linestyle="--", linewidth=1)
ax.set(xlim=(0, limit), ylim=(0, limit), xlabel="CERRA-Land 5,5 km (mm/mois)", ylabel="CHELSA ≈1 km (mm/mois)")
ax.set_title("Précipitations mensuelles\njanvier et juillet")
for _, row in data[
    (data["precip_ratio_chelsa_to_cerra_land_official"] < 0.5)
    | (data["precip_ratio_chelsa_to_cerra_land_official"] > 1.8)
].iterrows():
    ax.annotate(
        row["point"],
        (row["cerra_land_precip_mm"], row["chelsa_precip_1991_2020_mm"]),
        fontsize=7,
        xytext=(3, 3),
        textcoords="offset points",
    )

# Sunshine comparison
ax = axes[2]
sun = data.dropna(subset=["sunshine_hours_sarah3", "cerra_sunshine_hours"])
for region in regions:
    subset = sun[sun["region"] == region]
    ax.scatter(
        subset["cerra_sunshine_hours"],
        subset["sunshine_hours_sarah3"],
        s=42,
        alpha=0.82,
        color=colors[region],
        edgecolor="white",
        linewidth=0.5,
    )
limit = max(sun["cerra_sunshine_hours"].max(), sun["sunshine_hours_sarah3"].max()) * 1.06
ax.plot([0, limit], [0, limit], color="#344054", linestyle="--", linewidth=1)
ax.set(xlim=(0, limit), ylim=(0, limit), xlabel="CERRA dérivé (h/mois)", ylabel="SARAH-3 satellite (h/mois)")
ax.set_title("Durée d’ensoleillement\ncontrôle indicatif")
for _, row in sun[(sun["sunshine_hours_sarah3"] - sun["cerra_sunshine_hours"]).abs() > 80].iterrows():
    ax.annotate(row["point"], (row["cerra_sunshine_hours"], row["sunshine_hours_sarah3"]), fontsize=7, xytext=(3, 3), textcoords="offset points")

for axis in axes:
    axis.grid(True, color="#e4e7ec", linewidth=0.7)
    axis.set_facecolor("#fafafa")

handles, labels = axes[0].get_legend_handles_labels()
fig.legend(handles, labels, loc="lower center", ncol=4, fontsize=8, frameon=False, bbox_to_anchor=(0.5, 0.075))
fig.suptitle("Étape 1 — comparaison exploratoire des sources", fontsize=16, fontweight="bold")
fig.text(
    0.5,
    0.025,
    "Température : CHELSA/CERRA 1991–2005. Pluie : CHELSA/CERRA-Land officiel 1991–2020. Soleil : SARAH-3 1991–2020 comparé à CERRA 1991–2005.",
    ha="center",
    fontsize=8,
    color="#475467",
)

output = ROOT / "outputs" / "diagnostic-sources-etape-1.png"
fig.savefig(output, dpi=180, bbox_inches="tight", facecolor="white")
print(output)
