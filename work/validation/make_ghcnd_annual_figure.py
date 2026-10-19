#!/usr/bin/env python3
"""Plot monthly independent-validation diagnostics for CHELSA."""

from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd


ROOT = Path(__file__).resolve().parents[2]
frame = pd.read_csv(ROOT / "work" / "validation" / "ghcnd_chelsa_comparison_1991_2020.csv")
frame = frame[frame["comparability"].isin(["bonne", "indicative"])].copy()
month_labels = ["Jan", "Fév", "Mar", "Avr", "Mai", "Juin", "Juil", "Août", "Sep", "Oct", "Nov", "Déc"]

temp = frame.dropna(subset=["delta_tmean_c"])
temp_monthly = temp.groupby("month")["delta_tmean_c"].agg(
    bias="mean", mae=lambda values: values.abs().mean()
).reindex(range(1, 13))

rain = frame.dropna(subset=["precipitation_mm", "pr"])
wet = rain[rain["precipitation_mm"] >= 10.0]
rain_monthly = wet.groupby("month").agg(
    median_ratio=("precipitation_ratio", "median"),
    pairs=("precipitation_ratio", "count"),
).reindex(range(1, 13))

point_temp = temp.groupby("point")["delta_tmean_c"].apply(lambda values: values.abs().mean()).sort_values()

plt.style.use("seaborn-v0_8-whitegrid")
fig, axes = plt.subplots(2, 2, figsize=(14, 9))

ax = axes[0, 0]
ax.bar(month_labels, temp_monthly["bias"], color=["#cf5c5c" if v < 0 else "#2d8bba" for v in temp_monthly["bias"]])
ax.axhline(0, color="#444", linewidth=1)
ax.set(title="Biais mensuel de température", ylabel="CHELSA − station (°C)")

ax = axes[0, 1]
ax.plot(month_labels, temp_monthly["mae"], marker="o", color="#176b87", linewidth=2)
ax.set_ylim(0, max(1.1, temp_monthly["mae"].max() * 1.15))
ax.set(title="Erreur absolue moyenne", ylabel="°C")

ax = axes[1, 0]
ax.plot(month_labels, rain_monthly["median_ratio"], marker="o", color="#4b8f3a", linewidth=2)
ax.axhline(1, color="#444", linestyle="--", linewidth=1)
for index, (ratio, pairs) in enumerate(zip(rain_monthly["median_ratio"], rain_monthly["pairs"])):
    ax.annotate(f"n={int(pairs)}", (index, ratio), xytext=(0, 8), textcoords="offset points", ha="center", fontsize=8)
ax.set_ylim(0.8, max(1.5, rain_monthly["median_ratio"].max() * 1.12))
ax.set(title="Rapport médian des précipitations (mois ≥ 10 mm)", ylabel="CHELSA / station")

ax = axes[1, 1]
colors = ["#f28e2b" if point in {"Faro", "Reykjavik"} else "#176b87" for point in point_temp.index]
ax.barh(point_temp.index, point_temp.values, color=colors)
ax.set(title="Erreur moyenne par point — 12 mois", xlabel="Erreur absolue moyenne (°C)")

fig.suptitle("Validation indépendante CHELSA–GHCN · normales mensuelles 1991–2020", fontsize=16, fontweight="bold")
fig.text(
    0.5, 0.012,
    "10 points comparables · Orange : comparaison indicative · Les 8 cas non comparables sont exclus",
    ha="center", fontsize=10,
)
fig.tight_layout(rect=[0, 0.04, 1, 0.95])
output = ROOT / "outputs" / "validation-stations-ghcnd-12-mois.png"
fig.savefig(output, dpi=180, bbox_inches="tight")
print(f"Écrit : {output}")
