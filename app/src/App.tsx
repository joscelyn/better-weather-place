import { useEffect, useMemo, useRef, useState } from "react";
import * as maplibregl from "maplibre-gl";
import type { Map as MapLibreMap, StyleSpecification } from "maplibre-gl";
import { Protocol } from "pmtiles";
import { climateArchiveUrl, climateLayers, months, type ClimateLayer } from "./climate";
import { readClimateValue } from "./climate-values";

const CLIMATE_LAYER = "climate-layer";
const CLIMATE_SOURCE = "climate-source";
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

type Place = {
  title: string;
  copy: string;
};

const defaultState: SavedState = {
  layerId: "comfort",
  month: 1,
  opacity: 0.76,
  center: [9, 46],
  zoom: 3.25,
};

const protocol = new Protocol();
maplibregl.addProtocol("pmtiles", protocol.tile);

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

function persistState(layer: ClimateLayer, month: number, opacity: number, map?: MapLibreMap): void {
  const center = map?.getCenter();
  const state: SavedState = {
    layerId: layer.id,
    month,
    opacity,
    center: center ? [center.lng, center.lat] : defaultState.center,
    zoom: map?.getZoom() ?? defaultState.zoom,
  };
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(state));
  } catch {
    // La carte reste utilisable lorsque le stockage local est désactivé.
  }
}

function firstOverlayLayer(style: StyleSpecification): string | undefined {
  return style.layers?.find((layer) => layer.type === "line" || layer.type === "symbol")?.id;
}

function customizeBasemap(map: MapLibreMap): void {
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
    map.setPaintProperty(layer.id, "line-opacity", layer.id === "highway_path" ? 0.08 : isCasing ? 0.1 : 0.2);
  }
}

function addTerrainRelief(map: MapLibreMap): void {
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
  map.addLayer({
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
  }, overlayLayer);
  if (overlayLayer && map.getLayer("water")) map.moveLayer("water", overlayLayer);
}

function gradientFor(layer: ClimateLayer): string {
  const low = layer.stops[0][0];
  const high = layer.stops.at(-1)![0];
  return `linear-gradient(to top, ${layer.stops.map(([value, color]) => {
    const percent = ((value - low) / (high - low)) * 100;
    return `${color} ${percent.toFixed(2)}%`;
  }).join(", ")})`;
}

function preloadAdjacentMonths(layer: ClimateLayer, month: number): void {
  const adjacentMonths = [month === 1 ? 12 : month - 1, month === 12 ? 1 : month + 1];
  for (const adjacentMonth of adjacentMonths) {
    const url = climateArchiveUrl(layer.id, adjacentMonth).replace("pmtiles://", "");
    void fetch(url, { headers: { Range: "bytes=0-16383" } }).catch(() => undefined);
  }
}

export function App() {
  const initialState = useMemo(loadState, []);
  const [layerId, setLayerId] = useState(initialState.layerId);
  const [selectedMonth, setSelectedMonth] = useState(initialState.month);
  const [opacity, setOpacity] = useState(initialState.opacity);
  const [mapReady, setMapReady] = useState(false);
  const [status, setStatus] = useState("Chargement de la carte…");
  const [statusReady, setStatusReady] = useState(false);
  const [place, setPlace] = useState<Place>({
    title: "Explorer la carte",
    copy: "Clique sur une zone pour afficher ses coordonnées et la valeur climatique.",
  });

  const mapContainerRef = useRef<HTMLDivElement>(null);
  const mapRef = useRef<MapLibreMap | undefined>(undefined);
  const activeSourceIdRef = useRef<string | undefined>(undefined);
  const layerRef = useRef<ClimateLayer>(climateLayers[0]);
  const monthRef = useRef(selectedMonth);
  const opacityRef = useRef(opacity);
  const placeRequestRef = useRef(0);
  const aboutDialogRef = useRef<HTMLDialogElement>(null);
  const attributionDialogRef = useRef<HTMLDialogElement>(null);

  const selectedLayer = climateLayers.find((layer) => layer.id === layerId) ?? climateLayers[0];
  const isComfortScore = selectedLayer.id === "comfort";
  const legendIndexes = [
    selectedLayer.stops.length - 1,
    Math.round((selectedLayer.stops.length - 1) * 0.75),
    Math.round((selectedLayer.stops.length - 1) * 0.5),
    Math.round((selectedLayer.stops.length - 1) * 0.25),
    0,
  ];

  layerRef.current = selectedLayer;
  monthRef.current = selectedMonth;
  opacityRef.current = opacity;

  useEffect(() => {
    if (!mapContainerRef.current) return;
    const map = new maplibregl.Map({
      container: mapContainerRef.current,
      style: BASEMAP_STYLE,
      center: initialState.center,
      zoom: initialState.zoom,
      minZoom: 2.4,
      maxZoom: 10,
      maxBounds: [[-31, 20], [51, 75]],
      attributionControl: false,
    });
    mapRef.current = map;
    map.addControl(new maplibregl.NavigationControl({ showCompass: false }), "top-right");

    map.on("load", () => {
      customizeBasemap(map);
      addTerrainRelief(map);
      setMapReady(true);
    });
    map.on("sourcedata", (event) => {
      if (!activeSourceIdRef.current || event.sourceId !== activeSourceIdRef.current) return;
      setStatus(`${layerRef.current.shortLabel} · ${months[monthRef.current - 1]}`);
      setStatusReady(true);
    });
    map.on("error", (event) => {
      console.error(event.error);
      setStatus("Une ressource cartographique n’a pas chargé");
      setStatusReady(false);
    });
    map.on("click", (event) => {
      const { lat, lng } = event.lngLat;
      const layer = layerRef.current;
      const month = monthRef.current;
      setPlace({ title: `${lat.toFixed(3)}°, ${lng.toFixed(3)}°`, copy: `Lecture de ${layer.label.toLowerCase()}…` });
      const request = ++placeRequestRef.current;
      void readClimateValue(layer.id, month, lng, lat).then((value) => {
        if (request !== placeRequestRef.current) return;
        const copy = value === null
          ? `${layer.label}, ${months[month - 1]} — aucune donnée terrestre à ce point.`
          : `${value.toLocaleString("fr-FR", { minimumFractionDigits: 1, maximumFractionDigits: 1 })} ${layer.unit} · ${months[month - 1]} · normale 1991–2020.`;
        setPlace({ title: `${lat.toFixed(3)}°, ${lng.toFixed(3)}°`, copy });
      }).catch((error: unknown) => console.error("Lecture de la valeur climatique impossible", error));
    });
    map.on("moveend", () => persistState(layerRef.current, monthRef.current, opacityRef.current, map));

    return () => {
      map.remove();
      mapRef.current = undefined;
    };
  }, [initialState]);

  useEffect(() => {
    const map = mapRef.current;
    if (!mapReady || !map) return;
    const sourceId = `${CLIMATE_SOURCE}-${selectedLayer.id}-${String(selectedMonth).padStart(2, "0")}`;
    const previousSourceId = activeSourceIdRef.current;
    activeSourceIdRef.current = sourceId;
    if (map.getLayer(CLIMATE_LAYER)) map.removeLayer(CLIMATE_LAYER);
    if (previousSourceId && map.getSource(previousSourceId)) map.removeSource(previousSourceId);
    map.addSource(sourceId, {
      type: "raster",
      url: climateArchiveUrl(selectedLayer.id, selectedMonth),
      tileSize: 256,
      maxzoom: selectedLayer.maxZoom,
      attribution: selectedLayer.source,
    });
    map.addLayer({
      id: CLIMATE_LAYER,
      type: "raster",
      source: sourceId,
      paint: {
        "raster-opacity": opacityRef.current,
        "raster-fade-duration": 180,
        "raster-resampling": "linear",
      },
    }, map.getLayer(RELIEF_LAYER) ? RELIEF_LAYER : firstOverlayLayer(map.getStyle()));
    setStatus(`Chargement · ${selectedLayer.shortLabel} · ${months[selectedMonth - 1]}`);
    setStatusReady(false);
    preloadAdjacentMonths(selectedLayer, selectedMonth);
  }, [mapReady, selectedLayer, selectedMonth]);

  useEffect(() => {
    const map = mapRef.current;
    if (map?.getLayer(CLIMATE_LAYER)) map.setPaintProperty(CLIMATE_LAYER, "raster-opacity", opacity);
    persistState(selectedLayer, selectedMonth, opacity, map);
  }, [opacity, selectedLayer, selectedMonth]);

  function selectMonth(month: number): void {
    setSelectedMonth(((month - 1 + 12) % 12) + 1);
  }

  function selectLayer(nextLayerId: string): void {
    setLayerId(nextLayerId);
  }

  return (
    <main className="shell">
      <div ref={mapContainerRef} id="map" aria-label="Carte climatique interactive" />

      <header className="brand-card glass">
        <div className="brand-mark" aria-hidden="true"><span /></div>
        <div><p className="eyebrow">Normales 1991–2020</p><h1>Better Weather Place</h1></div>
      </header>

      <section className="control-card glass" aria-label="Choix de la donnée climatique">
        <label htmlFor="variable">Afficher</label>
        <div className="select-wrap">
          <select id="variable" value={selectedLayer.id} onChange={(event) => selectLayer(event.target.value)}>
            {climateLayers.map((layer) => <option key={layer.id} value={layer.id}>{layer.label}</option>)}
            <option disabled>Jours de pluie — téléchargement en cours</option>
          </select>
          <svg viewBox="0 0 20 20" aria-hidden="true"><path d="m5 7.5 5 5 5-5" /></svg>
        </div>
        <div className="current-summary">
          <strong>{selectedLayer.label}</strong>
          <div className="current-meta-row">
            <span>{isComfortScore ? `${selectedLayer.resolution} · Score composite` : `${selectedLayer.resolution} · ${selectedLayer.source}`}</span>
          </div>
        </div>
        <label className="opacity-row" htmlFor="opacity"><span>Intensité</span><output>{Math.round(opacity * 100)} %</output></label>
        <input id="opacity" type="range" min="25" max="100" value={Math.round(opacity * 100)} onChange={(event) => setOpacity(Number(event.target.value) / 100)} />
        <div className="about-section">
          <button className="about-button" type="button" aria-label="À propos de Better Weather Place" aria-haspopup="dialog" onClick={() => aboutDialogRef.current?.showModal()}>
            <span className="about-button-icon" aria-hidden="true">i</span>
            <span className="about-button-copy">
              <strong>En savoir plus</strong>
              <small>Méthode, sources et score météo</small>
            </span>
            <span className="about-button-arrow" aria-hidden="true">→</span>
          </button>
        </div>
      </section>

      <aside className="legend-card glass" aria-label="Légende">
        <div id="legend-unit">{selectedLayer.unit}</div>
        <div className="legend-scale">
          <div className="legend-gradient" style={{ background: gradientFor(selectedLayer) }} />
          <div className="legend-labels">{legendIndexes.map((index, position) => <span key={`${index}-${position}`}>{selectedLayer.stops[index][0]}</span>)}</div>
        </div>
      </aside>

      <section className="place-card glass visible" aria-live="polite">
        <p className="eyebrow">Point sélectionné</p>
        <h2>{place.title}</h2>
        <p>{place.copy}</p>
        <dl>
          <div><dt>Source</dt><dd>{selectedLayer.source}</dd></div>
          <div><dt>Résolution</dt><dd>{selectedLayer.resolution}</dd></div>
        </dl>
        <p className="prototype-note">Valeur issue du pixel climatique au point sélectionné.</p>
      </section>

      <nav className="month-dock glass" aria-label="Choix du mois">
        <button type="button" className="month-arrow" aria-label="Mois précédent" onClick={() => selectMonth(selectedMonth - 1)}>←</button>
        <div className="months">
          {months.map((label, index) => {
            const month = index + 1;
            return <button key={label} type="button" className={month === selectedMonth ? "active" : ""} aria-current={month === selectedMonth ? "date" : undefined} onClick={() => selectMonth(month)}>{label}</button>;
          })}
        </div>
        <button type="button" className="month-arrow" aria-label="Mois suivant" onClick={() => selectMonth(selectedMonth + 1)}>→</button>
      </nav>

      <div className={`status-chip${statusReady ? " ready" : ""}`}>{status}</div>

      <button className="attribution-button glass" type="button" aria-label="Sources et attributions de la carte" aria-haspopup="dialog" onClick={() => attributionDialogRef.current?.showModal()}>
        <svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="12" cy="12" r="9" /><path d="M12 11v6M12 7.5v.1" /></svg>
      </button>

      <dialog ref={attributionDialogRef} className="attribution-dialog glass" aria-labelledby="attribution-title" onClick={(event) => event.target === event.currentTarget && event.currentTarget.close()}>
        <button className="dialog-close" type="button" aria-label="Fermer les sources et attributions" onClick={() => attributionDialogRef.current?.close()}>×</button>
        <p className="eyebrow">Carte et données</p>
        <h2 id="attribution-title">Sources et attributions</h2>
        <dl>
          <div><dt>Données climatiques</dt><dd><a href="https://chelsa-climate.org/" target="_blank" rel="noreferrer">CHELSA-monthly V2.1</a> · <a href="https://doi.org/10.5676/EUM_SAF_CM/SARAH/V003" target="_blank" rel="noreferrer">SARAH-3</a></dd></div>
          <div><dt>Fond de carte</dt><dd><a href="https://openfreemap.org/" target="_blank" rel="noreferrer">OpenFreeMap</a> · <a href="https://www.openmaptiles.org/" target="_blank" rel="noreferrer">© OpenMapTiles</a></dd></div>
          <div><dt>Données géographiques</dt><dd><a href="https://www.openstreetmap.org/copyright" target="_blank" rel="noreferrer">© contributeurs OpenStreetMap</a></dd></div>
          <div><dt>Relief</dt><dd><a href="https://registry.opendata.aws/terrain-tiles/" target="_blank" rel="noreferrer">Mapzen Terrain Tiles sur AWS</a></dd></div>
        </dl>
      </dialog>

      <dialog ref={aboutDialogRef} className="about-dialog glass" aria-labelledby="about-title" onClick={(event) => event.target === event.currentTarget && event.currentTarget.close()}>
        <button className="dialog-close" type="button" aria-label="Fermer la fenêtre À propos" onClick={() => aboutDialogRef.current?.close()}>×</button>
        <p className="eyebrow">À propos</p>
        <h2 id="about-title">Trouver le meilleur compromis météo</h2>
        <p className="project-purpose">Better Weather Place est une <a href={GITHUB_URL} target="_blank" rel="noreferrer">carte open source</a> qui permet de visualiser, mois par mois, les régions où il fait bon vivre selon différents critères climatiques.</p>
        <p>Le score météo mensuel va de 0 à 100. Il combine quatre critères avec une moyenne géométrique : un très mauvais résultat ne peut donc pas être entièrement compensé par les autres.</p>
        <div className="score-grid" aria-label="Composition du score météo">
          <div><strong>35 %</strong><span>Jour</span><small>idéal entre 22 et 27 °C</small></div>
          <div><strong>25 %</strong><span>Nuit</span><small>idéale entre 12 et 18 °C</small></div>
          <div><strong>25 %</strong><span>Soleil</span><small>idéal entre 6 et 9 h/jour</small></div>
          <div><strong>15 %</strong><span>Pluie</span><small>faible cumul favorisé</small></div>
        </div>
        <p className="about-detail">Les écarts sont pénalisés progressivement des deux côtés, avec une pénalité supplémentaire lorsque forte chaleur et fort soleil se cumulent. Ce score est un repère de confort général, pas une prévision ni un conseil médical.</p>
        <section className="sources-block" aria-labelledby="sources-title">
          <h3 id="sources-title">Données et méthode</h3>
          <ul>
            <li><a href="https://chelsa-climate.org/" target="_blank" rel="noreferrer">CHELSA-monthly V2.1</a> — températures et précipitations, environ 1 km.</li>
            <li><a href="https://doi.org/10.5676/EUM_SAF_CM/SARAH/V003" target="_blank" rel="noreferrer">SARAH-3</a> — durée d’ensoleillement, environ 5 km et jusqu’à 65° N.</li>
            <li>Normales climatiques mensuelles 1991–2020 ; résolution du score : environ 5 km.</li>
          </ul>
        </section>
        <a className="github-link" href={GITHUB_URL} target="_blank" rel="noreferrer">
          <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 2a10 10 0 0 0-3.16 19.49c.5.09.68-.22.68-.48v-1.87c-2.78.6-3.37-1.18-3.37-1.18-.45-1.16-1.11-1.47-1.11-1.47-.91-.62.07-.61.07-.61 1 .07 1.53 1.03 1.53 1.03.9 1.53 2.35 1.09 2.92.83.09-.65.35-1.09.64-1.34-2.22-.25-4.56-1.11-4.56-4.94 0-1.09.39-1.98 1.03-2.68-.1-.25-.45-1.27.1-2.64 0 0 .84-.27 2.75 1.02A9.57 9.57 0 0 1 12 6.82c.85 0 1.71.11 2.51.34 1.91-1.29 2.75-1.02 2.75-1.02.55 1.37.2 2.39.1 2.64.64.7 1.03 1.59 1.03 2.68 0 3.84-2.34 4.68-4.57 4.93.36.31.68.92.68 1.85v2.77c0 .27.18.58.69.48A10 10 0 0 0 12 2Z" /></svg>
          Ouvrir GitHub
        </a>
      </dialog>
    </main>
  );
}
