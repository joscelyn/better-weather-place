# Better Weather Place

Better Weather Place is an interactive climate map for finding places with comfortable weather throughout the year. It is designed with slow travel and van life in mind: choose a month, compare climate indicators, and explore how conditions change between coasts, plains, valleys, and mountain ranges.

The project currently covers Europe and the Mediterranean basin. It uses 1991–2020 monthly climate normals rather than forecasts, so the map describes the typical climate of a place—not the weather expected on a particular day.

## What the map shows

The public interface provides six monthly layers:

| Layer | Meaning | Approximate source resolution |
|---|---|---:|
| Weather score | Composite indicator combining daytime temperature, nighttime temperature, sunshine, and rainfall | 5 km |
| Average temperature | Mean near-surface air temperature | 1 km |
| Daytime temperature | Mean daily maximum temperature | 1 km |
| Nighttime temperature | Mean daily minimum temperature | 1 km |
| Monthly precipitation | Mean total precipitation for the selected month | 1 km |
| Sunshine duration | Mean monthly sunshine duration | 5 km |

Hovering over the map reads the underlying numerical rasters and displays all available indicators for that location. The selected layer, month, map position, zoom level, and language are saved in the browser.

Rainy-day frequency is being prepared from CERRA-Land but is not yet available in the public layer list. The Canary Islands are also outside the current priority area.

## How it works

Better Weather Place does not require an application API for ordinary map use.

1. Source datasets are downloaded and reduced to twelve monthly normals for 1991–2020.
2. The rasters are converted to Cloud Optimized GeoTIFFs (COGs), aligned, and masked using the Copernicus DEM land/water mask.
3. Each climate layer is rendered into a compact raster PMTiles archive for fast map display.
4. MapLibre loads only the PMTiles ranges needed for the visible map.
5. When the pointer moves over a location, the browser reads the corresponding COG byte ranges to obtain the numerical values.

This separation keeps navigation responsive without deriving climate values from compressed map colors:

```text
Source datasets
      │
      ▼
1991–2020 monthly normals
      │
      ▼
Masked and optimized COGs ─────► numerical values on hover
      │
      ▼
Raster PMTiles ────────────────► fast map rendering
```

The canonical definition of every layer lives in [`outputs/contrat-donnees-v1.json`](outputs/contrat-donnees-v1.json). The frontend and the PMTiles builder both read this manifest for layer availability, units, palettes, resolutions, zoom levels, storage scales, asset paths, and cache versions.

## Data sources

### Climate data

- [CHELSA-monthly V2.1](https://www.chelsa-climate.org/datasets/chelsa_monthly) provides monthly temperature and precipitation at approximately 1 km resolution. The dataset is released under CC0 1.0.
- [CM SAF SARAH-3](https://doi.org/10.5676/EUM_SAF_CM/SARAH/V003) provides satellite-derived sunshine duration on a 0.05° grid up to 65° N. CM SAF products are licensed by EUMETSAT under CC BY 4.0.
- [CERRA-Land](https://cds.climate.copernicus.eu/datasets/reanalysis-cerra-land) is used for the rainy-day pipeline and validation. It is distributed through the Copernicus Climate Data Store under a CC BY licence.

### Geographic and map data

- [Copernicus DEM GLO-30](https://dataspace.copernicus.eu/explore-data/data-collections/copernicus-contributing-missions/collections-description/COP-DEM) supplies the WBM land/water mask used to remove marine pixels.
- [OpenFreeMap](https://openfreemap.org/), [OpenMapTiles](https://openmaptiles.org/), and [OpenStreetMap](https://www.openstreetmap.org/copyright) provide the vector basemap.
- [Mapzen Terrain Tiles on AWS](https://registry.opendata.aws/terrain-tiles/) provide the current hillshade layer.

The complete attribution and licensing review is available in [`outputs/audit-licences-attributions.md`](outputs/audit-licences-attributions.md). Source datasets retain their own licences; publishing derived data does not replace those obligations.

## Interpreting the map

- These are thirty-year monthly averages, not forecasts and not guarantees for a future trip.
- A 1 km or 5 km grid cell cannot represent every local microclimate.
- Mountain valleys, slopes, and summits may have very different conditions inside the same coarse cell.
- Coastal cells can mix land and water influences, even after the display mask is applied.
- Sunshine coverage currently stops at 65° N; the planned CERRA complement for northern Europe is not yet part of the published layer.
- Color scales are optimized for visual comparison. Values outside their terminal colors are preserved in the COG and remain available numerically.

## Technology

- React 19 and TypeScript
- Vite
- MapLibre GL JS
- PMTiles for compact raster map delivery
- GeoTIFF.js for client-side COG reads
- Tailwind CSS and shadcn-style UI components
- Python, Rasterio, NumPy, Pillow, and PMTiles tooling for data preparation

## Repository structure

```text
app/                    React frontend
outputs/                data contract, reports, inventories, and validation results
work/                   download, processing, tiling, and validation scripts
work/downloads/         local source downloads; ignored by Git
work/derived/           generated COGs; ignored by Git
work/tiles/             generated PMTiles; ignored by Git
```

Large climate files are intentionally not stored in Git.

## Running the frontend locally

Install a current Node.js LTS release, then:

```bash
cd app
npm install
npm run dev
```

The basemap loads without locally generated climate files, but the climate overlays and hover values require the expected data tree. If the pipeline outputs already exist under `work/`, create the development links from the repository root:

```bash
mkdir -p app/public/data
ln -s ../../../work/tiles/1991-2020 app/public/data/1991-2020
ln -s ../../derived/1991-2020-masked work/tiles/1991-2020/raw
```

Then open the URL printed by Vite, normally `http://127.0.0.1:5173/`.

Useful frontend commands:

```bash
cd app
npm run lint
npm run build
npm run preview
```

See [`app/README.md`](app/README.md) for frontend-specific details.

## Rebuilding the climate data

The processing scripts use a local Python environment under `work/.venv/`. Raw downloads, generated rasters, and tiles are resumable and excluded from Git because they are large.

The main stages are:

```text
download source data
  → build monthly normals
  → build the WBM land mask
  → apply the mask to climate COGs
  → build the composite weather score
  → render PMTiles archives
  → validate COGs, PMTiles, and HTTP range delivery
```

Start with these documents:

- [`outputs/guide-telechargement-nocturne.md`](outputs/guide-telechargement-nocturne.md)
- [`outputs/guide-production-normales-chelsa.md`](outputs/guide-production-normales-chelsa.md)
- [`outputs/guide-production-normales-sarah3.md`](outputs/guide-production-normales-sarah3.md)
- [`outputs/guide-production-masque-wbm.md`](outputs/guide-production-masque-wbm.md)
- [`outputs/plan-etape-2-architecture.md`](outputs/plan-etape-2-architecture.md)

Some source services require free personal accounts and acceptance of their data terms. Credentials must remain in local configuration files such as `~/.cdsapirc` and must never be committed.

## Validation

The repository includes reproducible checks for source comparisons, mountain and coastal behavior, palette coverage, COG integrity, PMTiles rendering, and HTTP byte-range delivery.

Recent delivery checks include:

- [`outputs/comparaison-pixels-pmtiles-cog.md`](outputs/comparaison-pixels-pmtiles-cog.md): 51/51 sampled pixels consistent between COG-derived colors and PMTiles;
- [`outputs/rapport-http-range.md`](outputs/rapport-http-range.md): successful partial reads for both PMTiles and COG files;
- [`outputs/rapport-audit-grilles-production.md`](outputs/rapport-audit-grilles-production.md): production-grid and mask audit.

## Project status

The interactive map, six core layers, multilingual interface, local preference storage, hover inspection, hybrid basemap, and the main 1991–2020 data pipeline are operational.

Work still in progress includes the complete rainy-day layer, northern sunshine coverage above 65° N, altitude in the hover panel, final production hosting, and further performance optimization.

## Software licence

A repository-wide software licence has not yet been added. Until one is provided, the source code is publicly visible but no general reuse licence is granted. Dataset and basemap licences are documented separately in the attribution audit.
