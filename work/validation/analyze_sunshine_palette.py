#!/usr/bin/env python3
"""Audit the sunshine palette using available 1991-2020 reference series."""

from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[2]
OUTPUT = ROOT / "outputs"
VALIDATION = ROOT / "work" / "validation"
MONTH_LABELS = [
    "jan", "fév", "mar", "avr", "mai", "juin",
    "juil", "août", "sep", "oct", "nov", "déc",
]
STOPS = np.array([0, 20, 40, 80, 120, 160, 200, 240, 280, 320, 360, 400], dtype="float64")
EDGES = np.append(STOPS, 400.000001)


def standardize(
    frame: pd.DataFrame,
    source: str,
    point_column: str,
    value_column: str,
    role: str,
) -> pd.DataFrame:
    result = frame[[point_column, "month", value_column]].copy()
    result.columns = ["point", "month", "sunshine_hours"]
    result.insert(0, "role", role)
    result.insert(0, "source", source)
    return result.dropna(subset=["sunshine_hours"])


def load_samples() -> pd.DataFrame:
    sarah = pd.read_csv(VALIDATION / "sarah3_sunshine_normals_points.csv")
    sarah = sarah[(sarah["region"] != "canaries") & (sarah["coverage_status"] == "available")].copy()
    sarah["sample"] = sarah["region"] + " / " + sarah["point"]

    north = pd.read_csv(OUTPUT / "comparaison-cerra-wmo-ensoleillement-nord.csv")
    frames = [
        standardize(
            sarah, "SARAH-3 — domaine principal", "sample", "sunshine_hours_sarah3", "source affichée"
        ),
        standardize(
            north,
            "CERRA — complément nordique brut",
            "station",
            "cerra_1991_2020_hours",
            "source affichée indicative",
        ),
        standardize(
            north,
            "Normales WMO — contrôle nordique",
            "station",
            "wmo_1991_2020_hours",
            "contrôle indépendant",
        ),
    ]
    combined = pd.concat(frames, ignore_index=True)
    if not combined["sunshine_hours"].between(0, 744).all():
        raise RuntimeError("Sunshine normal outside the physical 0-744 hour range")
    return combined


def interval_label(left: float, right: float) -> str:
    if right > 400:
        return f"{left:g} à 400"
    return f"{left:g} à < {right:g}"


def main() -> None:
    samples = load_samples()
    samples.to_csv(OUTPUT / "analyse-palette-ensoleillement.csv", index=False)

    summary = (
        samples.groupby(["source", "month"])["sunshine_hours"]
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
    summary["above_400_count"] = (
        samples.assign(above=samples["sunshine_hours"] > 400)
        .groupby(["source", "month"])["above"]
        .sum()
        .to_numpy()
    )
    summary.to_csv(OUTPUT / "synthese-palette-ensoleillement.csv", index=False)

    counts, _ = np.histogram(samples["sunshine_hours"], bins=EDGES)
    occupancy = pd.DataFrame(
        {
            "interval": [interval_label(a, b) for a, b in zip(EDGES[:-1], EDGES[1:])],
            "sample_count": counts,
            "percent": 100 * counts / counts.sum(),
        }
    )
    occupancy.to_csv(OUTPUT / "occupation-palette-ensoleillement.csv", index=False)

    figure, axes = plt.subplots(2, 1, figsize=(12, 9), constrained_layout=True)
    styles = {
        "SARAH-3 — domaine principal": ("#d95f0e", "o"),
        "CERRA — complément nordique brut": ("#5d4d7a", "s"),
        "Normales WMO — contrôle nordique": ("#2c7fb8", "^"),
    }
    for source, data in summary.groupby("source"):
        color, marker = styles[source]
        axes[0].plot(data["month"], data["maximum"], color=color, marker=marker, label=source)
    axes[0].axhline(400, color="#7f2704", linestyle="--", linewidth=1.2, label="borne de palette 400 h")
    axes[0].set_xticks(range(1, 13), MONTH_LABELS)
    axes[0].set_ylim(0, 420)
    axes[0].set_ylabel("maximum observé (h/mois)")
    axes[0].set_title("Maximum mensuel par jeu de référence")
    axes[0].legend(loc="upper left", ncols=2, fontsize=8)
    axes[0].grid(axis="y", alpha=0.18)

    month_values = [
        samples.loc[samples["month"] == month, "sunshine_hours"].to_numpy()
        for month in range(1, 13)
    ]
    box = axes[1].boxplot(month_values, positions=range(1, 13), patch_artist=True, showfliers=True)
    for patch in box["boxes"]:
        patch.set_facecolor("#f6d66f")
        patch.set_alpha(0.72)
    for median in box["medians"]:
        median.set_color("#7f2704")
        median.set_linewidth(1.8)
    axes[1].axhline(400, color="#7f2704", linestyle="--", linewidth=1.2)
    axes[1].set_xticks(range(1, 13), MONTH_LABELS)
    axes[1].set_ylim(0, 420)
    axes[1].set_ylabel("durée d’ensoleillement (h/mois)")
    axes[1].set_title("Distribution des séries de référence combinées")
    axes[1].grid(axis="y", alpha=0.18)

    figure.suptitle("Audit de la palette — durée d’ensoleillement 1991–2020", fontsize=15)
    figure.savefig(OUTPUT / "analyse-palette-ensoleillement.png", dpi=180)
    plt.close(figure)

    print(f"Valeurs mensuelles : {len(samples)}")
    print(f"Points distincts par source :\n{samples.groupby('source').point.nunique().to_string()}")
    print(f"Plage : {samples.sunshine_hours.min():.2f} à {samples.sunshine_hours.max():.2f} h/mois")
    print(f"Au-dessus de 400 h : {(samples.sunshine_hours > 400).sum()}")
    print(summary.to_string(index=False))


if __name__ == "__main__":
    main()
