import * as maplibregl from "maplibre-gl";
import type { Map as MapLibreMap, StyleSpecification } from "maplibre-gl";
import "maplibre-gl/dist/maplibre-gl.css";
import { Protocol } from "pmtiles";
import { climateArchiveUrl, climateLayers, months, type ClimateLayer } from "./climate";
import { readClimateValue } from "./climate-values";
import "./style.css";

const CLIMATE_SOURCE = "climate-source";
const CLIMATE_LAYER = "climate-layer";
const TERRAIN_SOURCE = "terrain-dem";
const RELIEF_LAYER = "terrain-hillshade";
const BASEMAP_STYLE = "https://tiles.openfreemap.org/styles/positron";
const STORAGE_KEY = "better-weather-place:map-state:v1";
const GITHUB_URL = import.meta.env.VITE_GITHUB_URL || "https://github.com";

type SavedState = {
  layerId: string;
  month: number;
  opacity: number;
  center: [number, number];
  zoom: number;
};

const defaultState: SavedState = {
  layerId: "comfort",
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

    <button id="about-button" class="about-button glass" type="button" aria-label="À propos de Better Weather Place" aria-haspopup="dialog" aria-controls="about-dialog">
      <svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="12" cy="12" r="9"></circle><path d="M12 11v6M12 7.5v.1"></path></svg>
    </button>

    <section class="control-card glass" aria-label="Choix de la donnée climatique">
      <label for="variable">Afficher</label>
      <div class="select-wrap">
        <select id="variable"></select>
        <span aria-hidden="true">⌄</span>
      </div>
      <div class="current-summary">
        <strong id="current-label"></strong>
        <div class="current-meta-row">
          <span id="current-meta"></span>
          <button id="score-more" type="button" hidden>En savoir plus</button>
        </div>
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

    <div id="hover-card" class="hover-card glass" role="status" aria-live="polite">
      <strong id="hover-value">—</strong>
      <span id="hover-context"></span>
    </div>

    <section id="place-card" class="place-card glass" aria-live="polite">
      <button id="close-place" aria-label="Fermer">×</button>
      <p class="eyebrow">Point sélectionné</p>
      <h2 id="place-title">Explorer la carte</h2>
      <p id="place-copy">Clique sur une zone pour conserver ses coordonnées et le contexte de la donnée.</p>
      <dl>
        <div><dt>Source</dt><dd id="place-source"></dd></div>
        <div><dt>Résolution</dt><dd id="place-resolution"></dd></div>
      </dl>
      <p class="prototype-note">Valeur issue du pixel climatique au point sélectionné.</p>
    </section>

    <nav class="month-dock glass" aria-label="Choix du mois">
      <button id="previous-month" class="month-arrow" aria-label="Mois précédent">←</button>
      <div id="months" class="months"></div>
      <button id="next-month" class="month-arrow" aria-label="Mois suivant">→</button>
    </nav>

    <div id="status" class="status-chip">Chargement de la carte…</div>

    <button id="attribution-button" class="attribution-button glass" type="button" aria-label="Sources et attributions de la carte" aria-haspopup="dialog" aria-controls="attribution-dialog">
      <svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="12" cy="12" r="9"></circle><path d="M12 11v6M12 7.5v.1"></path></svg>
    </button>

    <dialog id="attribution-dialog" class="attribution-dialog glass" aria-labelledby="attribution-title">
      <button id="close-attribution" class="dialog-close" type="button" aria-label="Fermer les sources et attributions">×</button>
      <p class="eyebrow">Carte et données</p>
      <h2 id="attribution-title">Sources et attributions</h2>
      <dl>
        <div><dt>Données climatiques</dt><dd><a href="https://chelsa-climate.org/" target="_blank" rel="noreferrer">CHELSA-monthly V2.1</a> · <a href="https://doi.org/10.5676/EUM_SAF_CM/SARAH/V003" target="_blank" rel="noreferrer">SARAH-3</a></dd></div>
        <div><dt>Fond de carte</dt><dd><a href="https://openfreemap.org/" target="_blank" rel="noreferrer">OpenFreeMap</a> · <a href="https://www.openmaptiles.org/" target="_blank" rel="noreferrer">© OpenMapTiles</a></dd></div>
        <div><dt>Données géographiques</dt><dd><a href="https://www.openstreetmap.org/copyright" target="_blank" rel="noreferrer">© contributeurs OpenStreetMap</a></dd></div>
        <div><dt>Relief</dt><dd><a href="https://registry.opendata.aws/terrain-tiles/" target="_blank" rel="noreferrer">Mapzen Terrain Tiles sur AWS</a></dd></div>
      </dl>
    </dialog>

    <dialog id="about-dialog" class="about-dialog glass" aria-labelledby="about-title">
      <button id="close-about" class="dialog-close" type="button" aria-label="Fermer la fenêtre À propos">×</button>
      <p class="eyebrow">À propos</p>
      <h2 id="about-title">Trouver le meilleur compromis météo</h2>
      <p class="project-purpose">Better Weather Place est une <a href="${GITHUB_URL}" target="_blank" rel="noreferrer">carte open source</a> qui permet de visualiser, mois par mois, les régions où il fait bon vivre selon différents critères climatiques.</p>
      <p>Le score météo mensuel va de 0 à 100. Il combine quatre critères avec une moyenne géométrique : un très mauvais résultat ne peut donc pas être entièrement compensé par les autres.</p>
      <div class="score-grid" aria-label="Composition du score météo">
        <div><strong>35 %</strong><span>Jour</span><small>idéal entre 22 et 27 °C</small></div>
        <div><strong>25 %</strong><span>Nuit</span><small>idéale entre 12 et 18 °C</small></div>
        <div><strong>25 %</strong><span>Soleil</span><small>idéal entre 6 et 9 h/jour</small></div>
        <div><strong>15 %</strong><span>Pluie</span><small>faible cumul favorisé</small></div>
      </div>
      <p class="about-detail">Les écarts sont pénalisés progressivement des deux côtés, avec une pénalité supplémentaire lorsque forte chaleur et fort soleil se cumulent. Ce score est un repère de confort général, pas une prévision ni un conseil médical.</p>
      <section class="sources-block" aria-labelledby="sources-title">
        <h3 id="sources-title">Données et méthode</h3>
        <ul>
          <li><a href="https://chelsa-climate.org/" target="_blank" rel="noreferrer">CHELSA-monthly V2.1</a> — températures et précipitations, environ 1 km.</li>
          <li><a href="https://doi.org/10.5676/EUM_SAF_CM/SARAH/V003" target="_blank" rel="noreferrer">SARAH-3</a> — durée d’ensoleillement, environ 5 km et jusqu’à 65° N.</li>
          <li>Normales climatiques mensuelles 1991–2020 ; résolution du score : environ 5 km.</li>
        </ul>
      </section>
      <a class="github-link" href="${GITHUB_URL}" target="_blank" rel="noreferrer">
        <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 2a10 10 0 0 0-3.16 19.49c.5.09.68-.22.68-.48v-1.87c-2.78.6-3.37-1.18-3.37-1.18-.45-1.16-1.11-1.47-1.11-1.47-.91-.62.07-.61.07-.61 1 .07 1.53 1.03 1.53 1.03.9 1.53 2.35 1.09 2.92.83.09-.65.35-1.09.64-1.34-2.22-.25-4.56-1.11-4.56-4.94 0-1.09.39-1.98 1.03-2.68-.1-.25-.45-1.27.1-2.64 0 0 .84-.27 2.75 1.02A9.57 9.57 0 0 1 12 6.82c.85 0 1.71.11 2.51.34 1.91-1.29 2.75-1.02 2.75-1.02.55 1.37.2 2.39.1 2.64.64.7 1.03 1.59 1.03 2.68 0 3.84-2.34 4.68-4.57 4.93.36.31.68.92.68 1.85v2.77c0 .27.18.58.69.48A10 10 0 0 0 12 2Z"></path></svg>
        Ouvrir GitHub
      </a>
    </dialog>
  </main>
`;

const variableSelect = document.querySelector<HTMLSelectElement>("#variable")!;
const monthsElement = document.querySelector<HTMLDivElement>("#months")!;
const statusElement = document.querySelector<HTMLDivElement>("#status")!;
const placeCard = document.querySelector<HTMLElement>("#place-card")!;
const hoverCard = document.querySelector<HTMLDivElement>("#hover-card")!;
const hoverValue = document.querySelector<HTMLElement>("#hover-value")!;
const hoverContext = document.querySelector<HTMLElement>("#hover-context")!;
let hoverTimer: number | undefined;
let hoverRequest = 0;
let placeRequest = 0;

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

function positionHoverCard(x: number, y: number): void {
  const cardWidth = 176;
  const cardHeight = 64;
  const left = Math.min(x + 16, window.innerWidth - cardWidth - 12);
  const top = Math.min(y + 16, window.innerHeight - cardHeight - 12);
  hoverCard.style.left = `${Math.max(12, left)}px`;
  hoverCard.style.top = `${Math.max(12, top)}px`;
}

async function showClimateValue(longitude: number, latitude: number, request: number): Promise<number | null> {
  const layer = selectedLayer;
  const month = selectedMonth;
  try {
    const value = await readClimateValue(layer.id, month, longitude, latitude);
    if (request !== hoverRequest) return value;
    hoverValue.textContent = value === null
      ? "Pas de donnée"
      : `${value.toLocaleString("fr-FR", { minimumFractionDigits: 1, maximumFractionDigits: 1 })} ${layer.unit}`;
    hoverContext.textContent = `${layer.shortLabel} · ${months[month - 1]}`;
    hoverCard.classList.add("visible");
    return value;
  } catch (error) {
    console.error("Lecture de la valeur climatique impossible", error);
    if (request === hoverRequest) hoverCard.classList.remove("visible");
    return null;
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

function customizeBasemap(): void {
  for (const layer of map.getStyle().layers ?? []) {
    if (layer.id === "ferry") {
      map.setLayoutProperty(layer.id, "visibility", "none");
      continue;
    }
    if (layer.id === "water" && layer.type === "fill") {
      map.setPaintProperty(layer.id, "fill-color", "#9fcbdc");
      map.setPaintProperty(layer.id, "fill-opacity", 1);
      continue;
    }
    const isRoad = layer.type === "line"
      && (/^(tunnel|highway|bridge)[_-]/.test(layer.id) || layer.id === "road_pier")
      && !layer.id.includes("railway");
    if (!isRoad) continue;
    const isCasing = layer.id.includes("casing");
    map.setPaintProperty(layer.id, "line-color", isCasing ? "#777d79" : "#eceeea");
    const roadOpacity = layer.id === "highway_path" ? 0.18 : isCasing ? 0.2 : 0.36;
    map.setPaintProperty(layer.id, "line-opacity", roadOpacity);
  }
}

function addTerrainRelief(): void {
  if (map.getSource(TERRAIN_SOURCE)) return;
  const overlayLayer = firstOverlayLayer(map.getStyle());
  map.addSource(TERRAIN_SOURCE, {
    type: "raster-dem",
    tiles: ["https://s3.amazonaws.com/elevation-tiles-prod/terrarium/{z}/{x}/{y}.png"],
    tileSize: 256,
    maxzoom: 15,
    encoding: "terrarium",
    attribution: "Terrain: Mapzen, AWS Terrain Tiles",
  });
  map.addLayer(
    {
      id: RELIEF_LAYER,
      type: "hillshade",
      source: TERRAIN_SOURCE,
      paint: {
        "hillshade-exaggeration": 0.24,
        "hillshade-illumination-direction": 315,
        "hillshade-shadow-color": "rgba(42, 46, 44, 0.3)",
        "hillshade-highlight-color": "rgba(255, 255, 255, 0.36)",
        "hillshade-accent-color": "rgba(96, 101, 98, 0.16)",
      },
    },
    overlayLayer,
  );
  // Le remplissage de l’eau repasse au-dessus du relief pour conserver une mer bleue et unie.
  if (overlayLayer && map.getLayer("water")) map.moveLayer("water", overlayLayer);
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
    map.getLayer(RELIEF_LAYER) ? RELIEF_LAYER : firstOverlayLayer(map.getStyle()),
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
  const isComfortScore = selectedLayer.id === "comfort";
  document.querySelector<HTMLSpanElement>("#current-meta")!.textContent = isComfortScore
    ? `${selectedLayer.resolution} · Score composite`
    : `${selectedLayer.resolution} · ${selectedLayer.source}`;
  document.querySelector<HTMLButtonElement>("#score-more")!.hidden = !isComfortScore;
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
  hoverRequest += 1;
  hoverCard.classList.remove("visible");
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
  hoverRequest += 1;
  hoverCard.classList.remove("visible");
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
const aboutDialog = document.querySelector<HTMLDialogElement>("#about-dialog")!;
document.querySelector<HTMLButtonElement>("#about-button")!.addEventListener("click", () => aboutDialog.showModal());
document.querySelector<HTMLButtonElement>("#score-more")!.addEventListener("click", () => aboutDialog.showModal());
document.querySelector<HTMLButtonElement>("#close-about")!.addEventListener("click", () => aboutDialog.close());
aboutDialog.addEventListener("click", (event) => {
  if (event.target === aboutDialog) aboutDialog.close();
});
const attributionDialog = document.querySelector<HTMLDialogElement>("#attribution-dialog")!;
document.querySelector<HTMLButtonElement>("#attribution-button")!.addEventListener("click", () => attributionDialog.showModal());
document.querySelector<HTMLButtonElement>("#close-attribution")!.addEventListener("click", () => attributionDialog.close());
attributionDialog.addEventListener("click", (event) => {
  if (event.target === attributionDialog) attributionDialog.close();
});

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
map.on("load", () => {
  mapReady = true;
  customizeBasemap();
  addTerrainRelief();
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
  const placeCopy = document.querySelector<HTMLParagraphElement>("#place-copy")!;
  placeCopy.textContent = `Lecture de ${selectedLayer.label.toLowerCase()}…`;
  placeCard.classList.add("visible");
  const request = ++placeRequest;
  const layer = selectedLayer;
  const month = selectedMonth;
  void readClimateValue(layer.id, month, lng, lat).then((value) => {
    if (request !== placeRequest) return;
    placeCopy.textContent = value === null
      ? `${layer.label}, ${months[month - 1]} — aucune donnée terrestre à ce point.`
      : `${value.toLocaleString("fr-FR", { minimumFractionDigits: 1, maximumFractionDigits: 1 })} ${layer.unit} · ${months[month - 1]} · normale 1991–2020.`;
  });
});
map.on("mousemove", (event) => {
  positionHoverCard(event.point.x, event.point.y);
  hoverValue.textContent = "Lecture…";
  hoverContext.textContent = `${selectedLayer.shortLabel} · ${months[selectedMonth - 1]}`;
  hoverCard.classList.add("visible");
  window.clearTimeout(hoverTimer);
  const request = ++hoverRequest;
  hoverTimer = window.setTimeout(() => {
    void showClimateValue(event.lngLat.lng, event.lngLat.lat, request);
  }, 90);
});
map.getCanvas().addEventListener("mouseleave", () => {
  window.clearTimeout(hoverTimer);
  hoverRequest += 1;
  hoverCard.classList.remove("visible");
});
map.on("moveend", saveState);

renderControls();
