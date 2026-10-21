# Better Weather Place frontend

This directory contains the React frontend for Better Weather Place. For the project overview, climate sources, scientific limitations, and data-processing pipeline, see the [main README](../README.md).

## Stack

- React 19 and TypeScript
- Vite
- MapLibre GL JS
- PMTiles raster overlays
- GeoTIFF.js for numerical COG reads
- Tailwind CSS and shadcn-style components

The frontend is static and does not require a dedicated application backend. PMTiles provide the rendered climate map, while Cloud Optimized GeoTIFFs provide numerical values on hover through HTTP range requests.

## Install and run

```bash
npm install
npm run dev
```

Vite prints the local development URL, normally `http://127.0.0.1:5173/`.

Available commands:

```bash
npm run dev       # start the development server
npm run lint      # run ESLint
npm run lint:fix  # apply safe ESLint fixes
npm run build     # type-check and create a production build
npm run preview   # serve the production build locally
```

## Local climate data

Generated climate files are too large for Git. The application expects this public URL layout:

```text
/data/1991-2020/{layer}/{month}.pmtiles
/data/1991-2020/raw/{layer}/{month}.tif
```

When the pipeline outputs exist under `work/`, create the local links from the repository root:

```bash
mkdir -p app/public/data
ln -s ../../../work/tiles/1991-2020 app/public/data/1991-2020
ln -s ../../derived/1991-2020-masked work/tiles/1991-2020/raw
```

Both links are ignored by Git. The same URL contract can later be hosted from a VPS or object storage, provided that the server supports HTTPS, byte-range requests, and CORS when files are served from another origin.

## Canonical data contract

The frontend imports [`../outputs/contrat-donnees-v1.json`](../outputs/contrat-donnees-v1.json) at build time. This manifest defines:

- the layers currently available in the interface;
- units and storage scale factors;
- color palettes;
- native resolutions and maximum zoom levels;
- PMTiles and COG URL templates;
- the asset version used for cache invalidation.

Do not duplicate these values in React components. Interface translations remain in `src/utils/i18n.ts` because presentation copy is separate from the numerical data contract.

## Runtime behavior

- MapLibre renders the OpenFreeMap basemap and the selected PMTiles raster overlay.
- Adjacent months are prefetched to make month changes feel immediate.
- GeoTIFF.js reads only the required COG ranges when climate values are requested.
- Layer, month, map center, zoom, opacity, and language preferences are stored in `localStorage`.
- The interface follows the device light or dark theme.
- Source and licence information is available from the attribution popup.

## Environment variables

Copy `.env.example` when a local override is needed:

```bash
cp .env.example .env.local
```

If it is omitted, the link falls back to the GitHub home page.

## Production build

```bash
npm run lint
npm run build
```

The generated static application is written to `dist/`. Climate files are not copied into the build automatically; deploy them under the URL layout described above and verify byte-range support with:

```bash
../work/.venv/bin/python ../work/validation/test_http_range.py \
  --base-url https://your-domain.example/
```
