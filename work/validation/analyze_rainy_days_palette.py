#!/usr/bin/env python3
"""Audit the rainy-day palette using all available 1991-2020 reference series."""

from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[2]
OUTPUT = ROOT / "outputs"
MONTH_LABELS = [
    "jan", "fév", "mar", "avr", "mai", "juin",
    "juil", "août", "sep", "oct", "nov", "déc",
]
EDGES = np.array([0, 1, 2, 4, 6, 8, 10, 15, 20, 25, 31.000001], dtype="float64")
COLORS = [
    "#fff7fb", "#ece7f2", "#d0d1e6", "#a6bddb", "#74a9cf",
    "#3690c0", "#0570b0", "#045a8d", "#023858", "#081d58",
]


def standardize(
    frame: pd.DataFrame,
    source: str,
    point_column: str,
    value_column: str,
) -> pd.DataFrame:
    result = frame[[point_column, "month", value_column]].copy()
    result.columns = ["point", "month", "rainy_days_ge_1mm"]
    result.insert(0, "source", source)
    return result.dropna(subset=["rainy_days_ge_1mm"])


def load_samples() -> pd.DataFrame:
    ghcnd = pd.read_csv(OUTPUT / "normales-stations-ghcnd-1991-2020.csv")
    ghcnd = ghcnd[ghcnd["region"] != "canaries"].copy()
    ghcnd["sample"] = ghcnd["region"] + " / " + ghcnd["point"]

    cerra = pd.read_csv(OUTPUT / "normales-cerra-land-1991-2020.csv")
    cerra = cerra[cerra["region"] != "canaries"].copy()
    cerra["sample"] = cerra["region"] + " / " + cerra["point"]

    morocco = pd.read_csv(OUTPUT / "comparaison-cerra-land-wmo-jours-pluie-maroc.csv")
    morocco["sample"] = "Maroc / " + morocco["station"]

    frames = [
        standardize(ghcnd, "Stations GHCN", "sample", "rain_days_ge_1mm"),
        standardize(cerra, "CERRA-Land — points européens", "sample", "rainy_days_ge_1mm"),
        standardize(morocco, "CERRA-Land — stations marocaines", "sample", "cerra_land_rainy_days"),
        standardize(morocco, "Normales WMO — stations marocaines", "sample", "wmo_rainy_days_ge_1mm"),
    ]
    combined = pd.concat(frames, ignore_index=True)
    if not combined["rainy_days_ge_1mm"].between(0, 31).all():
        raise RuntimeError("Rainy-day normal outside the physical 0-31 day range")
    return combined


def interval_label(left: float, right: float) -> str:
    if right > 31:
        return f"{left:g} à 31"
    return f"{left:g} à < {right:g}"


def main() -> None:
    samples = load_samples()
    samples.to_csv(OUTPUT / "analyse-palette-jours-pluie.csv", index=False)

    summary = (
        samples.groupby(["source", "month"])["rainy_days_ge_1mm"]
        .agg(
            sample_count="count",
            minimum="min",
            p10=lambda values: values.quantile(0.10),
            median="median",
            p90=lambda values: values.quantile(0.90),
            maximum="max",
        )
        .reset_index()
    )
    summary["above_25_count"] = (
        samples.assign(above=samples["rainy_days_ge_1mm"] > 25)
        .groupby(["source", "month"])["above"]
        .sum()
        .to_numpy()
    )
    summary.to_csv(OUTPUT / "synthese-palette-jours-pluie.csv", index=False)

    counts, _ = np.histogram(samples["rainy_days_ge_1mm"], bins=EDGES)
    occupancy = pd.DataFrame(
        {
            "interval": [interval_label(a, b) for a, b in zip(EDGES[:-1], EDGES[1:])],
            "sample_count": counts,
            "percent": 100 * counts / counts.sum(),
        }
    )
    occupancy.to_csv(OUTPUT / "occupation-palette-jours-pluie.csv", index=False)

    figure, axes = plt.subplots(2, 1, figsize=(12, 9), constrained_layout=True)
    styles = {
        "Stations GHCN": ("#7b3294", "o"),
        "CERRA-Land — points européens": ("#008837", "s"),
        "CERRA-Land — stations marocaines": ("#2c7fb8", "^"),
        "Normales WMO — stations marocaines": ("#d95f0e", "D"),
    }
    for source, data in summary.groupby("source"):
        color, marker = styles[source]
        axes[0].plot(data["month"], data["maximum"], color=color, marker=marker, label=source)
    axes[0].axhline(25, color="#081d58", linestyle="--", linewidth=1.2, label="borne actuelle 25 jours")
    axes[0].axhline(31, color="#020617", linestyle=":", linewidth=1.2, label="maximum physique 31 jours")
    axes[0].set_xticks(range(1, 13), MONTH_LABELS)
    axes[0].set_ylim(0, 32)
    axes[0].set_ylabel("maximum observé (jours/mois)")
    axes[0].set_title("Maximum mensuel par jeu de référence")
    axes[0].legend(loc="upper right", ncols=2, fontsize=8)
    axes[0].grid(axis="y", alpha=0.18)

    month_values = [
        samples.loc[samples["month"] == month, "rainy_days_ge_1mm"].to_numpy()
        for month in range(1, 13)
    ]
    box = axes[1].boxplot(month_values, positions=range(1, 13), patch_artist=True, showfliers=True)
    for patch in box["boxes"]:
        patch.set_facecolor("#74a9cf")
        patch.set_alpha(0.65)
    for median in box["medians"]:
        median.set_color("#081d58")
        median.set_linewidth(1.8)
    axes[1].set_xticks(range(1, 13), MONTH_LABELS)
    axes[1].set_ylim(0, 32)
    axes[1].set_ylabel("jours avec au moins 1 mm")
    axes[1].set_title("Distribution des séries de référence combinées")
    axes[1].grid(axis="y", alpha=0.18)

    figure.suptitle("Audit de la palette — nombre moyen de jours de pluie 1991–2020", fontsize=15)
    figure.savefig(OUTPUT / "analyse-palette-jours-pluie.png", dpi=180)
    plt.close(figure)

    print(f"Séries mensuelles: {len(samples)}")
    print(f"Points distincts par source:\n{samples.groupby('source').point.nunique().to_string()}")
    print(f"Plage: {samples.rainy_days_ge_1mm.min():.2f} à {samples.rainy_days_ge_1mm.max():.2f} jours/mois")
    print(summary.to_string(index=False))


if __name__ == "__main__":
    main()
