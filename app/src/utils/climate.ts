import contractJson from "@climate-contract";
import type { ClimateLayer, ColorStop } from "@/types/climate";

type ContractPalette = { stops: [number, string][] };
type ContractLayer = {
  id: string;
  label_fr: string;
  short_label_fr: string;
  unit: string;
  source: string;
  native_resolution: string;
  native_max_zoom: number;
  storage: { scale_factor: number };
  palette?: ContractPalette;
  palette_ref?: string;
};
type ClimateContract = {
  data_version: string;
  months: { number: number; id: string; label_fr: string }[];
  asset_contract: {
    available_layer_ids: string[];
    display_template: string;
    value_template: string;
  };
  layers: ContractLayer[];
};

const contract = contractJson as unknown as ClimateContract;
const layersById = new Map(contract.layers.map(layer => [layer.id, layer]));

function contractLayer(id: string): ContractLayer {
  const layer = layersById.get(id);
  if (!layer) { throw new Error(`Couche absente du contrat de données : ${id}`); }
  return layer;
}

function paletteFor(layer: ContractLayer): readonly ColorStop[] {
  const palette = layer.palette ?? (layer.palette_ref ? contractLayer(layer.palette_ref).palette : undefined);
  if (!palette?.stops.length) { throw new Error(`Palette absente du contrat de données : ${layer.id}`); }
  return palette.stops as ColorStop[];
}

export const climateLayers: readonly ClimateLayer[] = contract.asset_contract.available_layer_ids.map((id) => {
  const layer = contractLayer(id);
  return {
    id: layer.id,
    label: layer.label_fr,
    shortLabel: layer.short_label_fr,
    unit: layer.unit,
    source: layer.source,
    resolution: layer.native_resolution,
    maxZoom: layer.native_max_zoom,
    stops: paletteFor(layer),
  };
});

export const months = contract.months.map(month => month.label_fr);

function dataBaseUrl(): URL {
  const configuredBaseUrl = import.meta.env.VITE_DATA_BASE_URL?.trim();

  if (!configuredBaseUrl) {
    return new URL("/", window.location.href);
  }

  const normalizedBaseUrl = configuredBaseUrl.endsWith("/")
    ? configuredBaseUrl
    : `${configuredBaseUrl}/`;

  return new URL(normalizedBaseUrl);
}

function assetUrl(template: string, layerId: string, month: number): URL {
  const monthId = String(month).padStart(2, "0");
  const relative = template.replace("{layer_id}", layerId).replace("{month}", monthId);
  const url = new URL(relative, dataBaseUrl());
  url.searchParams.set("v", contract.data_version);
  return url;
}

export function climateArchiveUrl(layerId: string, month: number): string {
  return `pmtiles://${assetUrl(contract.asset_contract.display_template, layerId, month).href}`;
}

export function climateValueUrl(layerId: string, month: number): string {
  return assetUrl(contract.asset_contract.value_template, layerId, month).href;
}

export function climateValueScale(layerId: string): number {
  return contractLayer(layerId).storage.scale_factor;
}
