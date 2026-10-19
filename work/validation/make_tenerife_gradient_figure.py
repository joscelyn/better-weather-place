#!/usr/bin/env python3
"""Visualise the observed and CHELSA elevation gradient over Tenerife."""

from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd


ROOT = Path(__file__).resolve().parents[2]
source = ROOT / "work" / "validation" / "tenerife_altitude_gradient_1991_2020.csv"
frame = pd.read_csv(source)
labels = ["Jan", "Fév", "Mar", "Avr", "Mai", "Juin", "Juil", "Août", "Sep", "Oct", "Nov", "Déc"]

plt.style.use("seaborn-v0_8-whitegrid")
figure, ax = plt.subplots(figsize=(11, 5.8))
ax.axvspan(6.5, 8.5, color="#f28e2b", alpha=0.12, label="juillet–août")
ax.plot(
    frame["month"], frame["station_gradient_c_per_1000m"],
    marker="o", linewidth=2.4, color="#176b87", label="Stations Tenerife Sur–Izaña",
)
ax.plot(
    frame["month"], frame["chelsa_gradient_c_per_1000m"],
    marker="o", linewidth=2.4, color="#d95f59", label="CHELSA aux mêmes coordonnées",
)
ax.axhline(0, color="#444", linewidth=1)
ax.set_xticks(range(1, 13), labels)
ax.set_ylabel("Gradient de température (°C / 1 000 m)")
ax.set_title("Tenerife — contraste côte/haute altitude, normales 1991–2020", fontsize=15, fontweight="bold")
ax.legend(frameon=True, ncol=3, loc="lower center")
ax.text(
    0.01, 0.97,
    "Un gradient moins négatif signifie que la haute altitude se rapproche de la température côtière.",
    transform=ax.transAxes, va="top", fontsize=9.5,
)
figure.tight_layout()
output = ROOT / "outputs" / "controle-gradient-altitudinal-tenerife.png"
figure.savefig(output, dpi=180, bbox_inches="tight")
print(f"Écrit : {output}")
