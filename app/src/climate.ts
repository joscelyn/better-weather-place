export type ColorStop = readonly [number, string];

export type ClimateLayer = {
  id: string;
  label: string;
  shortLabel: string;
  unit: string;
  source: string;
  resolution: string;
  maxZoom: number;
  stops: readonly ColorStop[];
};

const temperatureStops = [
  [-40, "#171747"], [-30, "#313695"], [-20, "#4575b4"],
  [-10, "#74add1"], [-5, "#abd9e9"], [0, "#e0f3f8"],
  [5, "#ffffbf"], [10, "#fee090"], [15, "#fdae61"],
  [20, "#f46d43"], [25, "#d73027"], [35, "#a50026"],
  [40, "#67001f"], [50, "#31000f"],
] as const;

export const climateLayers: readonly ClimateLayer[] = [
  {
    id: "tavg",
    label: "Température moyenne",
    shortLabel: "Température",
    unit: "°C",
    source: "CHELSA-monthly V2.1",
    resolution: "environ 1 km",
    maxZoom: 7,
    stops: temperatureStops,
  },
  {
    id: "tmax",
    label: "Moyenne des maximales",
    shortLabel: "Maximales",
    unit: "°C",
    source: "CHELSA-monthly V2.1",
    resolution: "environ 1 km",
    maxZoom: 7,
    stops: temperatureStops,
  },
  {
    id: "tmin",
    label: "Moyenne des minimales",
    shortLabel: "Minimales",
    unit: "°C",
    source: "CHELSA-monthly V2.1",
    resolution: "environ 1 km",
    maxZoom: 7,
    stops: temperatureStops,
  },
  {
    id: "precipitation",
    label: "Précipitations mensuelles",
    shortLabel: "Pluie totale",
    unit: "mm/mois",
    source: "CHELSA-monthly V2.1",
    resolution: "environ 1 km",
    maxZoom: 7,
    stops: [
      [0, "#f7fbff"], [5, "#e3eef9"], [10, "#cfe1f2"],
      [20, "#9ecae1"], [40, "#6baed6"], [60, "#4292c6"],
      [100, "#2171b5"], [150, "#08519c"], [250, "#08306b"],
      [400, "#3f007d"],
    ],
  },
  {
    id: "sunshine",
    label: "Durée d’ensoleillement",
    shortLabel: "Soleil",
    unit: "h/mois",
    source: "SARAH-3 (jusqu’à 65° N)",
    resolution: "environ 5 km",
    maxZoom: 5,
    stops: [
      [0, "#2d1e3e"], [20, "#44345f"], [40, "#5d4d7a"],
      [80, "#786b91"], [120, "#958baa"], [160, "#b3acc0"],
      [200, "#d2cfbe"], [240, "#eee9a9"], [280, "#f6d66f"],
      [320, "#f7b942"], [360, "#f28e2b"], [400, "#d95f0e"],
    ],
  },
] as const;

export const months = [
  "janv.", "févr.", "mars", "avr.", "mai", "juin",
  "juil.", "août", "sept.", "oct.", "nov.", "déc.",
] as const;

export function climateArchiveUrl(layerId: string, month: number): string {
  const relative = `/data/1991-2020/${layerId}/${String(month).padStart(2, "0")}.pmtiles`;
  return `pmtiles://${new URL(relative, window.location.href).href}`;
}
