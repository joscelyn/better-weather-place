import { useEffect, useMemo, useRef, useState } from "react";
import { ArrowRightIcon, ChevronLeftIcon, ChevronRightIcon, InfoIcon, XIcon } from "lucide-react";
import * as maplibregl from "maplibre-gl";
import type { Map as MapLibreMap, StyleSpecification } from "maplibre-gl";
import { Protocol } from "pmtiles";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import {
  Dialog,
  DialogClose,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Separator } from "@/components/ui/separator";
import { Slider } from "@/components/ui/slider";
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
  values: Partial<Record<string, number | null>>;
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
  const [aboutOpen, setAboutOpen] = useState(false);
  const [attributionOpen, setAttributionOpen] = useState(false);
  const [place, setPlace] = useState<Place>({
    title: "Explorer la carte",
    values: {},
  });

  const mapContainerRef = useRef<HTMLDivElement>(null);
  const mapRef = useRef<MapLibreMap | undefined>(undefined);
  const activeSourceIdRef = useRef<string | undefined>(undefined);
  const layerRef = useRef<ClimateLayer>(climateLayers[0]);
  const monthRef = useRef(selectedMonth);
  const opacityRef = useRef(opacity);
  const placeRequestRef = useRef(0);
  const hoverTimerRef = useRef<ReturnType<typeof setTimeout> | undefined>(undefined);
  const pendingHoverRef = useRef<[number, number] | undefined>(undefined);

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
    const readPlace = (lng: number, lat: number) => {
      const month = monthRef.current;
      setPlace({ title: `${lat.toFixed(3)}°, ${lng.toFixed(3)}°`, values: {} });
      const request = ++placeRequestRef.current;
      void Promise.all(climateLayers.map(async (layer) => [
        layer.id,
        await readClimateValue(layer.id, month, lng, lat),
      ] as const)).then((entries) => {
        if (request !== placeRequestRef.current) return;
        setPlace({ title: `${lat.toFixed(3)}°, ${lng.toFixed(3)}°`, values: Object.fromEntries(entries) });
      }).catch((error: unknown) => console.error("Lecture de la valeur climatique impossible", error));
    };
    const schedulePlaceRead = (lng: number, lat: number) => {
      pendingHoverRef.current = [lng, lat];
      if (hoverTimerRef.current) return;
      hoverTimerRef.current = setTimeout(() => {
        hoverTimerRef.current = undefined;
        const coordinates = pendingHoverRef.current;
        if (coordinates) readPlace(...coordinates);
      }, 120);
    };
    map.on("mousemove", (event) => {
      schedulePlaceRead(event.lngLat.lng, event.lngLat.lat);
    });
    map.on("click", (event) => {
      if (window.matchMedia("(hover: hover)").matches) return;
      readPlace(event.lngLat.lng, event.lngLat.lat);
    });
    map.on("moveend", () => persistState(layerRef.current, monthRef.current, opacityRef.current, map));

    return () => {
      if (hoverTimerRef.current) clearTimeout(hoverTimerRef.current);
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

      <Card className="control-card glass gap-0 py-0" aria-label="Choix de la donnée climatique">
        <Label htmlFor="variable">Afficher</Label>
        <Select value={selectedLayer.id} onValueChange={selectLayer}>
          <SelectTrigger id="variable" className="variable-trigger">
            <SelectValue />
          </SelectTrigger>
          <SelectContent position="popper" align="start">
            {climateLayers.map((layer) => <SelectItem key={layer.id} value={layer.id}>{layer.label}</SelectItem>)}
            <SelectItem value="rainy-days" disabled>Jours de pluie — téléchargement en cours</SelectItem>
          </SelectContent>
        </Select>
        <div className="current-summary">
          <strong>{selectedLayer.label}</strong>
          <div className="current-meta-row">
            <span>{isComfortScore ? `${selectedLayer.resolution} · Score composite` : `${selectedLayer.resolution} · ${selectedLayer.source}`}</span>
          </div>
        </div>
        <Label className="opacity-row" htmlFor="opacity"><span>Intensité</span><output>{Math.round(opacity * 100)} %</output></Label>
        <Slider id="opacity" min={25} max={100} value={[Math.round(opacity * 100)]} onValueChange={([value]) => setOpacity(value / 100)} aria-label="Intensité de la couche climatique" />
        <div className="about-section">
          <Separator />
          <Button className="about-button" variant="ghost" type="button" aria-label="À propos de Better Weather Place" aria-haspopup="dialog" onClick={() => setAboutOpen(true)}>
            <span className="about-button-icon" aria-hidden="true"><InfoIcon /></span>
            <span className="about-button-copy">
              <strong>En savoir plus</strong>
              <small>Méthode, sources et score météo</small>
            </span>
            <ArrowRightIcon className="about-button-arrow" aria-hidden="true" />
          </Button>
        </div>
      </Card>

      <Card className="legend-card glass gap-0 py-0" aria-label="Légende">
        <div id="legend-unit">{selectedLayer.unit}</div>
        <div className="legend-scale">
          <div className="legend-gradient" style={{ background: gradientFor(selectedLayer) }} />
          <div className="legend-labels">{legendIndexes.map((index, position) => <span key={`${index}-${position}`}>{selectedLayer.stops[index][0]}</span>)}</div>
        </div>
      </Card>

      <Card className="place-card glass visible gap-0 py-0" aria-live="polite">
        <p className="eyebrow">{Object.keys(place.values).length ? months[selectedMonth - 1] : "Données au survol"}</p>
        <h2>{place.title}</h2>
        <p className="place-hint">{place.title === "Explorer la carte" ? "Survolez la carte pour comparer les indicateurs météo de ce lieu." : Object.keys(place.values).length ? "Normales mensuelles 1991–2020" : "Lecture des données…"}</p>
        <dl className="place-metrics">
          {climateLayers.map((layer) => {
            const value = place.values[layer.id];
            return (
              <div key={layer.id} className={layer.id === selectedLayer.id ? "active" : ""}>
                <dt>{layer.shortLabel}</dt>
                <dd>{value === undefined ? "—" : value === null ? "N/D" : <>{value.toLocaleString("fr-FR", { minimumFractionDigits: 1, maximumFractionDigits: 1 })}<small>{layer.unit}</small></>}</dd>
              </div>
            );
          })}
        </dl>
        <p className="prototype-note">La donnée affichée sur la carte est mise en évidence.</p>
      </Card>

      <nav className="month-dock glass" aria-label="Choix du mois">
        <Button type="button" variant="ghost" size="icon" className="month-arrow" aria-label="Mois précédent" onClick={() => selectMonth(selectedMonth - 1)}><ChevronLeftIcon /></Button>
        <div className="months">
          {months.map((label, index) => {
            const month = index + 1;
            return <Button key={label} type="button" variant="ghost" className={month === selectedMonth ? "active" : ""} aria-current={month === selectedMonth ? "date" : undefined} onClick={() => selectMonth(month)}>{label}</Button>;
          })}
        </div>
        <Button type="button" variant="ghost" size="icon" className="month-arrow" aria-label="Mois suivant" onClick={() => selectMonth(selectedMonth + 1)}><ChevronRightIcon /></Button>
      </nav>

      <div className={`status-chip${statusReady ? " ready" : ""}`}>{status}</div>

      <Button className="attribution-button glass" variant="outline" size="icon" type="button" aria-label="Sources et attributions de la carte" aria-haspopup="dialog" onClick={() => setAttributionOpen(true)}>
        <InfoIcon />
      </Button>

      <Dialog open={attributionOpen} onOpenChange={setAttributionOpen}>
        <DialogContent className="attribution-dialog glass" showCloseButton={false}>
          <DialogClose asChild>
            <Button className="dialog-close" variant="ghost" size="icon-sm" aria-label="Fermer les sources et attributions"><XIcon /></Button>
          </DialogClose>
          <DialogHeader>
            <p className="eyebrow">Carte et données</p>
            <DialogTitle id="attribution-title">Sources et attributions</DialogTitle>
            <DialogDescription className="sr-only">Origine des données climatiques, géographiques et cartographiques.</DialogDescription>
          </DialogHeader>
          <dl>
            <div><dt>Données climatiques</dt><dd><a href="https://chelsa-climate.org/" target="_blank" rel="noreferrer">CHELSA-monthly V2.1</a> · <a href="https://doi.org/10.5676/EUM_SAF_CM/SARAH/V003" target="_blank" rel="noreferrer">SARAH-3</a></dd></div>
            <div><dt>Fond de carte</dt><dd><a href="https://openfreemap.org/" target="_blank" rel="noreferrer">OpenFreeMap</a> · <a href="https://www.openmaptiles.org/" target="_blank" rel="noreferrer">© OpenMapTiles</a></dd></div>
            <div><dt>Données géographiques</dt><dd><a href="https://www.openstreetmap.org/copyright" target="_blank" rel="noreferrer">© contributeurs OpenStreetMap</a></dd></div>
            <div><dt>Relief</dt><dd><a href="https://registry.opendata.aws/terrain-tiles/" target="_blank" rel="noreferrer">Mapzen Terrain Tiles sur AWS</a></dd></div>
          </dl>
        </DialogContent>
      </Dialog>

      <Dialog open={aboutOpen} onOpenChange={setAboutOpen}>
        <DialogContent className="about-dialog glass" showCloseButton={false}>
          <DialogClose asChild>
            <Button className="dialog-close" variant="ghost" size="icon-sm" aria-label="Fermer la fenêtre À propos"><XIcon /></Button>
          </DialogClose>
          <DialogHeader>
            <p className="eyebrow">À propos</p>
            <DialogTitle id="about-title">Trouver le meilleur compromis météo</DialogTitle>
            <DialogDescription className="project-purpose">Better Weather Place est une <a href={GITHUB_URL} target="_blank" rel="noreferrer">carte open source</a> qui permet de visualiser, mois par mois, les régions où il fait bon vivre selon différents critères climatiques.</DialogDescription>
          </DialogHeader>
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
          <Button asChild variant="ghost" className="github-link">
            <a href={GITHUB_URL} target="_blank" rel="noreferrer">
              <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 2a10 10 0 0 0-3.16 19.49c.5.09.68-.22.68-.48v-1.87c-2.78.6-3.37-1.18-3.37-1.18-.45-1.16-1.11-1.47-1.11-1.47-.91-.62.07-.61.07-.61 1 .07 1.53 1.03 1.53 1.03.9 1.53 2.35 1.09 2.92.83.09-.65.35-1.09.64-1.34-2.22-.25-4.56-1.11-4.56-4.94 0-1.09.39-1.98 1.03-2.68-.1-.25-.45-1.27.1-2.64 0 0 .84-.27 2.75 1.02A9.57 9.57 0 0 1 12 6.82c.85 0 1.71.11 2.51.34 1.91-1.29 2.75-1.02 2.75-1.02.55 1.37.2 2.39.1 2.64.64.7 1.03 1.59 1.03 2.68 0 3.84-2.34 4.68-4.57 4.93.36.31.68.92.68 1.85v2.77c0 .27.18.58.69.48A10 10 0 0 0 12 2Z" /></svg>
              Ouvrir GitHub
            </a>
          </Button>
        </DialogContent>
      </Dialog>
    </main>
  );
}
