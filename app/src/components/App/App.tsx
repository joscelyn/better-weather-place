import { Button } from "@/components/Button";
import { Card } from "@/components/Card";
import {
  Dialog,
  DialogClose,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/Dialog";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/Select";
import type { ClimateLayer } from "@/types/climate";
import { climateArchiveUrl, climateLayers } from "@/utils/climate";
import { readClimateValue } from "@/utils/climateValues";
import { detectLanguage, languageNames, supportedLanguages, translations } from "@/utils/i18n";
import type { Language } from "@/utils/i18n";
import { applySystemTheme, getSystemTheme, SYSTEM_THEME_QUERY } from "@/utils/theme";
import type { SystemTheme } from "@/utils/theme";
import {
  ArrowRightIcon,
  CloudRainIcon,
  GaugeIcon,
  ChevronLeftIcon,
  ChevronRightIcon,
  InfoIcon,
  MoonIcon,
  SunIcon,
  ThermometerIcon,
  ThermometerSunIcon,
  UmbrellaIcon,
  XIcon,
} from "lucide-react";
import type { Map as MapLibreMap, StyleSpecification } from "maplibre-gl";
import * as maplibregl from "maplibre-gl";
import { Protocol } from "pmtiles";
import { useEffect, useMemo, useRef, useState } from "react";

const CLIMATE_LAYER = "climate-layer";
const CLIMATE_SOURCE = "climate-source";
const TERRAIN_SOURCE = "terrain-dem";
const RELIEF_LAYER = "terrain-hillshade";
const LAYER_FADE_DURATION = 220;
const BASEMAP_STYLE = "https://tiles.openfreemap.org/styles/positron";
const STORAGE_KEY = "better-weather-place:map-state:v1";
const LANGUAGE_STORAGE_KEY = "better-weather-place:language:v1";
const GITHUB_URL = import.meta.env.VITE_GITHUB_URL || "https://github.com";

type SavedState = {
  layerId: string;
  month: number;
  opacity: number;
  center: [number, number];
  zoom: number;
};

type Place = {
  coordinatesTitle?: string;
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
    if (!candidate) { return defaultState; }
    const layerId = climateLayers.some(layer => layer.id === candidate.layerId)
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
      && candidate.center.every(coordinate => typeof coordinate === "number" && Number.isFinite(coordinate))
      ? candidate.center as [number, number]
      : defaultState.center;
    const zoom = typeof candidate.zoom === "number" && candidate.zoom >= 2.4 && candidate.zoom <= 10
      ? candidate.zoom
      : defaultState.zoom;
    return { layerId, month, opacity, center, zoom };
  }
  catch {
    return defaultState;
  }
}

function loadLanguage(): Language {
  try {
    const savedLanguage = localStorage.getItem(LANGUAGE_STORAGE_KEY);
    const supportedLanguage = supportedLanguages.find(language => language === savedLanguage);
    return supportedLanguage ?? detectLanguage();
  }
  catch {
    return detectLanguage();
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
  }
  catch {
    // La carte reste utilisable lorsque le stockage local est désactivé.
  }
}

function firstOverlayLayer(style: StyleSpecification): string | undefined {
  const layers = style.layers ?? [];
  const lastFillIndex = layers.reduce(
    (lastIndex, layer, index) => layer.type === "fill" ? index : lastIndex,
    -1,
  );
  return layers.slice(lastFillIndex + 1).find(layer => layer.type === "line" || layer.type === "symbol")?.id;
}

function customizeBasemap(map: MapLibreMap, theme: SystemTheme): void {
  const isDark = theme === "dark";
  for (const layer of map.getStyle().layers ?? []) {
    if (layer.id === "ferry") {
      map.setLayoutProperty(layer.id, "visibility", "none");
      continue;
    }
    if (layer.type === "background") {
      map.setPaintProperty(layer.id, "background-color", isDark ? "#192324" : "#e9efe9");
      continue;
    }
    if (layer.id === "water" && layer.type === "fill") {
      map.setPaintProperty(layer.id, "fill-color", isDark ? "#233b46" : "#9fcbdc");
      map.setPaintProperty(layer.id, "fill-opacity", 1);
      continue;
    }
    if (layer.type === "fill" && /building/i.test(layer.id)) {
      map.setPaintProperty(layer.id, "fill-color", isDark ? "#2d3636" : "#dfe5df");
      map.setPaintProperty(layer.id, "fill-opacity", isDark ? 0.72 : 0.64);
      continue;
    }
    if (layer.type === "fill" && layer.id === "landuse_residential") {
      map.setPaintProperty(layer.id, "fill-color", isDark ? "#273535" : "#eaeae6");
      continue;
    }
    if (layer.type === "fill" && /^(aeroway-area|road_area_pier)$/.test(layer.id)) {
      map.setPaintProperty(layer.id, "fill-color", isDark ? "#323d3d" : "#f2f3f0");
      continue;
    }
    if (layer.type === "fill" && /(park|wood|grass|landcover)/i.test(layer.id)) {
      map.setPaintProperty(layer.id, "fill-color", isDark ? "#253a33" : "#dce9dd");
      map.setPaintProperty(layer.id, "fill-opacity", isDark ? 0.72 : 0.62);
      continue;
    }
    const isRoad = layer.type === "line"
      && (/^(tunnel|highway|bridge)[_-]/.test(layer.id) || layer.id === "road_pier")
      && !layer.id.includes("railway");
    if (isRoad) {
      const isCasing = layer.id.includes("casing");
      map.setPaintProperty(layer.id, "line-color", isDark
        ? (isCasing ? "#171d1d" : "#5f6c68")
        : (isCasing ? "#777d79" : "#eceeea"));
      map.setPaintProperty(layer.id, "line-opacity", layer.id === "highway_path" ? 0.08 : isCasing ? 0.14 : 0.24);
      continue;
    }
    if (layer.type === "line" && /(boundary|waterway)/i.test(layer.id)) {
      map.setPaintProperty(layer.id, "line-color", isDark ? "#687872" : "#8ea099");
      map.setPaintProperty(layer.id, "line-opacity", isDark ? 0.46 : 0.4);
      continue;
    }
    if (layer.type === "symbol" && layer.layout?.["text-field"]) {
      map.setPaintProperty(layer.id, "text-color", isDark ? "#d2dad7" : "#53605b");
      map.setPaintProperty(layer.id, "text-halo-color", isDark ? "#172120" : "#f3f6f2");
      map.setPaintProperty(layer.id, "text-halo-width", 1);
    }
  }
}

function applyTerrainTheme(map: MapLibreMap, theme: SystemTheme): void {
  if (!map.getLayer(RELIEF_LAYER)) { return; }
  const isDark = theme === "dark";
  map.setPaintProperty(RELIEF_LAYER, "hillshade-shadow-color", isDark ? "rgba(4, 10, 9, 0.68)" : "rgba(42, 46, 44, 0.3)");
  map.setPaintProperty(RELIEF_LAYER, "hillshade-highlight-color", isDark ? "rgba(162, 181, 174, 0.18)" : "rgba(255, 255, 255, 0.36)");
  map.setPaintProperty(RELIEF_LAYER, "hillshade-accent-color", isDark ? "rgba(70, 91, 84, 0.3)" : "rgba(96, 101, 98, 0.16)");
}

function addTerrainRelief(map: MapLibreMap, theme: SystemTheme): void {
  if (map.getSource(TERRAIN_SOURCE)) { return; }
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
  if (overlayLayer && map.getLayer("water")) { map.moveLayer("water", overlayLayer); }
  applyTerrainTheme(map, theme);
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

function ClimateLayerIcon({ layerId }: { layerId: string }) {
  switch (layerId) {
    case "comfort": return <GaugeIcon />;
    case "tavg": return <ThermometerIcon />;
    case "tmax": return <ThermometerSunIcon />;
    case "tmin": return <MoonIcon />;
    case "precipitation": return <CloudRainIcon />;
    case "sunshine": return <SunIcon />;
    default: return <UmbrellaIcon />;
  }
}

export function App() {
  const initialState = useMemo(() => loadState(), []);
  const [systemTheme, setSystemTheme] = useState<SystemTheme>(() => getSystemTheme());
  const [language, setLanguage] = useState<Language>(() => loadLanguage());
  const [layerId, setLayerId] = useState(initialState.layerId);
  const [selectedMonth, setSelectedMonth] = useState(initialState.month);
  const [opacity] = useState(initialState.opacity);
  const [mapReady, setMapReady] = useState(false);
  const [aboutOpen, setAboutOpen] = useState(false);
  const [attributionOpen, setAttributionOpen] = useState(false);
  const [placeLoading, setPlaceLoading] = useState(false);
  const [place, setPlace] = useState<Place>({ values: {} });

  const mapContainerRef = useRef<HTMLDivElement>(null);
  const mapRef = useRef<MapLibreMap | undefined>(undefined);
  const activeSourceIdRef = useRef<string | undefined>(undefined);
  const activeLayerIdRef = useRef<string | undefined>(undefined);
  const visibleSourceIdRef = useRef<string | undefined>(undefined);
  const visibleLayerIdRef = useRef<string | undefined>(undefined);
  const fadeTimersRef = useRef<Set<number>>(new Set());
  const layerRef = useRef<ClimateLayer>(climateLayers[0]);
  const monthRef = useRef(selectedMonth);
  const opacityRef = useRef(opacity);
  const placeRequestRef = useRef(0);
  const hoverTimerRef = useRef<ReturnType<typeof setTimeout> | undefined>(undefined);
  const pendingHoverRef = useRef<[number, number] | undefined>(undefined);
  const lastPlaceCoordinatesRef = useRef<[number, number] | undefined>(undefined);
  const placeReaderRef = useRef<((lng: number, lat: number) => void) | undefined>(undefined);
  const systemThemeRef = useRef(systemTheme);

  const copy = translations[language];
  const localizedLayers = useMemo(
    () => climateLayers.map(layer => ({ ...layer, ...copy.layers[layer.id] })),
    [copy],
  );
  const selectedClimateLayer = climateLayers.find(layer => layer.id === layerId) ?? climateLayers[0];
  const selectedLayer = localizedLayers.find(layer => layer.id === layerId) ?? localizedLayers[0];
  const legendIndexes = [
    selectedLayer.stops.length - 1,
    Math.round((selectedLayer.stops.length - 1) * 0.75),
    Math.round((selectedLayer.stops.length - 1) * 0.5),
    Math.round((selectedLayer.stops.length - 1) * 0.25),
    0,
  ];
  useEffect(() => {
    const mediaQuery = window.matchMedia(SYSTEM_THEME_QUERY);
    const handleThemeChange = () => setSystemTheme(mediaQuery.matches ? "dark" : "light");
    mediaQuery.addEventListener("change", handleThemeChange);
    return () => mediaQuery.removeEventListener("change", handleThemeChange);
  }, []);

  useEffect(() => {
    systemThemeRef.current = systemTheme;
    applySystemTheme(systemTheme);
    document.querySelector("meta[name=\"theme-color\"]")?.setAttribute(
      "content",
      systemTheme === "dark" ? "#111a1b" : "#e9f2ec",
    );
    const map = mapRef.current;
    if (mapReady && map) {
      customizeBasemap(map, systemTheme);
      applyTerrainTheme(map, systemTheme);
    }
  }, [mapReady, systemTheme]);

  useEffect(() => {
    document.documentElement.lang = language;
    document.querySelector("meta[name=\"description\"]")?.setAttribute("content", copy.metaDescription);
    document.querySelector("meta[property=\"og:description\"]")?.setAttribute("content", copy.metaDescription);
    document.querySelector("meta[name=\"twitter:description\"]")?.setAttribute("content", copy.metaDescription);
    try {
      localStorage.setItem(LANGUAGE_STORAGE_KEY, language);
    }
    catch {
      // La langue détectée reste active lorsque le stockage local est désactivé.
    }
  }, [copy.metaDescription, language]);

  useEffect(() => {
    const zoomInButton = mapContainerRef.current?.querySelector<HTMLButtonElement>(".maplibregl-ctrl-zoom-in");
    const zoomOutButton = mapContainerRef.current?.querySelector<HTMLButtonElement>(".maplibregl-ctrl-zoom-out");
    for (const [button, label] of [[zoomInButton, copy.ui.zoomIn], [zoomOutButton, copy.ui.zoomOut]] as const) {
      if (!button) { continue; }
      button.title = label;
      button.setAttribute("aria-label", label);
    }
  }, [copy.ui.zoomIn, copy.ui.zoomOut, mapReady]);

  useEffect(() => {
    layerRef.current = selectedClimateLayer;
    monthRef.current = selectedMonth;
    opacityRef.current = opacity;
  }, [opacity, selectedClimateLayer, selectedMonth]);

  useEffect(() => {
    const handleKeyDown = (event: KeyboardEvent) => {
      const target = event.target;
      if (event.altKey || event.ctrlKey || event.metaKey || event.shiftKey || (target instanceof HTMLElement && (
        target.isContentEditable
        || target.closest("input, textarea, select, [role='slider'], [role='combobox'], [role='listbox'], [role='option'], [role='dialog']")
      ))) { return; }

      if (event.key === "ArrowLeft" || event.key === "ArrowRight") {
        event.preventDefault();
        event.stopPropagation();
        const offset = event.key === "ArrowLeft" ? -1 : 1;
        setSelectedMonth(currentMonth => ((currentMonth - 1 + offset + 12) % 12) + 1);
      }
      else if (event.key === "ArrowUp" || event.key === "ArrowDown") {
        event.preventDefault();
        event.stopPropagation();
        const offset = event.key === "ArrowUp" ? -1 : 1;
        setLayerId((currentLayerId) => {
          const currentIndex = climateLayers.findIndex(layer => layer.id === currentLayerId);
          const nextIndex = (currentIndex + offset + climateLayers.length) % climateLayers.length;
          return climateLayers[nextIndex].id;
        });
      }
    };

    window.addEventListener("keydown", handleKeyDown, { capture: true });
    return () => window.removeEventListener("keydown", handleKeyDown, { capture: true });
  }, []);

  useEffect(() => {
    if (!mapContainerRef.current) { return; }
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
    const fadeTimers = fadeTimersRef.current;
    mapRef.current = map;
    map.addControl(new maplibregl.NavigationControl({ showCompass: false }), "top-right");

    map.on("load", () => {
      customizeBasemap(map, systemThemeRef.current);
      addTerrainRelief(map, systemThemeRef.current);
      setMapReady(true);
    });
    map.on("sourcedata", (event) => {
      if (!activeSourceIdRef.current || event.sourceId !== activeSourceIdRef.current || event.sourceDataType !== "content") { return; }
      const nextLayerId = activeLayerIdRef.current;
      if (!nextLayerId || !map.getLayer(nextLayerId)) { return; }
      if (visibleLayerIdRef.current === nextLayerId) { return; }
      const previousLayerId = visibleLayerIdRef.current;
      const previousSourceId = visibleSourceIdRef.current;
      map.setPaintProperty(nextLayerId, "raster-opacity-transition", { duration: LAYER_FADE_DURATION, delay: 0 });
      map.setPaintProperty(nextLayerId, "raster-opacity", opacityRef.current);
      visibleLayerIdRef.current = nextLayerId;
      visibleSourceIdRef.current = event.sourceId;

      if (previousLayerId && map.getLayer(previousLayerId)) {
        map.setPaintProperty(previousLayerId, "raster-opacity-transition", { duration: LAYER_FADE_DURATION, delay: 0 });
        map.setPaintProperty(previousLayerId, "raster-opacity", 0);
      }
      if (previousLayerId || previousSourceId) {
        const timer = window.setTimeout(() => {
          fadeTimers.delete(timer);
          if (previousLayerId && map.getLayer(previousLayerId)) { map.removeLayer(previousLayerId); }
          if (previousSourceId && map.getSource(previousSourceId)) { map.removeSource(previousSourceId); }
        }, LAYER_FADE_DURATION + 40);
        fadeTimers.add(timer);
      }
    });
    map.on("error", (event) => {
      console.error(event.error);
    });
    const readPlace = (lng: number, lat: number, request = ++placeRequestRef.current) => {
      lastPlaceCoordinatesRef.current = [lng, lat];
      const month = monthRef.current;
      setPlaceLoading(true);
      void Promise.all(climateLayers.map(async layer => [
        layer.id,
        await readClimateValue(layer.id, month, lng, lat),
      ] as const)).then((entries) => {
        if (request !== placeRequestRef.current) { return; }
        setPlace({ coordinatesTitle: `${lat.toFixed(3)}°, ${lng.toFixed(3)}°`, values: Object.fromEntries(entries) });
        setPlaceLoading(false);
      }).catch((error: unknown) => {
        if (request === placeRequestRef.current) { setPlaceLoading(false); }
        console.error("Lecture de la valeur climatique impossible", error);
      });
    };
    placeReaderRef.current = readPlace;
    const schedulePlaceRead = (lng: number, lat: number) => {
      pendingHoverRef.current = [lng, lat];
      const request = ++placeRequestRef.current;
      setPlaceLoading(true);
      if (hoverTimerRef.current) { clearTimeout(hoverTimerRef.current); }
      hoverTimerRef.current = setTimeout(() => {
        hoverTimerRef.current = undefined;
        const coordinates = pendingHoverRef.current;
        if (coordinates) { readPlace(...coordinates, request); }
      }, 160);
    };
    map.on("mousemove", (event) => {
      schedulePlaceRead(event.lngLat.lng, event.lngLat.lat);
    });
    map.on("click", (event) => {
      if (window.matchMedia("(hover: hover)").matches) { return; }
      readPlace(event.lngLat.lng, event.lngLat.lat);
    });
    map.on("moveend", () => persistState(layerRef.current, monthRef.current, opacityRef.current, map));

    return () => {
      if (hoverTimerRef.current) { clearTimeout(hoverTimerRef.current); }
      for (const timer of fadeTimers) { window.clearTimeout(timer); }
      fadeTimers.clear();
      placeReaderRef.current = undefined;
      map.remove();
      mapRef.current = undefined;
    };
  }, [initialState]);

  useEffect(() => {
    const coordinates = lastPlaceCoordinatesRef.current;
    if (coordinates) { placeReaderRef.current?.(...coordinates); }
  }, [selectedMonth]);

  useEffect(() => {
    const map = mapRef.current;
    if (!mapReady || !map) { return; }
    const sourceId = `${CLIMATE_SOURCE}-${selectedClimateLayer.id}-${String(selectedMonth).padStart(2, "0")}`;
    const layerId = `${CLIMATE_LAYER}-${selectedClimateLayer.id}-${String(selectedMonth).padStart(2, "0")}`;
    const previousPendingSourceId = activeSourceIdRef.current;
    const previousPendingLayerId = activeLayerIdRef.current;

    if (previousPendingLayerId && previousPendingLayerId !== visibleLayerIdRef.current && map.getLayer(previousPendingLayerId)) {
      map.removeLayer(previousPendingLayerId);
    }
    if (previousPendingSourceId && previousPendingSourceId !== visibleSourceIdRef.current && map.getSource(previousPendingSourceId)) {
      map.removeSource(previousPendingSourceId);
    }
    activeSourceIdRef.current = sourceId;
    activeLayerIdRef.current = layerId;
    map.addSource(sourceId, {
      type: "raster",
      url: climateArchiveUrl(selectedClimateLayer.id, selectedMonth),
      tileSize: 256,
      maxzoom: selectedClimateLayer.maxZoom,
      attribution: selectedClimateLayer.source,
    });
    map.addLayer({
      id: layerId,
      type: "raster",
      source: sourceId,
      paint: {
        "raster-opacity": 0,
        "raster-opacity-transition": { duration: LAYER_FADE_DURATION, delay: 0 },
        "raster-fade-duration": 180,
        "raster-resampling": "linear",
      },
    }, map.getLayer(RELIEF_LAYER) ? RELIEF_LAYER : firstOverlayLayer(map.getStyle()));
    preloadAdjacentMonths(selectedClimateLayer, selectedMonth);
  }, [mapReady, selectedClimateLayer, selectedMonth]);

  useEffect(() => {
    const map = mapRef.current;
    const visibleLayerId = visibleLayerIdRef.current;
    if (visibleLayerId && map?.getLayer(visibleLayerId)) { map.setPaintProperty(visibleLayerId, "raster-opacity", opacity); }
    persistState(selectedClimateLayer, selectedMonth, opacity, map);
  }, [opacity, selectedClimateLayer, selectedMonth]);

  function selectMonth(month: number): void {
    setSelectedMonth(((month - 1 + 12) % 12) + 1);
  }

  function selectLayer(nextLayerId: string): void {
    setLayerId(nextLayerId);
  }

  function selectLanguage(nextLanguage: string): void {
    const supportedLanguage = supportedLanguages.find(candidate => candidate === nextLanguage);
    if (supportedLanguage) { setLanguage(supportedLanguage); }
  }

  return (
    <main className="shell">
      <div ref={mapContainerRef} id="map" aria-label={copy.ui.climateMap} />

      <header className="brand-card">
        <div className="brand-mark" aria-hidden="true"><span /></div>
        <div className="brand-copy">
          <p className="eyebrow">Normales 1991–2020</p>
          <h1>Better Weather Place</h1>
        </div>
      </header>

      <div className="language-selector">
        <Select value={language} onValueChange={selectLanguage}>
          <SelectTrigger className="language-trigger" aria-label={copy.ui.language}>
            <SelectValue>{language.toUpperCase()}</SelectValue>
          </SelectTrigger>
          <SelectContent position="popper" align="end">
            {supportedLanguages.map(candidate => (
              <SelectItem key={candidate} value={candidate} lang={candidate}>{languageNames[candidate]}</SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>

      <div className="layer-selector" aria-label={copy.ui.climateDataChoice}>
        <div className="layer-selector-sizer" aria-hidden="true">
          {[...localizedLayers.map(layer => layer.label), copy.ui.rainyDays].map(label => <span key={label}>{label}</span>)}
        </div>
        <Select value={selectedLayer.id} onValueChange={selectLayer}>
          <SelectTrigger id="variable" className="variable-trigger" aria-label={`${copy.ui.display} : ${selectedLayer.label}`}>
            <span className="layer-select-value">
              <span className="layer-icon" aria-hidden="true"><ClimateLayerIcon layerId={selectedLayer.id} /></span>
              <span>{selectedLayer.label}</span>
            </span>
          </SelectTrigger>
          <SelectContent className="layer-select-content" position="popper" align="start">
            {localizedLayers.map(layer => (
              <SelectItem key={layer.id} value={layer.id} className="layer-select-item">
                <span className="layer-icon" aria-hidden="true"><ClimateLayerIcon layerId={layer.id} /></span>
                <span>{layer.label}</span>
              </SelectItem>
            ))}
            <SelectItem value="rainy-days" className="layer-select-item" disabled>
              <span className="layer-icon" aria-hidden="true"><ClimateLayerIcon layerId="rainy-days" /></span>
              <span>{copy.ui.rainyDays}</span>
            </SelectItem>
          </SelectContent>
        </Select>
      </div>

      <Card className="legend-card glass gap-0 py-0" aria-label={copy.ui.legend}>
        <div id="legend-unit">{selectedLayer.unit}</div>
        <div className="legend-scale">
          <div className="legend-gradient" style={{ background: gradientFor(selectedLayer) }} />
          <div className="legend-labels">{legendIndexes.map((index, position) => <span key={`${index}-${position}`}>{selectedLayer.stops[index][0]}</span>)}</div>
        </div>
      </Card>

      <Card className="place-card glass visible gap-0 py-0" aria-label={copy.ui.hoveredPointData}>
        {placeLoading && (
          <span className="place-loader" role="status" aria-label={copy.ui.updatingData}>
            <span aria-hidden="true" />
          </span>
        )}
        <p className="eyebrow">{Object.keys(place.values).length ? copy.months[selectedMonth - 1] : copy.ui.hoverData}</p>
        <h2>{place.coordinatesTitle ?? copy.ui.exploreMap}</h2>
        <p className="place-hint">{!place.coordinatesTitle ? copy.ui.hoverHint : Object.keys(place.values).length ? copy.ui.monthlyNormals : copy.ui.readingData}</p>
        <dl className="place-metrics">
          {localizedLayers.map((layer) => {
            const value = place.values[layer.id];
            return (
              <div key={layer.id} className={layer.id === selectedLayer.id ? "active" : ""}>
                <dt>{layer.shortLabel}</dt>
                <dd>
                  {value === undefined
                    ? "—"
                    : value === null
                      ? copy.ui.unavailable
                      : (
                          <>
                            {value.toLocaleString(copy.locale, { minimumFractionDigits: 1, maximumFractionDigits: 1 })}
                            <small>{layer.unit}</small>
                          </>
                        )}
                </dd>
              </div>
            );
          })}
        </dl>
        <Button className="place-about-button" variant="ghost" type="button" aria-label={copy.ui.aboutLabel} aria-haspopup="dialog" onClick={() => setAboutOpen(true)}>
          <span className="about-button-icon" aria-hidden="true"><InfoIcon /></span>
          <span className="about-button-copy">
            <strong>{copy.ui.learnMore}</strong>
            <small>{copy.ui.methodSourcesScore}</small>
          </span>
          <ArrowRightIcon className="about-button-arrow" aria-hidden="true" />
        </Button>
      </Card>

      <nav className="month-dock glass" aria-label={copy.ui.monthChoice}>
        <Button type="button" variant="ghost" size="icon" className="month-arrow" aria-label={copy.ui.previousMonth} onPointerUp={event => event.currentTarget.blur()} onClick={() => selectMonth(selectedMonth - 1)}><ChevronLeftIcon /></Button>
        <div className="months">
          {copy.months.map((label, index) => {
            const month = index + 1;
            return <Button key={label} type="button" variant="ghost" className={month === selectedMonth ? "active" : ""} aria-current={month === selectedMonth ? "date" : undefined} onPointerUp={event => event.currentTarget.blur()} onClick={() => selectMonth(month)}>{label}</Button>;
          })}
        </div>
        <Button type="button" variant="ghost" size="icon" className="month-arrow" aria-label={copy.ui.nextMonth} onPointerUp={event => event.currentTarget.blur()} onClick={() => selectMonth(selectedMonth + 1)}><ChevronRightIcon /></Button>
      </nav>

      <nav className="mobile-month-selector" aria-label={copy.ui.monthChoice}>
        <Select value={String(selectedMonth)} onValueChange={value => selectMonth(Number(value))}>
          <SelectTrigger className="mobile-month-trigger" aria-label={copy.ui.monthChoice}>
            <SelectValue>{copy.months[selectedMonth - 1]}</SelectValue>
          </SelectTrigger>
          <SelectContent position="popper" align="center">
            {copy.months.map((label, index) => <SelectItem key={label} value={String(index + 1)}>{label}</SelectItem>)}
          </SelectContent>
        </Select>
      </nav>

      <Button className="attribution-button glass" variant="outline" size="icon" type="button" aria-label={copy.ui.mapSourcesLabel} aria-haspopup="dialog" onClick={() => setAttributionOpen(true)}>
        <InfoIcon />
      </Button>

      <Dialog open={attributionOpen} onOpenChange={setAttributionOpen}>
        <DialogContent className="attribution-dialog glass" showCloseButton={false}>
          <DialogClose asChild>
            <Button className="dialog-close" variant="ghost" size="icon-sm" aria-label={copy.ui.closeSources}><XIcon /></Button>
          </DialogClose>
          <DialogHeader>
            <p className="eyebrow">{copy.ui.mapAndData}</p>
            <DialogTitle id="attribution-title">{copy.ui.sourcesAndAttributions}</DialogTitle>
            <DialogDescription className="sr-only">{copy.ui.sourcesDescription}</DialogDescription>
          </DialogHeader>
          <dl>
            <div>
              <dt>{copy.ui.climateData}</dt>
              <dd>
                <a href="https://www.chelsa-climate.org/datasets/chelsa_monthly" target="_blank" rel="noreferrer">CHELSA-monthly V2.1</a>
                {" (CC0 1.0)"}
                {" "}
                ·
                {" "}
                <a href="https://doi.org/10.5676/EUM_SAF_CM/SARAH/V003" target="_blank" rel="noreferrer">SARAH-3</a>
                {" — modified data © EUMETSAT, CC BY 4.0"}
              </dd>
            </div>
            <div>
              <dt>{copy.ui.baseMap}</dt>
              <dd>
                <a href="https://openfreemap.org/" target="_blank" rel="noreferrer">OpenFreeMap</a>
                {" "}
                ·
                {" "}
                <a href="https://www.openmaptiles.org/" target="_blank" rel="noreferrer">© OpenMapTiles</a>
              </dd>
            </div>
            <div>
              <dt>{copy.ui.geographicData}</dt>
              <dd><a href="https://www.openstreetmap.org/copyright" target="_blank" rel="noreferrer">{copy.ui.osmContributors}</a></dd>
            </div>
            <div>
              <dt>{copy.ui.terrain}</dt>
              <dd>
                <a href="https://registry.opendata.aws/terrain-tiles/" target="_blank" rel="noreferrer">{copy.ui.terrainProvider}</a>
                {" · "}
                <a href="https://github.com/tilezen/joerd/blob/master/docs/attribution.md" target="_blank" rel="noreferrer">source attributions</a>
              </dd>
            </div>
            <div>
              <dt>Land/water mask</dt>
              <dd>
                produced using Copernicus WorldDEM-30 © DLR e.V. 2010-2014 and © Airbus Defence and Space GmbH 2014-2018 provided under COPERNICUS by the European Union and ESA; all rights reserved.
                {" The organisations in charge of the Copernicus programme by law or by delegation do not incur any liability for any use of the Copernicus WorldDEM-30. "}
                {" "}
                <a href="https://documentation.dataspace.copernicus.eu/APIs/SentinelHub/Data/DEM/resources/license/License-COPDEM-30.pdf" target="_blank" rel="noreferrer">Licence</a>
              </dd>
            </div>
          </dl>
        </DialogContent>
      </Dialog>

      <Dialog open={aboutOpen} onOpenChange={setAboutOpen}>
        <DialogContent className="about-dialog glass" showCloseButton={false}>
          <DialogClose asChild>
            <Button className="dialog-close" variant="ghost" size="icon-sm" aria-label={copy.ui.closeAbout}><XIcon /></Button>
          </DialogClose>
          <DialogHeader>
            <DialogTitle id="about-title">{copy.ui.aboutTitle}</DialogTitle>
            <DialogDescription className="project-purpose">
              {copy.ui.aboutBeforeLink}
              {" "}
              <a href={GITHUB_URL} target="_blank" rel="noreferrer">{copy.ui.openSourceMap}</a>
              {" "}
              {copy.ui.aboutAfterLink}
            </DialogDescription>
          </DialogHeader>
          <h3 id="scoring-title">{copy.ui.scoring}</h3>
          <p>{copy.ui.scoringDescription}</p>
          <div className="score-grid" aria-label={copy.ui.scoreComposition}>
            <div>
              <strong>35 %</strong>
              <span>{copy.ui.day}</span>
              <small>{copy.ui.dayIdeal}</small>
            </div>
            <div>
              <strong>25 %</strong>
              <span>{copy.ui.night}</span>
              <small>{copy.ui.nightIdeal}</small>
            </div>
            <div>
              <strong>25 %</strong>
              <span>{copy.ui.sun}</span>
              <small>{copy.ui.sunIdeal}</small>
            </div>
            <div>
              <strong>15 %</strong>
              <span>{copy.ui.rain}</span>
              <small>{copy.ui.rainIdeal}</small>
            </div>
          </div>
          <p className="about-detail">{copy.ui.scoreDetail}</p>
          <section className="sources-block" aria-labelledby="sources-title">
            <h3 id="sources-title">{copy.ui.dataAndMethod}</h3>
            <ul>
              <li>
                <a href="https://www.chelsa-climate.org/datasets/chelsa_monthly" target="_blank" rel="noreferrer">CHELSA-monthly V2.1</a>
                {" "}
                —
                {" "}
                {copy.ui.temperatureSourceDetail}
              </li>
              <li>
                <a href="https://doi.org/10.5676/EUM_SAF_CM/SARAH/V003" target="_blank" rel="noreferrer">SARAH-3</a>
                {" "}
                —
                {" "}
                {copy.ui.sunshineSourceDetail}
              </li>
              <li>{copy.ui.normalsDetail}</li>
            </ul>
          </section>
          <Button asChild variant="ghost" className="github-link">
            <a href={GITHUB_URL} target="_blank" rel="noreferrer">
              <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 2a10 10 0 0 0-3.16 19.49c.5.09.68-.22.68-.48v-1.87c-2.78.6-3.37-1.18-3.37-1.18-.45-1.16-1.11-1.47-1.11-1.47-.91-.62.07-.61.07-.61 1 .07 1.53 1.03 1.53 1.03.9 1.53 2.35 1.09 2.92.83.09-.65.35-1.09.64-1.34-2.22-.25-4.56-1.11-4.56-4.94 0-1.09.39-1.98 1.03-2.68-.1-.25-.45-1.27.1-2.64 0 0 .84-.27 2.75 1.02A9.57 9.57 0 0 1 12 6.82c.85 0 1.71.11 2.51.34 1.91-1.29 2.75-1.02 2.75-1.02.55 1.37.2 2.39.1 2.64.64.7 1.03 1.59 1.03 2.68 0 3.84-2.34 4.68-4.57 4.93.36.31.68.92.68 1.85v2.77c0 .27.18.58.69.48A10 10 0 0 0 12 2Z" /></svg>
              {copy.ui.openGithub}
            </a>
          </Button>
        </DialogContent>
      </Dialog>
    </main>
  );
}
