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
