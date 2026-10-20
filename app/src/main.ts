import maplibregl, { type Map as MapLibreMap, type StyleSpecification } from "maplibre-gl";
import "maplibre-gl/dist/maplibre-gl.css";
import { Protocol } from "pmtiles";
import { climateArchiveUrl, climateLayers, months, type ClimateLayer } from "./climate";
import "./style.css";

const CLIMATE_SOURCE = "climate-source";
const CLIMATE_LAYER = "climate-layer";
const BASEMAP_STYLE = "https://tiles.openfreemap.org/styles/bright";
const STORAGE_KEY = "better-weather-place:map-state:v1";

type SavedState = {
  layerId: string;
  month: number;
  opacity: number;
  center: [number, number];
  zoom: number;
};

const defaultState: SavedState = {
  layerId: "tavg",
  month: 1,
  opacity: 0.76,
  center: [9, 46],
  zoom: 3.25,
};

function loadState(): SavedState {
  try {
    const candidate = JSON.parse(localStorage.getItem(STORAGE_KEY) ?? "null") as Partial<SavedState> | null;
    if (!candidate) return defaultState;
    const layerId = climateLayers.some((layer) => layer.id === candidate.layerId)
      ? candidate.layerId!
      : defaultState.layerId;
    const month = Number.isInteger(candidate.month) && candidate.month! >= 1 && candidate.month! <= 12
      ? candidate.month!
      : defaultState.month;
    const opacity = typeof candidate.opacity === "number" && candidate.opacity >= 0.25 && candidate.opacity <= 1
      ? candidate.opacity
      : defaultState.opacity;
    const center = Array.isArray(candidate.center)
      && candidate.center.length === 2
      && candidate.center.every((coordinate) => typeof coordinate === "number" && Number.isFinite(coordinate))
      ? candidate.center as [number, number]
      : defaultState.center;
    const zoom = typeof candidate.zoom === "number" && candidate.zoom >= 2.4 && candidate.zoom <= 10
      ? candidate.zoom
      : defaultState.zoom;
    return { layerId, month, opacity, center, zoom };
  } catch {
    return defaultState;
  }
}

const initialState = loadState();

let selectedLayer = climateLayers.find((layer) => layer.id === initialState.layerId) ?? climateLayers[0];
let selectedMonth = initialState.month;
let opacity = initialState.opacity;
let map: MapLibreMap;
let activeSourceId: string | undefined;
let mapReady = false;

const protocol = new Protocol();
maplibregl.addProtocol("pmtiles", protocol.tile);

document.querySelector<HTMLDivElement>("#app")!.innerHTML = `
  <main class="shell">
    <div id="map" aria-label="Carte climatique interactive"></div>

    <header class="brand-card glass">
      <div class="brand-mark" aria-hidden="true"><span></span></div>
      <div>
        <p class="eyebrow">Normales 1991–2020</p>
        <h1>Better Weather Place</h1>
      </div>
    </header>

    <section class="control-card glass" aria-label="Choix de la donnée climatique">
      <label for="variable">Afficher</label>
      <div class="select-wrap">
        <select id="variable"></select>
        <span aria-hidden="true">⌄</span>
      </div>
      <div class="current-summary">
        <strong id="current-label"></strong>
        <span id="current-meta"></span>
      </div>
      <label class="opacity-row" for="opacity">
        <span>Intensité</span><output id="opacity-value">76 %</output>
      </label>
      <input id="opacity" type="range" min="25" max="100" value="76" />
    </section>

    <aside class="legend-card glass" aria-label="Légende">
      <div id="legend-unit"></div>
      <div class="legend-scale">
        <div id="legend-gradient" class="legend-gradient"></div>
        <div id="legend-labels" class="legend-labels"></div>
      </div>
    </aside>

    <section id="place-card" class="place-card glass" aria-live="polite">
      <button id="close-place" aria-label="Fermer">×</button>
      <p class="eyebrow">Point sélectionné</p>
      <h2 id="place-title">Explorer la carte</h2>
      <p id="place-copy">Clique sur une zone pour conserver ses coordonnées et le contexte de la donnée.</p>
      <dl>
        <div><dt>Source</dt><dd id="place-source"></dd></div>
        <div><dt>Résolution</dt><dd id="place-resolution"></dd></div>
      </dl>
      <p class="prototype-note">La lecture numérique précise depuis le COG sera branchée après la maquette.</p>
    </section>

    <nav class="month-dock glass" aria-label="Choix du mois">
      <button id="previous-month" class="month-arrow" aria-label="Mois précédent">←</button>
      <div id="months" class="months"></div>
      <button id="next-month" class="month-arrow" aria-label="Mois suivant">→</button>
    </nav>

    <div id="status" class="status-chip">Chargement de la carte…</div>
  </main>
`;

const variableSelect = document.querySelector<HTMLSelectElement>("#variable")!;
const monthsElement = document.querySelector<HTMLDivElement>("#months")!;
const statusElement = document.querySelector<HTMLDivElement>("#status")!;
const placeCard = document.querySelector<HTMLElement>("#place-card")!;

function saveState(): void {
  const center = map?.getCenter();
  const state: SavedState = {
    layerId: selectedLayer.id,
    month: selectedMonth,
    opacity,
    center: center ? [center.lng, center.lat] : initialState.center,
    zoom: map ? map.getZoom() : initialState.zoom,
  };
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(state));
  } catch {
    // La carte reste utilisable lorsque le stockage local est désactivé.
  }
}

for (const layer of climateLayers) {
  const option = document.createElement("option");
  option.value = layer.id;
  option.textContent = layer.label;
  variableSelect.append(option);
}
const pendingOption = document.createElement("option");
pendingOption.disabled = true;
pendingOption.textContent = "Jours de pluie — téléchargement en cours";
variableSelect.append(pendingOption);

months.forEach((label, index) => {
  const button = document.createElement("button");
  button.type = "button";
  button.dataset.month = String(index + 1);
  button.textContent = label;
  button.addEventListener("click", () => selectMonth(index + 1));
  monthsElement.append(button);
});

function firstOverlayLayer(style: StyleSpecification): string | undefined {
  return style.layers?.find((layer) => layer.type === "line" || layer.type === "symbol")?.id;
}

function addClimateLayer(): void {
  if (!mapReady) return;
  const nextSourceId = `${CLIMATE_SOURCE}-${selectedLayer.id}-${String(selectedMonth).padStart(2, "0")}`;
  const previousSourceId = activeSourceId;
  activeSourceId = nextSourceId;
  if (map.getLayer(CLIMATE_LAYER)) map.removeLayer(CLIMATE_LAYER);
  if (previousSourceId && map.getSource(previousSourceId)) map.removeSource(previousSourceId);
  map.addSource(nextSourceId, {
    type: "raster",
    url: climateArchiveUrl(selectedLayer.id, selectedMonth),
    tileSize: 256,
    maxzoom: selectedLayer.maxZoom,
    attribution: selectedLayer.source,
  });
  map.addLayer(
    {
      id: CLIMATE_LAYER,
      type: "raster",
      source: nextSourceId,
      paint: {
        "raster-opacity": opacity,
        "raster-fade-duration": 180,
        "raster-resampling": "linear",
      },
    },
    firstOverlayLayer(map.getStyle()),
  );
  statusElement.textContent = `Chargement · ${selectedLayer.shortLabel} · ${months[selectedMonth - 1]}`;
  statusElement.classList.remove("ready");
  preloadAdjacentMonths();
}

function gradientFor(layer: ClimateLayer): string {
  const low = layer.stops[0][0];
  const high = layer.stops.at(-1)![0];
  return `linear-gradient(to top, ${layer.stops.map(([value, color]) => {
    const percent = ((value - low) / (high - low)) * 100;
    return `${color} ${percent.toFixed(2)}%`;
  }).join(", ")})`;
}

function renderLegend(): void {
  const stops = selectedLayer.stops;
  document.querySelector<HTMLDivElement>("#legend-unit")!.textContent = selectedLayer.unit;
  document.querySelector<HTMLDivElement>("#legend-gradient")!.style.background = gradientFor(selectedLayer);
  const labelIndexes = [stops.length - 1, Math.round((stops.length - 1) * 0.75), Math.round((stops.length - 1) * 0.5), Math.round((stops.length - 1) * 0.25), 0];
  document.querySelector<HTMLDivElement>("#legend-labels")!.innerHTML = labelIndexes
    .map((index) => `<span>${stops[index][0]}</span>`).join("");
}

function renderControls(): void {
  variableSelect.value = selectedLayer.id;
  const opacityInput = document.querySelector<HTMLInputElement>("#opacity")!;
  opacityInput.value = String(Math.round(opacity * 100));
  document.querySelector<HTMLOutputElement>("#opacity-value")!.value = `${Math.round(opacity * 100)} %`;
  document.querySelector<HTMLDivElement>("#current-label")!.textContent = selectedLayer.label;
  document.querySelector<HTMLSpanElement>("#current-meta")!.textContent = `${selectedLayer.resolution} · ${selectedLayer.source}`;
  document.querySelector<HTMLElement>("#place-source")!.textContent = selectedLayer.source;
  document.querySelector<HTMLElement>("#place-resolution")!.textContent = selectedLayer.resolution;
  monthsElement.querySelectorAll("button").forEach((button) => {
    const active = Number((button as HTMLButtonElement).dataset.month) === selectedMonth;
    button.classList.toggle("active", active);
    button.setAttribute("aria-current", active ? "date" : "false");
    if (active) button.scrollIntoView({ behavior: "smooth", inline: "center", block: "nearest" });
  });
  renderLegend();
}

function selectMonth(month: number): void {
  selectedMonth = ((month - 1 + 12) % 12) + 1;
  renderControls();
  saveState();
  addClimateLayer();
}

function preloadAdjacentMonths(): void {
  for (const month of [selectedMonth === 1 ? 12 : selectedMonth - 1, selectedMonth === 12 ? 1 : selectedMonth + 1]) {
    const url = climateArchiveUrl(selectedLayer.id, month).replace("pmtiles://", "");
    void fetch(url, { headers: { Range: "bytes=0-16383" } }).catch(() => undefined);
  }
}

variableSelect.addEventListener("change", () => {
  selectedLayer = climateLayers.find((layer) => layer.id === variableSelect.value) ?? climateLayers[0];
  renderControls();
  saveState();
  addClimateLayer();
});
document.querySelector<HTMLInputElement>("#opacity")!.addEventListener("input", (event) => {
  opacity = Number((event.target as HTMLInputElement).value) / 100;
  document.querySelector<HTMLOutputElement>("#opacity-value")!.value = `${Math.round(opacity * 100)} %`;
  if (map?.getLayer(CLIMATE_LAYER)) map.setPaintProperty(CLIMATE_LAYER, "raster-opacity", opacity);
  saveState();
});
document.querySelector<HTMLButtonElement>("#previous-month")!.addEventListener("click", () => selectMonth(selectedMonth - 1));
document.querySelector<HTMLButtonElement>("#next-month")!.addEventListener("click", () => selectMonth(selectedMonth + 1));
document.querySelector<HTMLButtonElement>("#close-place")!.addEventListener("click", () => placeCard.classList.remove("visible"));

map = new maplibregl.Map({
  container: "map",
  style: BASEMAP_STYLE,
  center: initialState.center,
  zoom: initialState.zoom,
  minZoom: 2.4,
  maxZoom: 10,
  maxBounds: [[-31, 20], [51, 75]],
  attributionControl: false,
});
map.addControl(new maplibregl.NavigationControl({ showCompass: false }), "top-right");
map.addControl(new maplibregl.AttributionControl({ compact: true }), "bottom-right");
map.on("load", () => {
  mapReady = true;
  addClimateLayer();
});
map.on("sourcedata", (event) => {
  if (!activeSourceId || event.sourceId !== activeSourceId) return;
  statusElement.textContent = `${selectedLayer.shortLabel} · ${months[selectedMonth - 1]}`;
  statusElement.classList.add("ready");
});
map.on("error", (event) => {
  console.error(event.error);
  statusElement.textContent = "Une ressource cartographique n’a pas chargé";
  statusElement.classList.remove("ready");
});
map.on("click", (event) => {
  const { lat, lng } = event.lngLat;
  document.querySelector<HTMLHeadingElement>("#place-title")!.textContent = `${lat.toFixed(3)}°, ${lng.toFixed(3)}°`;
  document.querySelector<HTMLParagraphElement>("#place-copy")!.textContent = `${selectedLayer.label}, ${months[selectedMonth - 1]} — normale climatique 1991–2020.`;
  placeCard.classList.add("visible");
});
map.on("moveend", saveState);

renderControls();
