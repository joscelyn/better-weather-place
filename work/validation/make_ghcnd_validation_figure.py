#!/usr/bin/env python3
"""Create a compact visual of the independent station validation."""

from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[2]
data = pd.read_csv(ROOT / "work" / "validation" / "ghcnd_chelsa_comparison_jan_jul.csv")
data = data[data["comparability"].isin(["bonne", "indicative"])].copy()

plt.style.use("seaborn-v0_8-whitegrid")
fig, axes = plt.subplots(2, 2, figsize=(13, 10))
month_names = {1: "janvier", 7: "juillet"}

for column, month in enumerate([1, 7]):
    sample = data[data["month"] == month]
    ax = axes[0, column]
    for quality, marker, color in [
        ("bonne", "o", "#176b87"),
        ("indicative", "^", "#f28e2b"),
    ]:
        part = sample[sample["comparability"] == quality]
        ax.scatter(part["tmean_c"], part["tas"], s=55, marker=marker, color=color, label=quality)
    bounds = [sample[["tmean_c", "tas"]].min().min() - 1, sample[["tmean_c", "tas"]].max().max() + 1]
    ax.plot(bounds, bounds, "--", color="#555", linewidth=1)
    for row in sample.itertuples():
        if abs(row.delta_tmean_c) >= 1.4:
            ax.annotate(row.point, (row.tmean_c, row.tas), xytext=(4, 4), textcoords="offset points", fontsize=8)
    ax.set(xlabel="Station GHCN (°C)", ylabel="CHELSA (°C)", title=f"Température moyenne — {month_names[month]}")
    ax.set_xlim(bounds)
    ax.set_ylim(bounds)
    ax.set_aspect("equal", adjustable="box")
    if column == 0:
        ax.legend(frameon=True)

    ax = axes[1, column]
    rain = sample.dropna(subset=["precipitation_mm", "pr"])
    for quality, marker, color in [
        ("bonne", "o", "#176b87"),
        ("indicative", "^", "#f28e2b"),
    ]:
        part = rain[rain["comparability"] == quality]
        ax.scatter(part["precipitation_mm"], part["pr"], s=55, marker=marker, color=color)
    maximum = max(rain[["precipitation_mm", "pr"]].max().max() * 1.08, 5)
    ax.plot([0, maximum], [0, maximum], "--", color="#555", linewidth=1)
    for row in rain.itertuples():
        if abs(row.pr - row.precipitation_mm) >= 25:
            ax.annotate(row.point, (row.precipitation_mm, row.pr), xytext=(4, 4), textcoords="offset points", fontsize=8)
    ax.set(xlabel="Station GHCN (mm/mois)", ylabel="CHELSA (mm/mois)", title=f"Précipitations — {month_names[month]}")
    ax.set_xlim(-maximum * 0.015, maximum)
    ax.set_ylim(-maximum * 0.015, maximum)
    ax.set_aspect("equal", adjustable="box")

fig.suptitle("Validation indépendante de CHELSA par stations — normales 1991–2020", fontsize=16, fontweight="bold")
fig.text(
    0.5,
    0.015,
    "Cercles : bonne comparabilité · Triangles : comparaison indicative · Les cas non comparables sont exclus",
    ha="center",
    fontsize=10,
)
fig.tight_layout(rect=[0, 0.04, 1, 0.96])
output = ROOT / "outputs" / "validation-stations-ghcnd.png"
fig.savefig(output, dpi=180, bbox_inches="tight")
print(f"Écrit : {output}")
